# Generated by Django 2.0.1 on 2018-02-13 20:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('covered_data', '0028_auto_20180212_2145'),
    ]

    operations = [
        migrations.AddField(
            model_name='namedstormcovereddata',
            name='lat_end',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='namedstormcovereddata',
            name='lat_start',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='namedstormcovereddata',
            name='lng_end',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='namedstormcovereddata',
            name='lng_start',
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name='namedstormcovereddata',
            name='time_end',
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name='namedstormcovereddata',
            name='time_start',
            field=models.DateTimeField(null=True),
        ),
    ]