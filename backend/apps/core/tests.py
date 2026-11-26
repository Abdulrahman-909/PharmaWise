from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import Medicine, StockBatch
from apps.sales.models import Customer, Sale, SaleLine
from apps.sales.services import complete_sale

from .testing import make_org, make_user


def medicine(org, sku="SKU-1", **extra):
    return Medicine.objects.create(
        organization=org, sku=sku, generic_name="Paracetamol",
        strength="500 mg", dosage_form="Tablet", stock_unit="strip", **extra,
    )


def batch(org, med, number="B1", qty=10, days=100):
    return StockBatch.objects.create(
        organization=org, medicine=med, batch_number=number,
        expiry_date=timezone.localdate() + timedelta(days=days),
        quantity_on_hand=qty,
    )


class TenantIsolationTest(TestCase):
    """One organization must never see or touch another's data."""

    def setUp(self):
        self.org_a = make_org("Alpha Pharmacy")
        self.org_b = make_org("Beta Pharmacy")
        self.user_a = make_user(self.org_a, role="admin")
        self.user_b = make_user(self.org_b, role="admin")
        self.med_a = medicine(self.org_a, "A-1")
        self.med_b = medicine(self.org_b, "B-1")
        batch(self.org_a, self.med_a, "A-BATCH", days=10)
        batch(self.org_b, self.med_b, "B-BATCH", days=10)

        self.client_a = APIClient()
        self.client_a.force_authenticate(self.user_a)

    def test_for_organization_none_returns_nothing(self):
        self.assertEqual(Medicine.objects.for_organization(None).count(), 0)

    def test_medicine_list_only_shows_own_organization(self):
        rows = self.client_a.get("/api/medicines/").json()
        self.assertEqual([r["sku"] for r in rows], ["A-1"])

    def test_cannot_open_another_organizations_batches(self):
        response = self.client_a.get(f"/api/medicines/{self.med_b.pk}/batches/")
        self.assertEqual(response.status_code, 404)

    def test_expiring_report_only_shows_own_batches(self):
        rows = self.client_a.get("/api/reports/expiring-batches/").json()
        self.assertEqual([r["batch_number"] for r in rows], ["A-BATCH"])

    def test_daily_report_ignores_other_organizations_sales(self):
        sale_b = Sale.objects.create(
            organization=self.org_b, cashier=self.user_b, completed_at=timezone.now()
        )
        SaleLine.objects.create(
            sale=sale_b, medicine=self.med_b, package="unit", quantity=3,
            price_per_package=Decimal("10.00"), units_per_package=1,
        )
        report = self.client_a.get("/api/reports/daily-sales/").json()
        self.assertEqual(report["completed_sales"], 0)
        self.assertEqual(report["sales_after_discounts"], "0.00")

    def test_same_sku_allowed_in_different_organizations_only(self):
        medicine(self.org_b, "A-1")  # fine: a different organization
        with self.assertRaises(IntegrityError), transaction.atomic():
            medicine(self.org_a, "A-1")  # duplicate inside one organization

    def test_sale_cannot_use_another_organizations_medicine(self):
        sale = Sale.objects.create(organization=self.org_a, cashier=self.user_a)
        SaleLine.objects.create(
            sale=sale, medicine=self.med_b, package="unit", quantity=1,
            price_per_package=Decimal("10.00"), units_per_package=1,
        )
        with self.assertRaisesMessage(ValidationError, "different organization"):
            complete_sale(sale.pk)

        self.med_b.refresh_from_db()
        self.assertEqual(self.med_b.batches.get().quantity_on_hand, 10)

    def test_complete_sale_only_uses_own_organizations_batches(self):
        # Same SKU/medicine name in both organizations, stock only in org B.
        org_c = make_org("Gamma Pharmacy")
        user_c = make_user(org_c, role="admin")
        med_c = medicine(org_c, "C-1")  # no stock for Gamma
        batch(self.org_b, self.med_b, "B-EXTRA", qty=99)

        sale = Sale.objects.create(organization=org_c, cashier=user_c)
        SaleLine.objects.create(
            sale=sale, medicine=med_c, package="unit", quantity=1,
            price_per_package=Decimal("10.00"), units_per_package=1,
        )
        with self.assertRaisesMessage(ValidationError, "Insufficient unexpired stock"):
            complete_sale(sale.pk)

    def test_payment_and_return_inherit_the_sales_organization(self):
        from apps.sales.models import Payment, SaleReturn

        sale = Sale.objects.create(
            organization=self.org_a, cashier=self.user_a, completed_at=timezone.now()
        )
        payment = Payment.objects.create(
            sale=sale, amount=Decimal("5.00"), received_by=self.user_a
        )
        sale_return = SaleReturn.objects.create(
            sale=sale, created_by=self.user_a, reason="Test"
        )
        self.assertEqual(payment.organization_id, self.org_a.pk)
        self.assertEqual(sale_return.organization_id, self.org_a.pk)


class AdminScopeTest(TestCase):
    """The Django admin only lists the signed-in user's organization."""

    def setUp(self):
        self.org_a = make_org("Alpha Pharmacy")
        self.org_b = make_org("Beta Pharmacy")
        self.staff = make_user(
            self.org_a, role="admin", is_staff=True, is_superuser=True
        )
        self.platform = make_user(
            self.org_a, role="admin", username="platform",
            is_staff=True, is_superuser=True,
        )
        self.platform.organization = None
        self.platform.save()

        Customer.objects.create(organization=self.org_a, name="Ali", phone="1")
        Customer.objects.create(organization=self.org_b, name="Bashir", phone="2")
        medicine(self.org_a, "A-1")
        medicine(self.org_b, "B-1")

    def test_organization_staff_sees_only_own_customers(self):
        self.client.force_login(self.staff)
        page = self.client.get("/admin/sales/customer/")
        self.assertContains(page, "Ali")
        self.assertNotContains(page, "Bashir")

    def test_organization_staff_sees_only_own_medicines(self):
        self.client.force_login(self.staff)
        page = self.client.get("/admin/inventory/medicine/")
        self.assertContains(page, "A-1")
        self.assertNotContains(page, "B-1")

    def test_platform_admin_sees_every_organization(self):
        self.client.force_login(self.platform)
        page = self.client.get("/admin/sales/customer/")
        self.assertContains(page, "Ali")
        self.assertContains(page, "Bashir")

    def test_new_record_is_saved_in_the_users_organization(self):
        self.client.force_login(self.staff)
        response = self.client.post("/admin/sales/customer/add/", {
            "name": "Created in admin", "phone": "999",
        })
        self.assertEqual(response.status_code, 302)
        created = Customer.objects.get(name="Created in admin")
        self.assertEqual(created.organization_id, self.org_a.pk)
