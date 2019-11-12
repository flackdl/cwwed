# Generated by Django 2.2.6 on 2019-10-28 20:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0086_auto_20191028_1946'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='nsempsavariable',
            name='dataset_name',
        ),
        migrations.AlterField(
            model_name='nsempsavariable',
            name='name',
            field=models.CharField(choices=[('water_level', 'Water Level'), ('wave_height', 'Wave Height'), ('wind_speed', 'Wind Speed'), ('wind_direction', 'Wind Direction'), ('water_level_max', 'Water Level Max'), ('wind_speed_max', 'Wind Speed Max')], max_length=50),
        ),
    ]