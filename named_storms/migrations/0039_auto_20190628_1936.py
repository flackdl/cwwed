# Generated by Django 2.0.5 on 2019-06-28 19:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0038_auto_20190628_1518'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nsempsavariable',
            name='units',
            field=models.CharField(choices=[('m/s', 'm/s'), ('m', 'm'), ('degrees', 'degrees')], max_length=20),
        ),
    ]