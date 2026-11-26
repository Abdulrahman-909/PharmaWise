import django.db.models.deletion
from django.db import migrations, models


def assign_existing_users(apps, schema_editor):
    """Attach existing users to the default organization and give them a role."""
    User = apps.get_model("accounts", "User")
    Organization = apps.get_model("organizations", "Organization")
    organization = Organization.objects.order_by("pk").first()

    for user in User.objects.all():
        user.organization = organization
        user.role = "admin" if user.is_superuser else "cashier"
        user.save(update_fields=["organization", "role"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("organizations", "0002_default_organization"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                help_text="Leave empty only for platform administrators.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="organizations.organization",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("owner", "Business owner"),
                    ("admin", "Administrator"),
                    ("pharmacist", "Pharmacist"),
                    ("cashier", "Cashier"),
                    ("warehouse_manager", "Warehouse manager"),
                    ("accountant", "Accountant"),
                    ("sales_rep", "Sales representative"),
                    ("delivery", "Delivery employee"),
                    ("auditor", "Read-only auditor"),
                ],
                default="cashier",
                max_length=20,
            ),
        ),
        migrations.RunPython(assign_existing_users, migrations.RunPython.noop),
    ]
