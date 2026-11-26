from django.db import migrations

MODELS = ["sale", "customer", "payment", "paymentcorrection", "salereturn"]


def assign_default_organization(apps, schema_editor):
    """Attach every existing row to the default organization."""
    Organization = apps.get_model("organizations", "Organization")
    organization = Organization.objects.order_by("pk").first()

    for name in MODELS:
        model = apps.get_model("sales", name)
        model.objects.filter(organization__isnull=True).update(organization=organization)


class Migration(migrations.Migration):
    dependencies = [("sales", "0011_organization_nullable")]

    operations = [migrations.RunPython(assign_default_organization, migrations.RunPython.noop)]
