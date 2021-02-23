# Generated by Django 3.1.3 on 2021-02-22 16:01

import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='DemSource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.CharField(max_length=1000)),
            ],
        ),
        migrations.CreateModel(
            name='DemSourceLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_updated', models.DateTimeField(auto_now=True)),
                ('dems_added', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=1000), size=None)),
                ('dems_updated', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=1000), size=None)),
                ('dems_removed', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=1000), size=None)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dems.demsource')),
            ],
        ),
        migrations.CreateModel(
            name='Dem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=1000)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dems.demsource')),
            ],
        ),
    ]