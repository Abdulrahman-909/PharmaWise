from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """User account for PharmaWise.

    A user belongs to one organization and has one role. A superuser with no
    organization is a platform administrator who can manage every tenant.
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Business owner"
        ADMIN = "admin", "Administrator"
        PHARMACIST = "pharmacist", "Pharmacist"
        CASHIER = "cashier", "Cashier"
        WAREHOUSE_MANAGER = "warehouse_manager", "Warehouse manager"
        ACCOUNTANT = "accountant", "Accountant"
        SALES_REP = "sales_rep", "Sales representative"
        DELIVERY = "delivery", "Delivery employee"
        AUDITOR = "auditor", "Read-only auditor"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
        help_text="Leave empty only for platform administrators.",
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.CASHIER
    )

    def has_app_permission(self, code):
        from .permissions import role_has_permission

        if not self.is_active:
            return False
        return role_has_permission(self.role, code)
