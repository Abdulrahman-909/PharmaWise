"""Role-based permission codes for the PharmaWise API and screens.

Django's own admin keeps using Django model permissions. These codes are the
single source of truth for the API and the React app. Every endpoint checks
them on the server; the frontend only uses them to hide buttons.
"""

from rest_framework.permissions import BasePermission

# Permission codes (add new ones here as modules are built).
INVENTORY_VIEW = "inventory.view"
INVENTORY_MANAGE = "inventory.manage"
INVENTORY_ADJUST = "inventory.adjust"
INVENTORY_ADJUST_APPROVE = "inventory.adjust.approve"
SALES_VIEW = "sales.view"
SALES_CREATE = "sales.create"
SALES_CANCEL = "sales.cancel"
SALES_RETURN = "sales.return"
PURCHASING_VIEW = "purchasing.view"
PURCHASING_MANAGE = "purchasing.manage"
CUSTOMERS_VIEW = "customers.view"
CUSTOMERS_MANAGE = "customers.manage"
REPORTS_VIEW = "reports.view"
ACCOUNTING_VIEW = "accounting.view"
ACCOUNTING_POST = "accounting.post"
PERIOD_CLOSE = "period.close"
USERS_MANAGE = "users.manage"
SETTINGS_MANAGE = "settings.manage"
AUDIT_VIEW = "audit.view"

ALL_PERMISSIONS = frozenset(
    value for name, value in globals().items() if name.isupper() and isinstance(value, str)
    and "." in value
)

_VIEW_ONLY = {
    INVENTORY_VIEW, SALES_VIEW, PURCHASING_VIEW, CUSTOMERS_VIEW,
    REPORTS_VIEW, ACCOUNTING_VIEW, AUDIT_VIEW,
}

ROLE_PERMISSIONS = {
    "owner": set(ALL_PERMISSIONS),
    "admin": set(ALL_PERMISSIONS),
    "pharmacist": {
        INVENTORY_VIEW, INVENTORY_MANAGE, SALES_VIEW, SALES_CREATE, SALES_RETURN,
        CUSTOMERS_VIEW, CUSTOMERS_MANAGE, REPORTS_VIEW,
    },
    "cashier": {
        INVENTORY_VIEW, SALES_VIEW, SALES_CREATE, CUSTOMERS_VIEW,
    },
    "warehouse_manager": {
        INVENTORY_VIEW, INVENTORY_MANAGE, INVENTORY_ADJUST,
        PURCHASING_VIEW, PURCHASING_MANAGE, REPORTS_VIEW,
    },
    "accountant": {
        SALES_VIEW, PURCHASING_VIEW, CUSTOMERS_VIEW, REPORTS_VIEW,
        ACCOUNTING_VIEW, ACCOUNTING_POST, PERIOD_CLOSE, INVENTORY_VIEW,
    },
    "sales_rep": {
        INVENTORY_VIEW, SALES_VIEW, SALES_CREATE, CUSTOMERS_VIEW, CUSTOMERS_MANAGE,
    },
    "delivery": {SALES_VIEW},
    "auditor": set(_VIEW_ONLY),
}


def role_has_permission(role, code):
    return code in ROLE_PERMISSIONS.get(role, set())


def permissions_for_role(role):
    return sorted(ROLE_PERMISSIONS.get(role, set()))


class HasAppPermission(BasePermission):
    """Require a signed-in user with an organization and the permission code."""

    code = None
    message = "You do not have permission to do this."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.organization_id is None:
            self.message = "Your account is not linked to an organization."
            return False
        # Superusers inside an organization act as that organization's admin.
        if user.is_superuser:
            return user.is_active
        return user.has_app_permission(self.code)


def require(code):
    """Build a permission class: @permission_classes([require("reports.view")])."""
    if code not in ALL_PERMISSIONS:
        raise ValueError(f"Unknown permission code: {code}")
    return type(f"Require_{code.replace('.', '_')}", (HasAppPermission,), {"code": code})
