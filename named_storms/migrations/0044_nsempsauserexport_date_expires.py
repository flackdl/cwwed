# Generated by Django 2.0.5 on 2019-08-12 15:40

import pytz
import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('named_storms', '0043_nsempsauserexport'),
    ]

    operations = [
        migrations.AddField(
            model_name='nsempsauserexport',
            name='date_expires',
            field=models.DateTimeField(default=datetime.datetime(2019, 8, 12, 15, 40, 35, 566409).replace(tzinfo=pytz.utc)),
            preserve_default=False,
        ),
    ]
