# Generated by Django 2.0.5 on 2019-10-03 15:20

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0067_auto_20191001_1414'),
    ]

    operations = [
        migrations.RenameField(
            model_name='nsempsa',
            old_name='snapshot_extracted',
            new_name='extracted',
        ),
    ]
