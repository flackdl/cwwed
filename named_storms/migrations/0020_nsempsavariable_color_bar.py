# Generated by Django 2.0.5 on 2019-04-25 13:32

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0019_auto_20190423_1644'),
    ]

    operations = [
        migrations.AddField(
            model_name='nsempsavariable',
            name='color_bar',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=dict),
        ),
    ]
