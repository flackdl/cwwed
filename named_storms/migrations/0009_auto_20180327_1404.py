# Generated by Django 2.0.1 on 2018-03-27 14:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0008_auto_20180322_1811'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='nsem',
            options={'permissions': (('download', 'Can download data'),)},
        ),
    ]
