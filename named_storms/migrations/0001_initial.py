# Generated by Django 2.0.1 on 2018-08-20 20:43

import datetime
import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion
from django.utils.timezone import utc


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CoveredData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=500, unique=True)),
                ('description', models.TextField(blank=True)),
                ('active', models.BooleanField(default=True)),
                ('url', models.CharField(blank=True, max_length=5000)),
            ],
        ),
        migrations.CreateModel(
            name='CoveredDataProvider',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('processor_factory', models.CharField(choices=[('ERDDAP', 'ERDDAP'), ('NDBC', 'NDBC'), ('USGS', 'USGS'), ('JPL_QSCAT_L1C', 'JPL_QSCAT_L1C'), ('JPL_SMAP_L2B', 'JPL_SMAP_L2B'), ('JPL_MET_OP_ASCAT_L2', 'JPL_MET_OP_ASCAT_L2')], max_length=50)),
                ('processor_source', models.CharField(choices=[('FILE-GENERIC', 'FILE-GENERIC'), ('FILE-BINARY', 'FILE-BINARY'), ('DAP', 'DAP'), ('HDF', 'HDF')], max_length=50)),
                ('name', models.CharField(max_length=500)),
                ('url', models.CharField(max_length=5000)),
                ('active', models.BooleanField(default=True)),
                ('epoch_datetime', models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0, tzinfo=utc))),
                ('covered_data', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.CoveredData')),
            ],
        ),
        migrations.CreateModel(
            name='NamedStorm',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('geo', django.contrib.gis.db.models.fields.GeometryField(geography=True, srid=4326)),
                ('date_start', models.DateTimeField()),
                ('date_end', models.DateTimeField()),
                ('active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='NamedStormCoveredData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_start', models.DateTimeField()),
                ('date_end', models.DateTimeField()),
                ('geo', django.contrib.gis.db.models.fields.GeometryField(geography=True, srid=4326)),
                ('external_storm_id', models.CharField(blank=True, max_length=80)),
                ('covered_data', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.CoveredData')),
                ('named_storm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.NamedStorm')),
            ],
        ),
        migrations.CreateModel(
            name='NamedStormCoveredDataLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=False)),
                ('snapshot', models.TextField(blank=True)),
                ('exception', models.TextField(blank=True)),
                ('covered_data', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.CoveredData')),
                ('named_storm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.NamedStorm')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.CoveredDataProvider')),
            ],
        ),
        migrations.CreateModel(
            name='NSEM',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_requested', models.DateTimeField(auto_now_add=True)),
                ('date_returned', models.DateTimeField(null=True)),
                ('covered_data_snapshot', models.TextField(blank=True)),
                ('model_output_snapshot', models.TextField(blank=True)),
                ('model_output_snapshot_extracted', models.BooleanField(default=False)),
                ('named_storm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.NamedStorm')),
            ],
        ),
        migrations.AddField(
            model_name='namedstorm',
            name='covered_data',
            field=models.ManyToManyField(through='named_storms.NamedStormCoveredData', to='named_storms.CoveredData'),
        ),
    ]
