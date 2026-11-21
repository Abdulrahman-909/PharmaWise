from django.db import models


class Medicine(models.Model):
    sku = models.CharField("SKU", max_length=50, unique=True)
    generic_name = models.CharField(max_length=150)
    brand_name = models.CharField(max_length=150, blank=True)
    strength = models.CharField(max_length=80)
    dosage_form = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)
    reorder_level = models.PositiveIntegerField(null=True, blank=True)

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