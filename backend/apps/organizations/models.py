from django.db import models

from apps.core.models import TenantModel


class Organization(models.Model):
    """One pharmacy or distributor business (a tenant)."""

    class Currency(models.TextChoices):
        AFN = "AFN", "Afghani (AFN)"
        USD = "USD", "US dollar (USD)"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        DARI = "prs", "Dari"

    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    base_currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.AFN
    )
    default_language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.ENGLISH
    )
    timezone = models.CharField(max_length=64, default="Asia/Kabul")
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name


class Branch(TenantModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        verbose_name_plural = "branches"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"], name="unique_branch_code_per_org"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Warehouse(TenantModel):
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="warehouses",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_warehouse_code_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"
