import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0014_organization_backfill")]

    operations = [
        migrations.AlterField(model_name="medicine", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="stockbatch", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="supplier", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="purchasereceipt", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="medicine", name="sku", field=models.CharField(max_length=50, verbose_name="SKU")),
        migrations.AddConstraint(model_name="medicine", constraint=models.UniqueConstraint(fields=("organization", "sku"), name="unique_sku_per_organization")),
    ]
