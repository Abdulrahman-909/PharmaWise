from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Medicine(models.Model):
    sku = models.CharField("SKU", max_length=50, unique=True)
    generic_name = models.CharField(max_length=150)
    brand_name = models.CharField(max_length=150, blank=True)
    strength = models.CharField(max_length=80)
    dosage_form = models.CharField(max_length=80)
    stock_unit = models.CharField(
        max_length=20,
        choices=[
            ("strip", "Strip"),
            ("tablet", "Tablet"),
            ("capsule", "Capsule"),
            ("bottle", "Bottle"),
            ("packet", "Packet"),
            ("box", "Box"),
            ("bag", "Bag"),
            ("vial", "Vial"),
            ("ampoule", "Ampoule"),
            ("tube", "Tube"),
        ],
        default="",
        help_text="The unit used for batch quantities and the reorder level.",
    )
    is_active = models.BooleanField(default=True)
    reorder_level = models.PositiveIntegerField(null=True, blank=True)
    units_per_box = models.PositiveIntegerField(
        "Stock units per box",
        null=True,
        blank=True,
        help_text="For example, enter 10 if one box contains 10 strips.",
        validators=[MinValueValidator(1)],
    )
    unit_sale_price = models.DecimalField(
        "Selling price per stock unit (AFN)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Regular price for one strip, bottle, bag, or other stock unit.",
    )
    box_sale_price = models.DecimalField(
        "Selling price per full box (AFN)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Leave blank if this medicine has no separate box price.",
    )

    class Meta:
        ordering = ["generic_name", "strength", "sku"]

    def __str__(self):
        name = self.brand_name or self.generic_name
        return f"{name} {self.strength} ({self.dosage_form}) [{self.sku}]"


class StockBatch(models.Model):
    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.PROTECT,
        related_name="batches",
    )
    batch_number = models.CharField(max_length=80)
    expiry_date = models.DateField()
    quantity_on_hand = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["expiry_date", "batch_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["medicine", "batch_number"],
                name="unique_batch_per_medicine",
            ),
        ]

    def __str__(self):
        return f"{self.medicine.sku} — {self.batch_number}"


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class PurchaseReceipt(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_receipts",
    )
    invoice_number = models.CharField(max_length=80)
    received_on = models.DateField("Date received", default=timezone.localdate)
    posted_at = models.DateTimeField("Posted at", null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-received_on", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "invoice_number"],
                name="unique_invoice_per_supplier",
            ),
        ]

    def __str__(self):
        return f"{self.supplier} — {self.invoice_number}"


class PurchaseReceiptLine(models.Model):
    receipt = models.ForeignKey(
        PurchaseReceipt,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name="receipt_lines",
    )
    boxes_received = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    units_per_box = models.PositiveIntegerField(
        "Stock units per box on this delivery",
        validators=[MinValueValidator(1)],
    )

    @property
    def units_received(self):
        if self.boxes_received is None or self.units_per_box is None:
            return None
        return self.boxes_received * self.units_per_box

    def __str__(self):
        if self.batch_id is None:
            return "New receipt line"

        units = self.units_received
        if units is None:
            return str(self.batch)

        return f"{self.batch} — {units} units"