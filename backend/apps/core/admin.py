"""Admin helpers that keep each organization's data separate."""

from django.contrib import admin


def user_organization(request):
    return getattr(request.user, "organization", None)


def is_tenant_model(model):
    return any(f.name == "organization" for f in model._meta.get_fields())


class TenantFKMixin:
    """Limit foreign-key dropdowns to the signed-in user's organization."""

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        organization = user_organization(request)
        related = db_field.remote_field.model

        if (
            organization is not None
            and db_field.name != "organization"
            and is_tenant_model(related)
            and "queryset" not in kwargs
        ):
            kwargs["queryset"] = related._default_manager.filter(
                organization=organization
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class TenantInlineMixin(TenantFKMixin):
    pass


class TenantAdminMixin(TenantFKMixin):
    """Scope a ModelAdmin to the user's organization.

    - Users who belong to an organization only see and create that
      organization's records (even if they are superusers).
    - A superuser with no organization is a platform administrator: they
      see everything and must choose the organization when adding records.
    - Anyone else with no organization sees nothing.
    """

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        organization = user_organization(request)
        if organization is not None:
            return queryset.filter(organization=organization)
        if request.user.is_superuser:
            return queryset
        return queryset.none()

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        if user_organization(request) is not None and "organization" not in exclude:
            exclude.append("organization")
        return exclude or None

    def save_model(self, request, obj, form, change):
        organization = user_organization(request)
        if organization is not None and not getattr(obj, "organization_id", None):
            obj.organization = organization
        super().save_model(request, obj, form, change)
