from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.inventory.models import (
    Medicine,
    PurchaseReceipt,
    PurchaseReceiptLine,
    StockBatch,
    Supplier,
)

from .models import Sale, SaleLine
from .services import complete_sale


class DailyProfitTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cashier = user_model.objects.create(
            **{user_model.USERNAME_FIELD: "testcashier@example.com"},
            is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.cashier)

        self.medicine = Medicine.objects.create(
            sku="TEST-PROFIT",
            generic_name="Test medicine",
            strength="500 mg",
            dosage_form="Tablet",
            stock_unit="strip",
        )

    def create_posted_delivery(self, *, boxes, older_strips=0):
        """Set up a batch with older stock and one delivery at 65 AFN per box."""
        strips_per_box = 10
        delivered_strips = boxes * strips_per_box

        batch = StockBatch.objects.create(
            medicine=self.medicine,
            batch_number="TEST-BATCH",
            expiry_date=timezone.localdate() + timedelta(days=365),
            quantity_on_hand=older_strips + delivered_strips,
        )
        receipt = PurchaseReceipt.objects.create(
            supplier=Supplier.objects.create(name="Test supplier"),
            invoice_number="TEST-RECEIPT",
            posted_at=timezone.now(),
        )
        delivery = PurchaseReceiptLine.objects.create(
            receipt=receipt,
            batch=batch,
            boxes_received=boxes,
            units_per_box=strips_per_box,
            purchase_price_per_box=Decimal("65.00"),
            remaining_cost_units=delivered_strips,
        )
        return batch, delivery

    def add_strips_to_sale(self, sale, quantity):
        return SaleLine.objects.create(
            sale=sale,
            medicine=self.medicine,
            package=SaleLine.Package.UNIT,
            quantity=quantity,
            price_per_package=Decimal("10.00"),
            units_per_package=1,
        )

    def get_daily_report(self, sale):
        sale.refresh_from_db()
        report_date = timezone.localdate(sale.completed_at)
        response = self.client.get(
            "/api/reports/daily-sales/",
            {"date": report_date.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["completed_sales"], 1)
        return report

    def test_profit_when_every_sold_strip_has_a_known_cost(self):
        self.create_posted_delivery(boxes=1)
        sale = Sale.objects.create(cashier=self.cashier)
        self.add_strips_to_sale(sale, quantity=2)

        complete_sale(sale.pk)

        report = self.get_daily_report(sale)
        self.assertEqual(report["sales_after_discounts"], "20.00")
        self.assertEqual(report["known_purchase_cost"], "13.00")
        self.assertEqual(report["units_with_unknown_cost"], 0)
        self.assertEqual(report["gross_profit"], "7.00")

    def test_older_sale_with_unknown_cost_has_no_gross_profit(self):
        # A historical sale completed before delivery-cost tracking existed.
        sale = Sale.objects.create(
            cashier=self.cashier,
            completed_at=timezone.now(),
        )
        self.add_strips_to_sale(sale, quantity=5)

        report = self.get_daily_report(sale)
        self.assertEqual(report["sales_after_discounts"], "50.00")
        self.assertEqual(report["known_purchase_cost"], "0.00")
        self.assertEqual(report["units_with_unknown_cost"], 5)
        self.assertIsNone(report["gross_profit"])

    def test_sale_uses_older_strips_before_priced_delivery(self):
        batch, delivery = self.create_posted_delivery(boxes=2, older_strips=5)
        sale = Sale.objects.create(cashier=self.cashier)
        line = self.add_strips_to_sale(sale, quantity=7)

        complete_sale(sale.pk)

        batch.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(batch.quantity_on_hand, 18)
        self.assertEqual(delivery.remaining_cost_units, 18)

        # One deduction from the batch, split across two sources of stock.
        allocation = line.batch_allocations.get()
        self.assertEqual(allocation.batch_id, batch.pk)
        self.assertEqual(allocation.quantity, 7)
        self.assertEqual(allocation.cost_parts.count(), 2)

        opening_stock = allocation.cost_parts.get(receipt_line__isnull=True)
        self.assertEqual(opening_stock.quantity, 5)
        self.assertIsNone(opening_stock.cost_afn)

        priced_stock = allocation.cost_parts.get(receipt_line=delivery)
        self.assertEqual(priced_stock.quantity, 2)
        self.assertEqual(priced_stock.cost_afn, Decimal("13.00"))

        report = self.get_daily_report(sale)
        self.assertEqual(report["sales_after_discounts"], "70.00")
        self.assertEqual(report["known_purchase_cost"], "13.00")
        self.assertEqual(report["units_with_unknown_cost"], 5)
        self.assertIsNone(report["gross_profit"])