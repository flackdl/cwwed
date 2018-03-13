from django.contrib.gis.db import models

PROCESSOR_DATA_TYPE_SEQUENCE = 'sequence'
PROCESSOR_DATA_TYPE_GRID = 'grid'
PROCESSOR_DATA_TYPE_CHOICES = (
    PROCESSOR_DATA_TYPE_SEQUENCE,
    PROCESSOR_DATA_TYPE_GRID,
)

PROCESSOR_DATA_SOURCE_DAP = 'dap'
PROCESSOR_DATA_SOURCE_NDBC = 'ndbc'  # National Data Buoy Center - https://dods.ndbc.noaa.gov/
PROCESSOR_DATA_SOURCE_CHOICES = (
    PROCESSOR_DATA_SOURCE_DAP,
    PROCESSOR_DATA_SOURCE_NDBC,
)


class DataProviderProcessor(models.Model):
    name = models.CharField(max_length=200, choices=zip(PROCESSOR_DATA_SOURCE_CHOICES, PROCESSOR_DATA_SOURCE_CHOICES))

    def __str__(self):
        return self.name


class NamedStorm(models.Model):
    covered_data = models.ManyToManyField(
        to='CoveredData',
        through='NamedStormCoveredData',
    )
    name = models.CharField(max_length=50, unique=True)  # i.e "Harvey"
    geo = models.GeometryField(geography=True)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CoveredData(models.Model):
    name = models.CharField(max_length=500, unique=True)  # i.e "Global Forecast System"
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class CoveredDataProvider(models.Model):
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    processor = models.ForeignKey(DataProviderProcessor, on_delete=models.CASCADE)
    name = models.CharField(max_length=500)  # i.e  "NOAA/NCEP"
    url = models.CharField(max_length=500)
    data_type = models.CharField(max_length=200, choices=zip(PROCESSOR_DATA_TYPE_CHOICES, PROCESSOR_DATA_TYPE_CHOICES))
    active = models.BooleanField(default=True)

    def __str__(self):
        return '{} // {}'.format(self.name, self.covered_data)


class NamedStormCoveredData(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    geo = models.GeometryField(geography=True)

    def __str__(self):
        return '{} // {}'.format(self.named_storm, self.covered_data)
