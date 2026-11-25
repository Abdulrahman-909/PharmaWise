from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Medicine

from .models import Sale, SaleLine, SaleReturn, SaleReturnLine
from .services import post_sale_return


class SaleReturnQuantityTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cashier = user_model.objects.create(
            **{user_model.USERNAME_FIELD: "returncashier@example.com"},
            is_staff=True,
        )
        medicine = Medicine.objects.create(
            sku="TEST-RETURN",
            generic_name="Test medicine",
            strength="500 mg",
            dosage_form="Tablet",
            stock_unit="strip",
        )
        self.sale = Sale.objects.create(
            cashier=self.cashier,
            completed_at=timezone.now(),
        )
        self.sale_line = SaleLine.objects.create(
            sale=self.sale,
            medicine=medicine,
            package=SaleLine.Package.UNIT,
            quantity=7,
            price_per_package=Decimal("10.00"),
            units_per_package=1,
        )

    def test_second_return_can_only_claim_the_remaining_units(self):
        first_return = SaleReturn.objects.create(
            sale=self.sale,
            created_by=self.cashier,
            reason="First return",
        )
        SaleReturnLine.objects.create(
            sale_return=first_return,
            sale_line=self.sale_line,
            quantity=1,
        )
        post_sale_return(first_return.pk)

        second_return = SaleReturn.objects.create(
            sale=self.sale,
            created_by=self.cashier,
            reason="Second return",
        )
        second_line = SaleReturnLine(
            sale_return=second_return,
            sale_line=self.sale_line,
            quantity=7,
        )

        # One of the seven strips has already been returned.
        with self.assertRaises(ValidationError) as error:
            second_line.full_clean()

        self.assertIn(
            "Only 6 stock units remain available to return.",
            error.exception.message_dict["quantity"],
        )

        second_line.quantity = 6
        second_line.full_clean()
        second_line.save()
        self.assertEqual(second_return.lines.get().quantity, 6)

    def test_valid_return_can_only_be_posted_once(self):
        sale_return = SaleReturn.objects.create(
            sale=self.sale,
            created_by=self.cashier,
            reason="Return one strip",
        )
        SaleReturnLine.objects.create(
            sale_return=sale_return,
            sale_line=self.sale_line,
            quantity=1,
        )

        self.assertIsNone(sale_return.posted_at)
        post_sale_return(sale_return.pk)

        sale_return.refresh_from_db()
        first_posted_at = sale_return.posted_at
        self.assertIsNotNone(first_posted_at)
        self.assertEqual(sale_return.status, "Posted")

        with self.assertRaisesMessage(
            ValidationError,
            "This return is already posted.",
        ):
            post_sale_return(sale_return.pk)

        sale_return.refresh_from_db()
        self.assertEqual(sale_return.posted_at, first_posted_at)