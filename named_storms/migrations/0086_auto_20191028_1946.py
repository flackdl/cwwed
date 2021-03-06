# Generated by Django 2.2.6 on 2019-10-28 19:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0085_remove_nsempsa_validated_files'),
    ]

    operations = [
        migrations.AddField(
            model_name='nsempsavariable',
            name='dataset_name',
            field=models.CharField(choices=[('water_level', 'water_level'), ('wave_height', 'wave_height'), ('wind_speed', 'wind_speed'), ('wind_direction', 'wind_direction')], default='', max_length=50),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='nsempsavariable',
            name='name',
            field=models.CharField(choices=[('water_level', 'Water Level'), ('wave_height', 'Wave Height'), ('wind_speed', 'Wind Speed'), ('wind_direction', 'Wind Direction')], max_length=50),
        ),
    ]
