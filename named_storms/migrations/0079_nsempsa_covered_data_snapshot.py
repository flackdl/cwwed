# Generated by Django 2.2.6 on 2019-10-17 17:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0078_auto_20191017_1705'),
    ]

    operations = [
        migrations.AddField(
            model_name='nsempsa',
            name='covered_data_snapshot',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='named_storms.NamedStormCoveredDataSnapshot'),
        ),
    ]
