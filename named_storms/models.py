from datetime import datetime
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


# data factories
PROCESSOR_DATA_FACTORY_CORE = 'CORE'  # core factory
PROCESSOR_DATA_FACTORY_ERDDAP = 'ERDDAP'  # any ERDDAP provider
PROCESSOR_DATA_FACTORY_NDBC = 'NDBC'  # National Data Buoy Center - https://dods.ndbc.noaa.gov/
PROCESSOR_DATA_FACTORY_USGS = 'USGS'  # USGS - https://stn.wim.usgs.gov/STNServices/Documentation/home
PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C = 'JPL_QSCAT_L1C'  # JPL - https://podaac.jpl.nasa.gov/dataset/QSCAT_L1C_NONSPINNING_SIGMA0_WINDS_V1
PROCESSOR_DATA_FACTORY_JPL_SMAP_L2B = 'JPL_SMAP_L2B'  # JPL - https://podaac.jpl.nasa.gov/dataset/SMAP_JPL_L2B_SSS_CAP_V4?ids=Measurement:ProcessingLevel&values=Ocean%20Winds:*2*
# https://podaac.jpl.nasa.gov/dataset/ASCATB-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT
# https://podaac.jpl.nasa.gov/dataset/ASCATA-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT
PROCESSOR_DATA_FACTORY_JPL_MET_OP_ASCAT_L2 = 'JPL_MET_OP_ASCAT_L2'
PROCESSOR_DATA_FACTORY_TIDES_AND_CURRENTS = 'TIDES_AND_CURRENTS'  # https://tidesandcurrents.noaa.gov/api/
PROCESSOR_DATA_FACTORY_NWM = 'NATIONAL_WATER_MODEL'  # http://nomads.ncep.noaa.gov/pub/data/nccf/com/nwm/prod


# data factory choices
PROCESSOR_DATA_FACTORY_CHOICES = (
    PROCESSOR_DATA_FACTORY_CORE,
    PROCESSOR_DATA_FACTORY_NDBC,
    PROCESSOR_DATA_FACTORY_USGS,
    PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C,
    PROCESSOR_DATA_FACTORY_JPL_SMAP_L2B,
    PROCESSOR_DATA_FACTORY_JPL_MET_OP_ASCAT_L2,
    PROCESSOR_DATA_FACTORY_TIDES_AND_CURRENTS,
    PROCESSOR_DATA_FACTORY_NWM,
)

# data sources
PROCESSOR_DATA_SOURCE_FILE_GENERIC = 'FILE-GENERIC'
PROCESSOR_DATA_SOURCE_FILE_BINARY = 'FILE-BINARY'
PROCESSOR_DATA_SOURCE_DAP = 'DAP'
PROCESSOR_DATA_SOURCE_FILE_HDF = 'HDF'

# data source choices
PROCESSOR_DATA_SOURCE_CHOICES = (
    PROCESSOR_DATA_SOURCE_FILE_GENERIC,
    PROCESSOR_DATA_SOURCE_FILE_BINARY,
    PROCESSOR_DATA_SOURCE_DAP,
    PROCESSOR_DATA_SOURCE_FILE_HDF,
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
    url = models.CharField(max_length=5000, blank=True, help_text='Product URL for this dataset')

    def __str__(self):
        return self.name


class CoveredDataProvider(models.Model):
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    processor_factory = models.CharField(max_length=50, choices=zip(PROCESSOR_DATA_FACTORY_CHOICES, PROCESSOR_DATA_FACTORY_CHOICES), help_text='Optionally specify a custom processor factory')
    processor_source = models.CharField(max_length=50, choices=zip(PROCESSOR_DATA_SOURCE_CHOICES, PROCESSOR_DATA_SOURCE_CHOICES))
    name = models.CharField(max_length=500)  # i.e  "NOAA/NCEP"
    url = models.CharField(max_length=5000)
    active = models.BooleanField(default=True)
    # some datasets define their time stamp epochs using non-unix epochs so allow them to define it themselves
    epoch_datetime = models.DateTimeField(default=datetime(1970, 1, 1, tzinfo=timezone.utc))

    def __str__(self):
        return self.name


class NamedStormCoveredData(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    date_start = models.DateTimeField(blank=True, null=True)  # optionally enforced in custom validation
    date_end = models.DateTimeField(blank=True, null=True)  # optionally enforced in custom validation
    dates_required = models.BooleanField(default=True)
    geo = models.GeometryField(geography=True)
    external_storm_id = models.CharField(max_length=80, blank=True)  # an id for a storm in an external system
    date_collected = models.DateField(blank=True, null=True)   # indicates last collection date, operating as a switch to recollect

    def __str__(self):
        return '{}: {}'.format(self.named_storm, self.covered_data)

    def clean(self):
        if self.dates_required and not all([self.date_start, self.date_end]):
            raise ValidationError('Start and End dates are required')
        return super().clean()

    @staticmethod
    def last_successful_log(named_storm: NamedStorm, covered_data: CoveredData):
        """
        :return: Last successful covered data log for a particular storm
        :rtype named_storm.models.NamedStormCoveredDataLog
        """
        # query last successful log by ordering by storm/data/date using "distinct" on storm/data
        log = named_storm.namedstormcovereddatalog_set.filter(success=True, covered_data=covered_data)
        log = log.order_by('named_storm', 'covered_data', '-date').distinct('named_storm', 'covered_data')
        if log.exists():
            return log.get()
        return None


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
            return '{}: {}'.format(self.date.isoformat(), self.snapshot)
        return 'Error:: {}: {}'.format(self.named_storm, self.covered_data)


class NSEM(models.Model):
    """
    Named Storm Event Model
    """
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    date_returned = models.DateTimeField(null=True, blank=True)  # manually set once the model output is returned
    covered_data_snapshot = models.TextField(blank=True)  # path to the covered data snapshot
    covered_data_logs = models.ManyToManyField(NamedStormCoveredDataLog, blank=True)  # list of logs going into the snapshot
    model_output_snapshot = models.TextField(blank=True)  # path to the model output snapshot
    model_output_snapshot_extracted = models.BooleanField(default=False)  # whether the output has been extracted to file storage

    def __str__(self):
        return str(self.named_storm)


class NsemPsa(models.Model):
    nsem = models.ForeignKey(NSEM, on_delete=models.CASCADE)
    variable = models.CharField(max_length=50)  # i.e "water_level"
    date = models.DateTimeField()
    geo = models.MultiPolygonField(geography=True)
    value = models.FloatField()
    color = models.CharField(max_length=7)  # rgb
