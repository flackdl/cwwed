# Generated by Django 2.0.5 on 2019-05-17 21:52

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0030_auto_20190517_2146'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nsempsadata',
            name='bbox',
            field=django.contrib.gis.db.models.fields.GeometryField(null=True, srid=4326),
        ),
    ]