# Generated by Django 3.1.3 on 2022-05-24 21:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0121_auto_20220524_1727'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='nsempsadata',
            index=models.Index(fields=['nsem_psa_variable', 'date', 'point'], name='named_storm_nsem_data_part_idx'),
        ),
    ]
