# Generated by Django 3.0.5 on 2020-09-07 12:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0104_auto_20200906_1452'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='nsempsacontour',
            name='meta',
        ),
    ]
