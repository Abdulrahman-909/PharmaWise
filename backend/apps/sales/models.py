from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Sale(models.Model):
    customer = models.ForeignKey(
        "Customer",
        on_delete=models.PROTECT,
        related_name="sales",
        null=True,
        blank=True,
    )
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-pk"]

    @property
    def status(self):
        return "Completed" if self.completed_at else "Draft"
    @property
    def total_due(self):
        if self.pk is None:
            return Decimal("0.00")

        return sum(
            (line.line_total for line in self.lines.all()),
            Decimal("0.00"),
        )

    def __str__(self):
        return f"Sale #{self.pk}" if self.pk else "New sale"

class SaleLine(models.Model):
    class Package(models.TextChoices):
        UNIT = "unit", "Single stock unit"
        BOX = "box", "Full box"

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    medicine = models.ForeignKey("inventory.Medicine", on_delete=models.PROTECT)
    package = models.CharField(max_length=4, choices=Package.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    discount = models.DecimalField(
        "Discount on this line (AFN)",
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    # Snapshot the selected package's price and size when it is chosen.
    price_per_package = models.DecimalField(
        max_digits=12, decimal_places=2, editable=False
    )
    units_per_package = models.PositiveIntegerField(editable=False)

    @property
    def stock_units(self):
        if self.quantity is None or self.units_per_package is None:
            return None
        return self.quantity * self.units_per_package

    @property
    def line_total(self):
        if self.quantity is None or self.price_per_package is None or self.discount is None:
            return None
        return self.quantity * self.price_per_package - self.discount

    def __str__(self):
        return f"Sale line #{self.pk}" if self.pk else "New sale line"
class SaleBatchAllocation(models.Model):
    sale_line = models.ForeignKey(
        SaleLine,
        on_delete=models.PROTECT,
        related_name="batch_allocations",
    )
    batch = models.ForeignKey(
        "inventory.StockBatch",
        on_delete=models.PROTECT,
        related_name="sale_allocations",
    )
    quantity = models.PositiveIntegerField(
        "Stock units deducted",
        validators=[MinValueValidator(1)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sale_line", "batch"],
                name="unique_batch_per_sale_line",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_allocation_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"Sale line #{self.sale_line_id} — {self.batch} — {self.quantity} units"
class Customer(models.Model):
    name = models.CharField("Customer name", max_length=150)
    phone = models.CharField("Phone number", max_length=30, db_index=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return f"{self.name} — {self.phone}"
class Payment(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(
        "Amount received (AFN)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments_received",
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["received_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_payment_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Payment for sale #{self.sale_id}: {self.amount} AFN"
class PaymentCorrection(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    amount = models.DecimalField(
        "Amount to subtract from the payment (AFN)",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    reason = models.CharField(max_length=255)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_corrections",
    )
    corrected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["corrected_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="sales_payment_correction_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Correction of {self.amount} AFN for payment #{self.payment_id}"