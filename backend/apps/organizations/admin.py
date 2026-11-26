from django.contrib import admin

from apps.core.admin import TenantAdminMixin

from .models import Branch, Organization, Warehouse


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "base_currency", "default_language", "is_active")
    prepopulated_fields = {"slug": ("name",)}

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        organization = getattr(request.user, "organization", None)
        if organization is not None:
            return queryset.filter(pk=organization.pk)
        if request.user.is_superuser:
            return queryset
        return queryset.none()

    def has_add_permission(self, request):
        # Only platform administrators (no organization) create tenants.
        return (
            getattr(request.user, "organization", None) is None
            and super().has_add_permission(request)
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Branch)
class BranchAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "phone", "is_active")
    search_fields = ("name", "code")


@admin.register(Warehouse)
class WarehouseAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "branch", "is_active")
    search_fields = ("name", "code")
