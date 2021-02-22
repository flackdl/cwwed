from django.contrib.postgres.fields import ArrayField
from django.db import models

"""
Digital Elevation Model (DEM) Updates
"""


class DemSource(models.Model):
    name = models.CharField(max_length=200, unique=True)
    url = models.CharField(max_length=1000, unique=True, help_text='ftp scheme')

    def __str__(self):
        return self.name


class DemSourceLog(models.Model):
    source = models.ForeignKey(DemSource, on_delete=models.CASCADE)
    date_scanned = models.DateTimeField()
    dems_added = ArrayField(base_field=models.CharField(max_length=1000))
    dems_updated = ArrayField(base_field=models.CharField(max_length=1000))
    dems_removed = ArrayField(base_field=models.CharField(max_length=1000))

    def __str__(self):
        return '{} <{}>'.format(self.source, self.date_scanned)


class Dem(models.Model):
    source = models.ForeignKey(DemSource, on_delete=models.CASCADE)
    path = models.CharField(max_length=1000, unique=True)
    date_updated = models.DateTimeField()

    def __str__(self):
        return self.path
