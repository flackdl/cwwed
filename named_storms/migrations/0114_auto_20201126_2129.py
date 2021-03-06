# Generated by Django 3.1.3 on 2020-11-26 21:29

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0113_nsempsamanifestdataset_meta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='namedstorm',
            name='geo',
            field=django.contrib.gis.db.models.fields.PolygonField(geography=True, srid=4326),
        ),
        migrations.AlterField(
            model_name='namedstormcovereddata',
            name='geo',
            field=django.contrib.gis.db.models.fields.PolygonField(geography=True, srid=4326),
        ),
        migrations.AlterField(
            model_name='nsempsa',
            name='manifest',
            field=models.JSONField(),
        ),
        migrations.AlterField(
            model_name='nsempsa',
            name='validation_exceptions',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='nsempsamanifestdataset',
            name='meta',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='nsempsauserexport',
            name='bbox',
            field=django.contrib.gis.db.models.fields.PolygonField(geography=True, srid=4326),
        ),
        migrations.AlterField(
            model_name='nsempsavariable',
            name='color_bar',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='nsempsavariable',
            name='meta',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
