"""Shared building blocks for multi-tenant (per-organization) data."""

from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_organization(self, organization):
        """Return only this organization's rows.

        Passing None returns nothing, so a missing organization can never
        accidentally expose every tenant's data.
        """
        if organization is None:
            return self.none()
        return self.filter(organization=organization)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    pass


class TenantModel(models.Model):
    """Abstract base for every record that belongs to one organization."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="+",
        editable=True,
    )

    objects = TenantManager()

    class Meta:
        abstract = True
