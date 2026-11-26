import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0012_purchasereceiptline_remaining_cost_units"), ("organizations", "0002_default_organization")]

    operations = [
        migrations.AddField(model_name="medicine", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="stockbatch", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="supplier", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="purchasereceipt", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
    ]
