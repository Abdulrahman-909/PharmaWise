import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0012_organization_backfill")]

    operations = [
        migrations.AlterField(model_name="sale", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="customer", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="payment", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="paymentcorrection", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AlterField(model_name="salereturn", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
    ]
