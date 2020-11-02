from datetime import datetime
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models import Index
from django.utils import timezone
from django.contrib.postgres import fields


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
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_start']

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
        # query last successful log by ordering by storm/data/date_completed using "distinct" on storm/data
        log = named_storm.namedstormcovereddatalog_set.filter(success=True, covered_data=covered_data)
        log = log.order_by('named_storm', 'covered_data', '-date_completed').distinct('named_storm', 'covered_data')
        if log.exists():
            return log.get()
        return None


class NamedStormCoveredDataLog(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    covered_data = models.ForeignKey(CoveredData, on_delete=models.CASCADE)
    provider = models.ForeignKey(CoveredDataProvider, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True, blank=True)  # manually set once data has been archived in object storage
    success = models.BooleanField(default=False)  # whether the covered data collection was a success
    snapshot = models.TextField(blank=True)  # the path to the covered data snapshot
    exception = models.TextField(blank=True)  # any error message during a failed collection

    def __str__(self):
        if self.success:
            return '{}: {}'.format(self.date_created.isoformat(), self.snapshot)
        return 'Error:: {}: {}'.format(self.named_storm, self.covered_data)


class NamedStormCoveredDataSnapshot(models.Model):
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    date_requested = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True, blank=True)  # manually set once snapshot is complete
    path = models.CharField(max_length=500, blank=True)  # path (prefix) in object storage
    covered_data_logs = models.ManyToManyField(NamedStormCoveredDataLog, blank=True)  # list of covered data logs gets populated after creation

    def get_covered_data_storage_url(self):
        from cwwed.storage_backends import S3ObjectStoragePrivate  # import locally to prevent circular references
        storage = S3ObjectStoragePrivate()
        if self.date_completed and self.path:
            return storage.storage_url(self.path)
        return None

    def __str__(self):
        return '{} <{}>'.format(self.named_storm, self.id)


class NsemPsa(models.Model):
    """
    Named Storm Event Model
    """
    named_storm = models.ForeignKey(NamedStorm, on_delete=models.CASCADE)
    date_created = models.DateTimeField(auto_now_add=True)
    covered_data_snapshot = models.ForeignKey(NamedStormCoveredDataSnapshot, on_delete=models.PROTECT)
    manifest = fields.JSONField()  # defines the uploaded psa dataset files and variables
    path = models.TextField()  # path to the psa
    extracted = models.BooleanField(default=False)  # whether the psa has been extracted to file storage
    date_validation = models.DateTimeField(null=True, blank=True)  # manually set once the psa validation was attempted
    validated = models.BooleanField(default=False)  # whether the supplied psa was validated
    validation_exceptions = fields.JSONField(default=dict, blank=True)  # any specific exceptions when validating the psa
    processed = models.BooleanField(default=False)  # whether the psa was fully ingested/processed
    date_processed = models.DateTimeField(null=True, blank=True)  # manually set once the psa is processed
    dates = fields.ArrayField(base_field=models.DateTimeField(), default=list)  # type: list

    def __str__(self):
        return '{} ({})'.format(self.named_storm, self.id)

    @classmethod
    def get_last_valid_psa(cls, storm_id: int):
        qs = cls.objects.filter(
            named_storm__id=storm_id,
            extracted=True,
            validated=True,
            processed=True
        )
        qs = qs.order_by('-date_created')
        return qs.first()


class NsemPsaManifestDataset(models.Model):
    nsem = models.ForeignKey(NsemPsa, on_delete=models.CASCADE)
    path = models.CharField(max_length=200)
    variables = fields.ArrayField(base_field=models.CharField(max_length=20))  # type: list
    structured = models.BooleanField(default=True, help_text='Whether the dataset has a structured grid')
    topology_name = models.CharField(max_length=50, default='element', help_text='Variable name for unstructured mesh connectivity')

    def __str__(self):
        return '{}: {}'.format(self.nsem, self.path)


class NsemPsaVariable(models.Model):
    DATA_TYPE_TIME_SERIES = 'time-series'
    DATA_TYPE_MAX_VALUES = 'max-values'

    GEO_TYPE_POLYGON = 'polygon'
    GEO_TYPE_WIND_BARB = 'wind-barb'

    UNITS_METERS = 'm'
    UNITS_METERS_PER_SECOND = 'm/s'
    UNITS_DEGREES = 'degrees'

    ELEMENT_WATER = 'water'
    ELEMENT_WIND = 'wind'

    ELEMENTS = (
        ELEMENT_WATER,
        ELEMENT_WIND,
    )

    DATA_TYPES = (
        DATA_TYPE_TIME_SERIES,
        DATA_TYPE_MAX_VALUES,
    )

    UNITS = (
        UNITS_METERS_PER_SECOND,
        UNITS_METERS,
        UNITS_DEGREES,
    )

    GEO_TYPES = (
        GEO_TYPE_POLYGON,
        GEO_TYPE_WIND_BARB,
    )

    VARIABLE_WATER_LEVEL = 'Water Level'
    VARIABLE_WAVE_HEIGHT = 'Wave Height'
    VARIABLE_WIND_SPEED = 'Wind Speed'
    VARIABLE_WIND_GUST = 'Wind Gust'
    VARIABLE_WIND_BARBS = 'Wind Barbs'

    VARIABLE_DATASET_WATER_LEVEL = 'water_level'
    VARIABLE_DATASET_WAVE_HEIGHT = 'wave_height'
    VARIABLE_DATASET_WIND_SPEED = 'wind_speed'
    VARIABLE_DATASET_WIND_DIRECTION = 'wind_direction'
    VARIABLE_DATASET_WIND_GUST = 'wind_gust'
    VARIABLE_DATASET_WATER_LEVEL_MAX = 'water_level_max'

    VARIABLE_NAMES = (
        VARIABLE_WATER_LEVEL,
        VARIABLE_WAVE_HEIGHT,
        VARIABLE_WIND_SPEED,
        VARIABLE_WIND_GUST,
        VARIABLE_WIND_BARBS,
    )

    VARIABLE_DATASETS = (
        VARIABLE_DATASET_WATER_LEVEL,
        VARIABLE_DATASET_WATER_LEVEL_MAX,
        VARIABLE_DATASET_WAVE_HEIGHT,
        VARIABLE_DATASET_WIND_SPEED,
        VARIABLE_DATASET_WIND_DIRECTION,
        VARIABLE_DATASET_WIND_GUST,
    )

    VARIABLES = {
        VARIABLE_DATASET_WATER_LEVEL: {
            'display_name': VARIABLE_WATER_LEVEL,
            'units': UNITS_METERS,
            'geo_type': GEO_TYPE_POLYGON,
            'data_type': DATA_TYPE_TIME_SERIES,
            'element_type': ELEMENT_WATER,
            'auto_displayed': True,
        },
        VARIABLE_DATASET_WATER_LEVEL_MAX: {
            'display_name': VARIABLE_WATER_LEVEL,
            'units': UNITS_METERS,
            'geo_type': GEO_TYPE_POLYGON,
            'data_type': DATA_TYPE_MAX_VALUES,
            'element_type': ELEMENT_WATER,
            'auto_displayed': False,
        },
        VARIABLE_DATASET_WAVE_HEIGHT: {
            'display_name': VARIABLE_WAVE_HEIGHT,
            'units': UNITS_METERS,
            'geo_type': GEO_TYPE_POLYGON,
            'data_type': DATA_TYPE_TIME_SERIES,
            'element_type': ELEMENT_WATER,
            'auto_displayed': True,
        },
        VARIABLE_DATASET_WIND_SPEED: {
            'display_name': VARIABLE_WIND_SPEED,
            'units': UNITS_METERS_PER_SECOND,
            'geo_type': GEO_TYPE_POLYGON,
            'data_type': DATA_TYPE_TIME_SERIES,
            'element_type': ELEMENT_WIND,
            'auto_displayed': True,
        },
        VARIABLE_DATASET_WIND_GUST: {
            'display_name': VARIABLE_WIND_GUST,
            'units': UNITS_METERS_PER_SECOND,
            'geo_type': GEO_TYPE_POLYGON,
            'data_type': DATA_TYPE_TIME_SERIES,
            'element_type': ELEMENT_WIND,
            'auto_displayed': False,
        },
        VARIABLE_DATASET_WIND_DIRECTION: {
            'display_name': VARIABLE_WIND_BARBS,
            'units': UNITS_DEGREES,
            'geo_type': GEO_TYPE_WIND_BARB,
            'data_type': DATA_TYPE_TIME_SERIES,
            'element_type': ELEMENT_WIND,
            'auto_displayed': False,
        },
    }

    nsem = models.ForeignKey(NsemPsa, on_delete=models.CASCADE)
    name = models.CharField(max_length=50, choices=zip(VARIABLE_DATASETS, VARIABLE_DATASETS))  # i.e "water_level"
    color_bar = fields.JSONField(default=dict, blank=True)  # a list of 2-tuples, i.e [(.5, '#2e2e2e'),]
    auto_displayed = models.BooleanField(default=False)
    display_name = models.CharField(max_length=50, choices=zip(VARIABLE_NAMES, VARIABLE_NAMES))  # i.e "Water Level"
    geo_type = models.CharField(choices=zip(GEO_TYPES, GEO_TYPES), max_length=20)  # i.e "polygon"
    data_type = models.CharField(choices=zip(DATA_TYPES, DATA_TYPES), max_length=20)  # i.e "time-series"
    element_type = models.CharField(choices=zip(ELEMENTS, ELEMENTS), max_length=20)  # i.e "water"
    units = models.CharField(choices=zip(UNITS, UNITS), max_length=20)  # i.e "m/s"

    class Meta:
        unique_together = ('nsem', 'name')
        ordering = ['name']

    def save(self, **kwargs):
        # automatically define display name
        self.display_name = self.get_attribute('display_name')

        # validate variable attributes
        assert self.geo_type == self.get_attribute('geo_type'), 'improper attribute value'
        assert self.data_type == self.get_attribute('data_type'), 'improper attribute value'
        assert self.element_type == self.get_attribute('element_type'), 'improper attribute value'
        assert self.units == self.get_attribute('units'), 'improper attribute value'

        return super().save(**kwargs)

    def get_attribute(self, attribute: str):
        return NsemPsaVariable.get_variable_attribute(self.name, attribute)

    @classmethod
    def get_time_series_variables(cls):
        return [name for name, v in cls.VARIABLES.items() if v['data_type'] == cls.DATA_TYPE_TIME_SERIES]

    @classmethod
    def get_variable_attribute(cls, variable, attribute: str):
        assert variable in cls.VARIABLES, 'unknown variable "{}"'.format(variable)
        assert attribute in cls.VARIABLES[variable], 'unknown attribute "{}"'.format(attribute)
        return cls.VARIABLES[variable][attribute]

    def __str__(self):
        return self.name


class NsemPsaData(models.Model):
    nsem_psa_variable = models.ForeignKey(NsemPsaVariable, on_delete=models.CASCADE)
    point = models.PointField(geography=True)
    date = models.DateTimeField(null=True, blank=True)  # note: variable data types of "max-values" will have empty date values
    value = models.FloatField()

    def __str__(self):
        return '{} <data>'.format(self.nsem_psa_variable)

    class Meta:
        indexes = [
            Index(fields=['nsem_psa_variable', 'date', 'point']),
        ]


class NsemPsaContour(models.Model):
    nsem_psa_variable = models.ForeignKey(NsemPsaVariable, on_delete=models.CASCADE)
    date = models.DateTimeField(null=True, blank=True)  # note: variable data types of "max-values" will have empty date values
    geo = models.GeometryField(geography=True)
    value = models.FloatField()
    color = models.CharField(max_length=7, blank=True)  # rgb hex, i.e "#ffffff"

    def __str__(self):
        return '{} <contour>'.format(self.nsem_psa_variable)

    class Meta:
        indexes = [
            Index(fields=['nsem_psa_variable', 'date', 'value']),
        ]


class NsemPsaUserExport(models.Model):
    FORMAT_NETCDF = 'netcdf'
    FORMAT_SHAPEFILE = 'shapefile'
    FORMAT_GEOJSON = 'geojson'
    FORMAT_KML = 'kml'
    FORMAT_CSV = 'csv'
    FORMAT_CHOICES = (
        (FORMAT_NETCDF, FORMAT_NETCDF),
        (FORMAT_SHAPEFILE, FORMAT_SHAPEFILE),
        (FORMAT_GEOJSON, FORMAT_GEOJSON),
        (FORMAT_KML, FORMAT_KML),
        (FORMAT_CSV, FORMAT_CSV),
    )

    nsem = models.ForeignKey(NsemPsa, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    url = models.CharField(max_length=1500, null=True, blank=True)  # signed download url
    format = models.CharField(max_length=30, choices=FORMAT_CHOICES)
    bbox = models.GeometryField(geography=True)
    date_filter = models.DateTimeField(null=True, blank=True)  # date to filter export against
    date_created = models.DateTimeField(auto_now_add=True)
    date_completed = models.DateTimeField(null=True, blank=True)
    date_expires = models.DateTimeField(null=True, blank=True)
