# Generated by Django 2.0.1 on 2018-03-21 18:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_logs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='namedstormcovereddatalog',
            name='message',
            field=models.TextField(blank=True),
        ),
    ]
