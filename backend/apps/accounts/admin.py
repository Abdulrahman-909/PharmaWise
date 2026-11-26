from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.audit.services import record_audit

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "get_full_name", "organization", "role", "is_active")
    list_filter = ("role", "is_active", "organization")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("PharmaWise", {"fields": ("organization", "role")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("PharmaWise", {"fields": ("organization", "role")}),
    )

    def _own_organization(self, request):
        return getattr(request.user, "organization", None)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        organization = self._own_organization(request)
        if organization is not None:
            return queryset.filter(organization=organization)
        if request.user.is_superuser:
            return queryset
        return queryset.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Organization users can only create users inside their own
        # organization, never promote anyone to platform superuser.
        if self._own_organization(request) is not None:
            for name in ("organization", "is_superuser"):
                if name in form.base_fields:
                    del form.base_fields[name]
        return form

    def save_model(self, request, obj, form, change):
        organization = self._own_organization(request)
        if organization is not None:
            obj.organization = organization
            obj.is_superuser = obj.is_superuser if change else False
        old_role = None
        if change:
            old_role = type(obj).objects.filter(pk=obj.pk).values_list("role", flat=True).first()
        super().save_model(request, obj, form, change)
        if change and old_role and old_role != obj.role:
            record_audit(
                "user.role_changed",
                request=request,
                target=obj,
                details={"from": old_role, "to": obj.role},
            )
