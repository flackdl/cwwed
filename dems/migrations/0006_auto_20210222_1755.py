# Generated by Django 3.1.3 on 2021-02-22 17:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dems', '0005_auto_20210222_1743'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dem',
            name='path',
            field=models.CharField(max_length=1000),
        ),
        migrations.AlterUniqueTogether(
            name='dem',
            unique_together={('source', 'path')},
        ),
    ]
