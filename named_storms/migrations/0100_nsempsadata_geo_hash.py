# Generated by Django 3.0.5 on 2020-08-25 15:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0099_auto_20200824_2346'),
    ]

    operations = [
        migrations.AddField(
            model_name='nsempsadata',
            name='geo_hash',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
    ]
