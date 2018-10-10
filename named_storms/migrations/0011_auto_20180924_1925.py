# Generated by Django 2.0.5 on 2018-09-24 19:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0010_auto_20180924_1813'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='namedstormcovereddata',
            name='last_successful_log',
        ),
        migrations.AlterField(
            model_name='covereddataprovider',
            name='processor_factory',
            field=models.CharField(choices=[('CORE', 'CORE'), ('NDBC', 'NDBC'), ('USGS', 'USGS'), ('JPL_QSCAT_L1C', 'JPL_QSCAT_L1C'), ('JPL_SMAP_L2B', 'JPL_SMAP_L2B'), ('JPL_MET_OP_ASCAT_L2', 'JPL_MET_OP_ASCAT_L2'), ('TIDES_AND_CURRENTS', 'TIDES_AND_CURRENTS'), ('NATIONAL_WATER_MODEL', 'NATIONAL_WATER_MODEL')], help_text='Optionally specify a custom processor factory', max_length=50),
        ),
    ]