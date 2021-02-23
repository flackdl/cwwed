import os
from urllib.parse import urlparse

from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField

"""
Digital Elevation Model (DEM) updates
"""


class DemSource(models.Model):
    name = models.CharField(max_length=200, unique=True)
    url = models.CharField(max_length=1000, unique=True, help_text='FTP scheme')

    def get_host(self):
        parsed = urlparse(self.url)
        return parsed.hostname

    def get_path(self):
        parsed = urlparse(self.url)
        return parsed.path

    def __str__(self):
        return self.name


class DemSourceLog(models.Model):
    source = models.ForeignKey(DemSource, on_delete=models.CASCADE)
    date_scanned = models.DateTimeField()
    dems_added = ArrayField(base_field=models.CharField(max_length=1000))
    dems_updated = ArrayField(base_field=models.CharField(max_length=1000))
    dems_removed = ArrayField(base_field=models.CharField(max_length=1000))

    class Meta:
        ordering = ('-date_scanned',)

    def __str__(self):
        return '{source} scanned {date} <added: {added}, updated: {updated}, removed: {removed}>'.format(
            source=self.source,
            date=self.date_scanned,
            added=len(self.dems_added),
            updated=len(self.dems_updated),
            removed=len(self.dems_removed),
        )


class Dem(models.Model):
    source = models.ForeignKey(DemSource, on_delete=models.CASCADE)
    path = models.CharField(max_length=1000)
    date_updated = models.DateTimeField()
    boundary = models.PolygonField(geography=True, null=True, blank=True)  # populated after creation
    resolution = models.FloatField(null=True, blank=True)  # populated after creation

    class Meta:
        unique_together = ('source', 'path')
        ordering = ('-date_updated',)

    def get_source_path(self):
        # full source path
        return os.path.join(self.source.get_path(), self.path)

    def get_url(self):
        return 'ftp://{}{}'.format(self.source.get_host(), os.path.join(self.source.get_host(), self.source.get_path(), self.path))

    @staticmethod
    def get_sub_path(dem_path: str, dem_source: DemSource):
        # strip out the source root path from dem path
        return dem_path.replace(dem_source.get_path(), '')

    def __str__(self):
        return self.path
