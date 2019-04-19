# Generated by Django 2.0.5 on 2019-04-19 18:35

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0017_auto_20190419_1835'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nsempsa',
            name='color',
            field=models.CharField(max_length=7),
        ),
        migrations.AlterField(
            model_name='nsempsa',
            name='date',
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name='nsempsa',
            name='geo',
            field=django.contrib.gis.db.models.fields.MultiPolygonField(geography=True, srid=4326),
        ),
        migrations.AlterField(
            model_name='nsempsa',
            name='value',
            field=models.FloatField(),
        ),
        migrations.AlterField(
            model_name='nsempsa',
            name='variable',
            field=models.CharField(max_length=50),
        ),
    ]