import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0010_salereturnline"), ("organizations", "0002_default_organization")]

    operations = [
        migrations.AddField(model_name="sale", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="customer", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="payment", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="paymentcorrection", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
        migrations.AddField(model_name="salereturn", name="organization", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organizations.organization")),
    ]
