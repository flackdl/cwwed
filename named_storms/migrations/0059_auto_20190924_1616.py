# Generated by Django 2.0.5 on 2019-09-24 16:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0058_auto_20190923_1656'),
    ]

    operations = [
        migrations.RenameField(
            model_name='nsempsa',
            old_name='date_processed',
            new_name='date_validated',
        ),
    ]
