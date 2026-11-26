from django.db import migrations


def create_default_organization(apps, schema_editor):
    """Every install starts with one organization.

    Existing rows created before multi-tenancy are attached to it by the
    migrations in the other apps, so no data is lost or orphaned.
    """
    Organization = apps.get_model("organizations", "Organization")
    Branch = apps.get_model("organizations", "Branch")
    Warehouse = apps.get_model("organizations", "Warehouse")

    if Organization.objects.exists():
        return

    organization = Organization.objects.create(
        name="Default Pharmacy", slug="default-pharmacy"
    )
    branch = Branch.objects.create(
        organization=organization, name="Main Branch", code="MAIN"
    )
    Warehouse.objects.create(
        organization=organization, branch=branch, name="Main Warehouse", code="WH1"
    )


class Migration(migrations.Migration):
    dependencies = [("organizations", "0001_initial")]

    operations = [
        migrations.RunPython(create_default_organization, migrations.RunPython.noop),
    ]
