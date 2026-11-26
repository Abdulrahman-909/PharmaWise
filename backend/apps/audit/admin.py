from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "username", "ip_address", "target_type", "target_id")
    list_filter = ("action",)
    search_fields = ("username", "action", "target_id")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        organization = getattr(request.user, "organization", None)
        if organization is not None:
            return queryset.filter(organization=organization)
        if request.user.is_superuser:
            return queryset
        return queryset.none()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
