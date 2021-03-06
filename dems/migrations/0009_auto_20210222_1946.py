# Generated by Django 3.1.3 on 2021-02-22 19:46

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dems', '0008_auto_20210222_1943'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dem',
            name='boundary',
            field=django.contrib.gis.db.models.fields.PolygonField(default='POLYGON ((-84.75055555554127 29.24944444812391, -84.75055555554127 29.50055555220391, -84.49944445146127 29.50055555220391, -84.49944445146127 29.24944444812391, -84.75055555554127 29.24944444812391))', geography=True, srid=4326),
            preserve_default=False,
        ),
    ]
