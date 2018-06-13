from django.contrib.gis.db import models


# data factories
PROCESSOR_DATA_FACTORY_ERDDAP = 'ERDDAP'  # factory for any ERDDAP provider
PROCESSOR_DATA_FACTORY_NDBC = 'NDBC'  # National Data Buoy Center - https://dods.ndbc.noaa.gov/
PROCESSOR_DATA_FACTORY_USGS = 'USGS'  # USGS - https://stn.wim.usgs.gov/STNServices/Documentation/home
PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C = 'JPL_QSCAT_L1C'  # JPL - https://podaac.jpl.nasa.gov/dataset/QSCAT_L1C_NONSPINNING_SIGMA0_WINDS_V1

# data factory choices
PROCESSOR_DATA_FACTORY_CHOICES = (
    PROCESSOR_DATA_FACTORY_ERDDAP,
    PROCESSOR_DATA_FACTORY_NDBC,
    PROCESSOR_DATA_FACTORY_USGS,
    PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C,
)

# data sources
PROCESSOR_DATA_SOURCE_FILE_GENERIC = 'FILE-GENERIC'
PROCESSOR_DATA_SOURCE_FILE_BINARY = 'FILE-BINARY'
PROCESSOR_DATA_SOURCE_DAP = 'DAP'

# data source choices
PROCESSOR_DATA_SOURCE_CHOICES = (
    PROCESSOR_DATA_SOURCE_FILE_GENERIC,
    PROCESSOR_DATA_SOURCE_FILE_BINARY,
    PROCESSOR_DATA_SOURCE_DAP,
)


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
    processor_factory = models.CharField(max_length=50, choices=zip(PROCESSOR_DATA_FACTORY_CHOICES, PROCESSOR_DATA_FACTORY_CHOICES))
    processor_source = models.CharField(max_length=50, choices=zip(PROCESSOR_DATA_SOURCE_CHOICES, PROCESSOR_DATA_SOURCE_CHOICES))
    name = models.CharField(max_length=500)  # i.e  "NOAA/NCEP"
    url = models.CharField(max_length=500)
    active = models.BooleanField(default=True)

    def __str__(self):
        return '{} // {}'.format(self.name, self.covered_data)


class NamedStormCoveredData(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    date_start = models.DateTimeField()
    date_end = models.DateTimeField()
    geo = models.GeometryField(geography=True)
    external_storm_id = models.CharField(max_length=80, blank=True)  # an id for a storm in an external system

    def __str__(self):
        return '{} // {}'.format(self.named_storm, self.covered_data)


class NamedStormCoveredDataLog(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    provider = models.ForeignKey(CoveredDataProvider, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)  # whether the covered data collection was a success
    snapshot = models.TextField(blank=True)  # the path to the covered data snapshot
    exception = models.TextField(blank=True)  # any error message during a failed collection

    def __str__(self):
        if self.success:
            return self.snapshot
        return 'Error:: {}: {}'.format(self.named_storm, self.covered_data)


class NSEM(models.Model):
    """
    Named Storm Event Model
    """
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    date_returned = models.DateTimeField(null=True)  # manually set once the model output is returned
    covered_data_snapshot = models.TextField(blank=True)  # path to the covered data snapshot
    model_output_snapshot = models.TextField(blank=True)  # path to the model output snapshot
    model_output_snapshot_extracted = models.BooleanField(default=False)  # whether the output has been extracted to file storage

    def __str__(self):
        return 'NSEM: {}'.format(self.named_storm)
