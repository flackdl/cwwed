# Generated by Django 3.0.5 on 2020-09-06 14:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0103_auto_20200827_1849'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='nsempsadata',
            name='named_storm_nsem_ps_395346_idx',
        ),
        migrations.AddIndex(
            model_name='nsempsadata',
            index=models.Index(fields=['nsem_psa_variable', 'date', 'point'], name='named_storm_nsem_ps_74649d_idx'),
        ),
    ]
