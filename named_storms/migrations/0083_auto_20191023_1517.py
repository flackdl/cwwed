# Generated by Django 2.2.6 on 2019-10-23 15:17

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0082_auto_20191022_1943'),
    ]

    operations = [
        migrations.RenameField(
            model_name='namedstormcovereddatalog',
            old_name='date',
            new_name='date_created',
        ),
    ]
