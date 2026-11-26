from django.db import migrations

MODELS = ["medicine", "stockbatch", "supplier", "purchasereceipt"]


def assign_default_organization(apps, schema_editor):
    """Attach every existing row to the default organization."""
    Organization = apps.get_model("organizations", "Organization")
    organization = Organization.objects.order_by("pk").first()

    for name in MODELS:
        model = apps.get_model("inventory", name)
        model.objects.filter(organization__isnull=True).update(organization=organization)


class Migration(migrations.Migration):
    dependencies = [("inventory", "0013_organization_nullable")]

    operations = [migrations.RunPython(assign_default_organization, migrations.RunPython.noop)]
