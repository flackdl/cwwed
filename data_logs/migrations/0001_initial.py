# Generated by Django 2.0.1 on 2018-03-21 18:00

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('named_storms', '0005_remove_namedstorm_latest_snapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='NamedStormCoveredDataLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=False)),
                ('snapshot', models.TextField(blank=True)),
                ('covered_data', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.CoveredData')),
                ('named_storm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.NamedStorm')),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='named_storms.CoveredDataProvider')),
            ],
        ),
    ]