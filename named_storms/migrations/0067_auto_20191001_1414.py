# Generated by Django 2.0.5 on 2019-10-01 14:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0066_auto_20191001_1413'),
    ]

    operations = [
        migrations.RenameField(
            model_name='nsempsa',
            old_name='date_validated',
            new_name='date_validation',
        ),
    ]