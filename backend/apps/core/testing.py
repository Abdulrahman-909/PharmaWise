"""Small helpers shared by the test suites."""

from django.contrib.auth import get_user_model

from apps.organizations.models import Organization


def make_org(name="Test Pharmacy", slug=None):
    return Organization.objects.create(
        name=name, slug=slug or name.lower().replace(" ", "-")
    )


def make_user(organization, role="cashier", username=None, **extra):
    User = get_user_model()
    return User.objects.create_user(
        username=username or f"{role}-{organization.slug}",
        password="StrongPass!234",
        organization=organization,
        role=role,
        **extra,
    )
