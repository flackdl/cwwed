from django.contrib.gis.db import models


class NamedStorm(models.Model):
    name = models.CharField(max_length=50, unique=True)  # i.e "Harvey"
    geo = models.GeometryField(geography=True)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()

    def __str__(self):
        return self.name


class NamedStormCoveredData(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    name = models.CharField(max_length=500, unique=True)  # i.e "Global Forecast System"

    def __str__(self):
        return '{} ({})'.format(self.name, self.named_storm)


class NamedStormCoveredDataProvider(models.Model):
    covered_data = models.ForeignKey(NamedStormCoveredData, on_delete=models.CASCADE)
    name = models.CharField(max_length=500)  # i.e  NOAA/ERDDAP
    source = models.CharField(max_length=500)  # url endpoint
    provider_class = models.CharField(max_length=150)

    def __str__(self):
        return self.name
