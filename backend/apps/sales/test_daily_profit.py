from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import Medicine, PurchaseReceipt, PurchaseReceiptLine
from apps.inventory.models import StockBatch, Supplier
from .models import Sale, SaleLine
from .services import complete_sale


class DailyProfitTest(TestCase):
    def test_profit_when_every_sold_strip_has_a_known_cost(self):
        user_model = get_user_model()
        cashier = user_model.objects.create(
            **{user_model.USERNAME_FIELD: "testcashier@example.com"},
            is_staff=True,
        )

        # Start with one posted box of 10 strips, purchased for 65 AFN.
        medicine = Medicine.objects.create(
            sku="TEST-PROFIT",
            generic_name="Test medicine",
            strength="500 mg",
            dosage_form="Tablet",
            stock_unit="strip",
        )
        batch = StockBatch.objects.create(
            medicine=medicine,
            batch_number="TEST-BOX",
            expiry_date=timezone.localdate().replace(year=2099, month=12, day=31),
            quantity_on_hand=10,
        )
        supplier = Supplier.objects.create(name="Test supplier")
        receipt = PurchaseReceipt.objects.create(
            supplier=supplier,
            invoice_number="TEST-001",
            posted_at=timezone.now(),
        )
        PurchaseReceiptLine.objects.create(
            receipt=receipt,
            batch=batch,
            boxes_received=1,
            units_per_box=10,
            purchase_price_per_box=Decimal("65.00"),
            remaining_cost_units=10,
        )

        # Sell two strips at 10 AFN each using the real checkout function.
        sale = Sale.objects.create(cashier=cashier)
        SaleLine.objects.create(
            sale=sale,
            medicine=medicine,
            package=SaleLine.Package.UNIT,
            quantity=2,
            price_per_package=Decimal("10.00"),
            units_per_package=1,
        )
        complete_sale(sale.pk)
        sale.refresh_from_db()

        client = APIClient()
        client.force_authenticate(user=cashier)
        response = client.get(
            "/api/reports/daily-sales/",
            {"date": timezone.localdate(sale.completed_at).isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["completed_sales"], 1)
        self.assertEqual(report["sales_after_discounts"], "20.00")
        self.assertEqual(report["known_purchase_cost"], "13.00")
        self.assertEqual(report["units_with_unknown_cost"], 0)
        self.assertEqual(report["gross_profit"], "7.00")