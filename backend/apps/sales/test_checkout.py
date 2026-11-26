from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.testing import make_org
from apps.inventory.models import Medicine, StockBatch
from .models import CheckoutRecord, Customer, Payment, Sale


class CashierCheckoutTest(TestCase):
    def setUp(self):
        self.org = make_org("Test pharmacy")
        self.user = get_user_model().objects.create(username="cashier", organization=self.org, role="cashier")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        medicine = Medicine.objects.create(
            organization=self.org, sku="MED-TEST", generic_name="Test", strength="500 mg", dosage_form="Tablet",
            stock_unit="strip", unit_sale_price=10, box_sale_price=90, units_per_box=10,
        )
        self.batch = StockBatch.objects.create(
            organization=self.org, medicine=medicine, batch_number="ONE", quantity_on_hand=18,
            expiry_date=timezone.localdate() + timedelta(days=90),
        )
        self.body = {"key": str(uuid4()), "customer": None, "paid": "80.00", "lines": [{
            "medicine": medicine.pk, "package": "box", "quantity": 1, "discount": "10.00",
            "expected_price": "90.00", "expected_units": 10,
        }]}

    def submit(self):
        return self.client.post("/api/checkout/", self.body, format="json")

    def test_cash_box_discount_and_retry(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["total"], "80.00")
        self.assertEqual(self.submit().data, response.data)
        self.assertEqual(Payment.objects.get().amount, Decimal("80.00"))
        self.assertEqual(Sale.objects.count(), 1)
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity_on_hand, 8)
        self.body["paid"] = "79.00"
        self.assertEqual(self.submit().status_code, 400)

    def test_partial_payment_records_customer_balance(self):
        self.body["customer"] = Customer.objects.create(organization=self.org, name="Test", phone="000").pk
        self.body["paid"] = "30.00"
        result = self.submit()
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["balance"], "50.00")
        self.assertEqual(Payment.objects.get().amount, Decimal("30.00"))
        self.assertEqual(Sale.objects.get().customer_id, self.body["customer"])

    def test_credit_requires_customer(self):
        self.body["paid"] = "0.00"
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_insufficient_stock_rolls_back_sale_payment_and_key(self):
        self.body["lines"][0]["quantity"] = 2
        self.body["paid"] = "170.00"
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Sale.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(CheckoutRecord.objects.exists())
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.quantity_on_hand, 18)

    def test_stale_catalog_price_rejected(self):
        self.body["lines"][0]["expected_price"] = "85.00"
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_read_only_staff_cannot_checkout(self):
        self.user.role = "auditor"
        self.user.save()
        self.client.force_authenticate(get_user_model().objects.get(pk=self.user.pk))
        self.assertEqual(self.submit().status_code, 403)

    def test_session_checkout_requires_csrf(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        self.assertEqual(self.submit().status_code, 403)
        token = self.client.get("/api/checkout/options/").data["csrf"]
        self.client.credentials(HTTP_X_CSRFTOKEN=token)
        self.assertEqual(self.submit().status_code, 201)

    def test_customer_must_belong_to_cashiers_pharmacy(self):
        other = make_org("Other pharmacy")
        self.body["customer"] = Customer.objects.create(organization=other, name="Other").pk
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(Sale.objects.exists())

    def test_record_repayment_once_and_reject_overpayment(self):
        self.body["customer"] = Customer.objects.create(organization=self.org, name="Test", phone="000").pk
        self.body["paid"] = "5.00"
        sale_id = self.submit().data["sale"]
        url = f"/api/receipts/{sale_id}/repay/"
        payload = {"key": str(uuid4()), "amount": "10.00"}
        first = self.client.post(url, payload, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["balance"], "65.00")
        self.assertEqual(self.client.post(url, payload, format="json").data, first.data)
        self.assertEqual(self.client.post(url, {"key": str(uuid4()), "amount": "66.00"}, format="json").status_code, 400)
        self.assertEqual(Payment.objects.count(), 2)

    def test_wholesale_price_requires_business_account(self):
        self.body["lines"][0]["agreed_price"] = "75.00"
        self.body["paid"] = "65.00"
        self.assertEqual(self.submit().status_code, 400)
        self.body["customer"] = Customer.objects.create(organization=self.org, name="Pharmacy", phone="011", is_business=True).pk
        result = self.submit()
        self.assertEqual(result.status_code, 201, result.data)
        self.assertTrue(result.data["wholesale"])
        self.assertEqual(result.data["total"], "65.00")
