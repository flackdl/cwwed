import os
import re
import celery
import pytz
import requests
from ftplib import FTP
from urllib.parse import urlencode
from functools import cmp_to_key
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.gis.geos import Point
from lxml import etree
from typing import List
from io import BytesIO
from urllib import parse
from named_storms.data.decorators import register_factory
from named_storms import tasks
from named_storms.data.processors import ProcessorData, GenericFileProcessor
from named_storms import models as storm_models
from named_storms.models import CoveredDataProvider, NamedStorm, NamedStormCoveredData


class ProcessorBaseFactory:
    # "singleton" (class variable) which automatically gets populated from factory class decorators
    registered_factories = {}

    def _verify_registered(self):
        # verify this factory instance was registered properly
        if self.__class__ not in ProcessorBaseFactory.registered_factories.values():
            raise NotImplementedError('Processor factory must be registered through register_factory()')


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_CORE)
class ProcessorCoreFactory(ProcessorBaseFactory):

    _named_storm: NamedStorm = None
    _provider: CoveredDataProvider = None
    _verify_ssl = True
    _provider_url_parsed = None
    _named_storm_covered_data: NamedStormCoveredData = None

    def __init__(self, storm: NamedStorm, provider: CoveredDataProvider):
        self._named_storm = storm
        self._provider = provider
        self._provider_url_parsed = parse.urlparse(self._provider.url)
        self._named_storm_covered_data = self._named_storm.namedstormcovereddata_set.get(covered_data=self._provider.covered_data)

    def _processors_data(self) -> List[ProcessorData]:
        return [
            ProcessorData(
                named_storm_id=self._named_storm.id,
                provider_id=self._provider.id,
                url=self._provider.url,
                kwargs=self._processor_kwargs(),
            )
        ]

    def processors_data(self) -> List[ProcessorData]:
        self._verify_registered()
        return self._processors_data()

    @staticmethod
    def generic_filter(records: list):
        # if DEBUG return a small subset of randomized records
        if settings.DEBUG:
            from random import shuffle
            shuffle(records)
            return records[:10]
        return records

    def _processor_kwargs(self):
        return {}


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_USGS)
class USGSProcessorFactory(ProcessorCoreFactory):
    """
    USGS - STN Web Services
    https://stn.wim.usgs.gov/STNServices/Documentation/home

    REST API which allows you to select an "event" (hurricane) and crawl through various sensors and
    retrieve associated datasets.

    The usgs "event id" is stored in NamedStormCoveredDataProvider.external_storm_id
    """

    FILE_TYPE_DATA = 2
    # some non-data files end up being tagged as "data" files so try and exclude the known offenders
    EXCLUDED_EXTENSIONS = ['PNG', 'png', 'MOV', 'JPG', 'jpg', 'jpeg', 'pdf']

    deployment_types = []
    sensors = []

    def _processors_data(self) -> List[ProcessorData]:
        assert self._named_storm_covered_data.external_storm_id, 'USGS Processor Factor requires the external_storm_id to match their "Event ID"'
        processors_data = []

        # fetch deployment types
        deployment_types_req = requests.get('https://stn.wim.usgs.gov/STNServices/DeploymentTypes.json', timeout=10)
        deployment_types_req.raise_for_status()
        self.deployment_types = deployment_types_req.json()

        # fetch event sensors
        sensors_req = requests.get(
            'https://stn.wim.usgs.gov/STNServices/Events/{}/Instruments.json'.format(self._named_storm_covered_data.external_storm_id),
            timeout=10,
        )
        sensors_req.raise_for_status()
        self.sensors = sensors_req.json()

        # fetch event data files
        files_req = requests.get(
            'https://stn.wim.usgs.gov/STNServices/Events/{}/Files.json'.format(self._named_storm_covered_data.external_storm_id),
            timeout=10,
        )
        files_req.raise_for_status()
        files_json = files_req.json()

        # filter unique files
        files_json = self._filter_unique_files(files_json)

        # filter
        files_json = self.generic_filter(files_json)

        # build a list of data processors for all the files/sensors for this event
        for file in files_json:

            # skip files that don't have an associated "instrument_id"
            if not file.get('instrument_id'):
                continue
            # skip files that aren't "data" files
            if file['filetype_id'] != self.FILE_TYPE_DATA:
                continue
            # skip files where their sensors aren't in the valid list of deployment types
            if not self._is_valid_sensor_deployment_type(file):
                continue
            # skip files where their types are blacklisted
            if not self._is_valid_file(file):
                continue

            file_url = 'https://stn.wim.usgs.gov/STNServices/Files/{}/item'.format(file['file_id'])
            processors_data.append(ProcessorData(
                named_storm_id=self._named_storm.id,
                provider_id=self._provider.id,
                url=file_url,
                label=file['name'],
                group=self._sensor_deployment_type(file['instrument_id']),
                kwargs=self._processor_kwargs(),
            ))
            
        # include "High Water Mark" (non-time series data without the use of sensors)
        # e.g https://stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json?Event=312
        hwm_url = 'https://stn.wim.usgs.gov/STNServices/HWMs/FilteredHWMs.json?{}'.format(
            urlencode({'Event': self._named_storm_covered_data.external_storm_id})
        )
        processors_data.append(ProcessorData(
            named_storm_id=self._named_storm.id,
            provider_id=self._provider.id,
            url=hwm_url,
            label='hwm.csv',  # json data will be converted to csv in the processor
            group='HWM',
            # flag to convert json to csv
            kwargs={GenericFileProcessor.CONVERT_JSON_TO_CSV: True},
        ))

        return processors_data

    def _filter_unique_files(self, files: dict):
        """
        skip duplicates (and consider identical files with different extensions the same), i.e
          SCGEO14318_10684844_reprocessed_stormtide_unfiltered.nc
          SCGEO14318_10684844_reprocessed_stormtide_unfiltered.csv
        skip duplicates where there's a .csv extension prepended to an .nc extension, i.e
          FLSTL03732_1028516.csv
          FLSTL03732_1028516.csv.nc
        """
        results = []
        unique_names = set()
        # sort them so '.nc' files appear first
        files = self._sort_files(files)

        for file in files:
            # remove the redundant .csv middle extension which will correctly prevent a duplicate
            file['name'] = re.sub(r'.csv.nc$', '.nc', file['name'])

            # get file name without extension
            file_split = os.path.splitext(file['name'])
            file_prefix = file_split[0]

            # skip exact duplicates
            if file_prefix in unique_names:
                continue

            # add to unique names and final results
            unique_names.add(file_prefix)
            results.append(file)

        return results

    @staticmethod
    def _sort_files(files: dict):
        """
        Sort .nc files first (we're excluding duplicate files with different extensions and prefer NetCDF over CSV)
        """
        def _nc_sort(a, b):
            if a['name'].endswith('.nc') and b['name'].endswith('.nc'):
                return 0
            elif a['name'].endswith('.nc'):
                return -1
            return 1
        return sorted(files, key=cmp_to_key(_nc_sort))

    def _is_valid_file(self, file: dict) -> bool:
        ext = re.sub(r'^.*\.', '', file['name'])
        return ext not in self.EXCLUDED_EXTENSIONS

    def _is_valid_sensor_deployment_type(self, file: dict) -> bool:
        sensor = self._sensor(file['instrument_id'])
        return sensor.get('deployment_type_id') in [dt['deployment_type_id'] for dt in self.deployment_types]

    def _sensor(self, instrument_id) -> dict:
        for sensor in self.sensors:
            if sensor['instrument_id'] == instrument_id:
                return sensor
        raise Exception('Unknown instrument_id {}'.format(instrument_id))

    def _sensor_deployment_type(self, instrument_id) -> str:
        sensor = self._sensor(instrument_id)
        for deployment_type in self.deployment_types:
            if deployment_type['deployment_type_id'] == sensor['deployment_type_id']:
                return deployment_type['method']
        raise Exception('Could not find deployment type for instrument_id {}'.format(instrument_id))


class THREDDSCatalogBaseFactory(ProcessorCoreFactory):

    namespaces = {
        'catalog': 'http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0',
        'xlink': 'http://www.w3.org/1999/xlink',
    }

    def _catalog_ref_title(self, catalog_ref: etree.Element) -> str:
        """
        :return: title value for a particular catalogRef element
        """
        title_key = '{{{}}}title'.format(self.namespaces['xlink'])
        return catalog_ref.get(title_key)

    def _catalog_ref_href(self, catalog_ref: etree.Element) -> str:
        """
        :return: absolute value from "href" attribute for a particular catalogRef element
        """
        dir_path = os.path.dirname(self._provider.url)
        href_key = '{{{}}}href'.format(self.namespaces['xlink'])
        catalog_path = catalog_ref.get(href_key)
        return os.path.join(
            dir_path,
            parse.urlparse(catalog_path).path,
        )

    def _is_using_dataset(self, dataset: str) -> bool:
        return True

    def _catalog_ref_elements(self, catalog_url: str) -> List[etree.ElementTree]:
        """
        Fetches a catalog and returns all catalogRef elements from a catalog url
        """

        # fetch and parse the main catalog
        catalog_response = requests.get(catalog_url, verify=self._verify_ssl, timeout=10)
        catalog_response.raise_for_status()
        catalog = etree.parse(BytesIO(catalog_response.content))

        # return all catalogRef elements
        return catalog.xpath('//catalog:catalogRef', namespaces=self.namespaces)

    def _catalog_documents(self, catalog_urls) -> List[etree.ElementTree]:
        """
        Fetches the catalog urls in parallel via tasks.
        :param catalog_urls: list of catalog urls
        :return: list of lxml catalog elements
        """
        task_group = celery.group([tasks.fetch_url_task.s(url, self._verify_ssl) for url in catalog_urls])
        task_promise = task_group()
        catalogs = task_promise.get()
        catalogs = [etree.parse(BytesIO(s.encode())) for s in catalogs]
        return catalogs


class JPLProcessorBaseFactory(THREDDSCatalogBaseFactory):
    """
    JPL Factory (BASE)

    The datasets are two levels deep in the catalog:
        - year (i.e "2018")
        - day of year (i.e "123" for the 123rd day of the year)
    """

    def _catalog_ref_url(self, catalog_ref: etree.Element) -> str:
        """
        :return: absolute catalog url for a particular catalogRef element
        """
        return '{}://{}{}'.format(
            self._provider_url_parsed.scheme,
            self._provider_url_parsed.hostname,
            os.path.join(
                catalog_ref.get('ID'),
                'catalog.xml',
            )
        )

    def _filter_catalog_refs_by_year(self, catalog_refs: etree.ElementTree) -> List[etree.ElementTree]:
        """
        Filters a list of top level (i.e titled by "year") catalogRef's
        """
        results = []
        for ref in catalog_refs:
            # the "title" will be the year, i.e "2018"
            year = int(self._catalog_ref_title(ref))
            if year in [self._named_storm_covered_data.date_start.year, self._named_storm_covered_data.date_end.year]:
                results.append(ref)
        return results

    def _filter_catalog_refs_by_day(self, year: int, catalog_refs: etree.ElementTree) -> List[etree.ElementTree]:
        """
        Filters a list of 2nd level catalogRef's, titled by "day of year" (i.e "123" is the 123rd day of the year)
        :param year YYYY
        """
        results = []
        year_start_date = datetime(year, 1, 1).replace(tzinfo=pytz.utc)
        for ref in catalog_refs:
            # the "title" will be the day of the year, i.e "123"
            day_of_year = int(self._catalog_ref_title(ref))
            data_days_since_year_start_date = (self._named_storm_covered_data.date_start - year_start_date).days + 1
            data_days_since_year_end_date = (self._named_storm_covered_data.date_end - year_start_date).days + 1
            if data_days_since_year_end_date >= day_of_year >= data_days_since_year_start_date:
                results.append(ref)
        return results

    def _processors_data(self) -> List[ProcessorData]:
        dataset_paths = []
        processors_data = []

        # fetch and build first level catalog refs (i.e designated by year)
        catalog_ref_elements_year = self._catalog_ref_elements(self._provider.url)
        catalog_ref_elements_year = self._filter_catalog_refs_by_year(catalog_ref_elements_year)

        # fetch and build second level catalogs (i.e for day of the year)
        catalog_refs = []
        for ref_year in catalog_ref_elements_year:
            year = int(self._catalog_ref_title(ref_year))
            url = self._catalog_ref_url(ref_year)

            catalog_documents_day = self._catalog_documents([url])

            catalog_ref_elements_day = []
            for catalog in catalog_documents_day:
                catalog_ref_elements_day += catalog.xpath('//catalog:catalogRef', namespaces=self.namespaces)
            catalog_ref_elements_day = self._filter_catalog_refs_by_day(year, catalog_ref_elements_day)

            catalog_refs += catalog_ref_elements_day

        # build a list of actual URLs for each yearly catalog
        catalog_ref_urls_day = []
        for ref in catalog_refs:
            catalog_ref_urls_day.append(self._catalog_ref_url(ref))

        # build a list of relevant datasets for each catalog
        catalog_documents = self._catalog_documents(catalog_ref_urls_day)
        for catalog_document in catalog_documents:
            for dataset in catalog_document.xpath('//catalog:dataset', namespaces=self.namespaces):
                if self._is_using_dataset(dataset.get('name')):
                    dataset_paths.append(dataset.get('ID'))

        # filter datasets
        dataset_paths = self.generic_filter(dataset_paths)

        # build a list of processors for all the relevant datasets
        for dataset_path in dataset_paths:
            label = os.path.basename(dataset_path)
            url = '{}://{}/{}'.format(
                self._provider_url_parsed.scheme,
                self._provider_url_parsed.hostname,
                dataset_path,
            )
            folder = os.path.basename(os.path.dirname(url))
            processors_data.append(ProcessorData(
                named_storm_id=self._named_storm.id,
                provider_id=self._provider.id,
                url=url,
                label=label,
                group=folder,
                kwargs=self._processor_kwargs(),
            ))

        return processors_data


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_JPL_MET_OP_ASCAT_L2)
class JPLMetOpASCATL2ProcessorFactory(JPLProcessorBaseFactory):
    """
    JPL MetOp-A/B ASCAT Level 2
    [Meteorological Operational (MetOp)]
    https://podaac.jpl.nasa.gov/dataset/ASCATA-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT
    https://podaac.jpl.nasa.gov/dataset/ASCATB-L2-Coastal?ids=Measurement:Sensor&values=Ocean%20Winds:ASCAT
    http://projects.knmi.nl/scatterometer/publications/pdf/ASCAT_Product_Manual.pdf
    """

    def _processor_kwargs(self):
        # override the default latitude/longitude keys using processor kwargs
        return {
            'dimension_longitude': 'lon',
            'dimension_latitude': 'lat',
        }

    def _is_using_dataset(self, dataset: str) -> bool:
        # the files have the .gz extension but they're returned as uncompressed netcdf files
        return dataset.endswith('.nc.gz')


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_JPL_SMAP_L2B)
class JPLSMAPL2BProcessorFactory(JPLProcessorBaseFactory):
    """
    JPL SMAP Level 2B CAP Sea Surface Salinity
    https://podaac.jpl.nasa.gov/dataset/SMAP_JPL_L2B_SSS_CAP_V42?ids=Platform&values=SMAP
    """

    def _is_using_dataset(self, dataset: str) -> bool:
        return dataset.endswith('.h5')


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_JPL_QSCAT_L1C)
class JPLQSCATL1CProcessorFactoryFactory(JPLProcessorBaseFactory):
    """
    JPL Quikscat L1C
    Note: we're actually using version 2 even though version 1 is displayed on the main data access page.
    https://podaac.jpl.nasa.gov/dataset/QSCAT_L1C_NONSPINNING_SIGMA0_WINDS_V1?ids=ProcessingLevel:Platform&values=*1*:QUIKSCAT
    """
    # the numpy `dtype` is defined in the following example script:
    # ftp://podaac.jpl.nasa.gov/allData/quikscat/L1C/sw/Python/quikscat_l1c.py
    DATA_TYPE = [
        ('timestr', 'S21'), ('time', 'f8'), ('lon', 'f4'), ('lat', 'f4'),
        ('fp_start', 'i4'), ('fp_end', 'i4'), ('npts', 'i4'), ('s0', 'f4'),
        ('inc', 'f4'), ('azi', 'f4'), ('atten', 'f4'), ('beam', 'u1'),
        ('land', 'u1'), ('espd', 'f4'), ('edir', 'f4'), ('rspd', 'f4'),
        ('rdir', 'f4'),
    ]

    def _processor_kwargs(self):
        return {
            'data_type': self.DATA_TYPE,
        }

    def _is_using_dataset(self, dataset: str) -> bool:
        return dataset.endswith('.dat')


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_NDBC)
class NDBCProcessorFactory(THREDDSCatalogBaseFactory):
    """
    https://dods.ndbc.noaa.gov/
    The NDBC has a THREDDS catalog which includes datasets for each station where the station format is 5 characters, i.e "20cm4".
    The datasets inside each station includes historical data and real-time data (45 days).  There is no overlap.
        - Historical data is in the format "20cm4h2014.nc"
        - "Real-time" data is in the format "20cm4h9999.nc"
    NOTE: NDBC's SSL certs aren't validating, so let's just not verify.
    """
    RE_PATTERN = re.compile(r'^(?P<station>\w{5})\w(?P<year>\d{4})\.nc$')
    # number of days "real-time" data is stored separately from the timestamped files
    REALTIME_DAYS = 45
    # "real-time" year format of file
    REALTIME_YEAR = 9999

    _verify_ssl = False

    def _processors_data(self) -> List[ProcessorData]:
        dataset_paths = []
        processors_data = []

        # build catalogRefs and filter
        catalog_refs = self._catalog_ref_elements(self._provider.url)
        catalog_refs = self.generic_filter(catalog_refs)

        # build list of catalog urls
        catalog_urls = [self._catalog_ref_href(ref) for ref in catalog_refs]

        # build a list of relevant datasets for each station
        catalogs = self._catalog_documents(catalog_urls)
        for station in catalogs:
            for dataset in station.xpath('//catalog:dataset', namespaces=self.namespaces):
                if self._is_using_dataset(dataset.get('name')):
                    dataset_paths.append(dataset.get('urlPath'))

        # build a list of processors for all the relevant datasets
        for dataset_path in dataset_paths:
            label, _ = os.path.splitext(os.path.basename(dataset_path))  # remove extension since it's handled later
            url = '{}://{}/{}/{}'.format(
                self._provider_url_parsed.scheme,
                self._provider_url_parsed.hostname,
                'thredds/dodsC',
                dataset_path,
            )
            processors_data.append(ProcessorData(
                named_storm_id=self._named_storm.id,
                provider_id=self._provider.id,
                url=url,
                label=label,
                kwargs=self._processor_kwargs(),
            ))

        return processors_data

    def _is_using_dataset(self, dataset: str) -> bool:
        """
        Determines if we're using this dataset.
        Format: "20cm4h9999.nc" for real-time and "20cm4h2018.nc" for specific year
        """
        # build a map of years to datasets
        matched = self.RE_PATTERN.match(dataset)
        if matched:
            year = int(matched.group('year'))
            now = datetime.utcnow().replace(tzinfo=pytz.UTC)

            # determine if the start/end dates are within the REALTIME days
            within_realtime_start = (self._named_storm_covered_data.date_start + timedelta(days=self.REALTIME_DAYS)) >= now
            within_realtime_end = (self._named_storm_covered_data.date_end + timedelta(days=self.REALTIME_DAYS)) >= now

            # "real-time" dataset
            if year == self.REALTIME_YEAR:
                return any([within_realtime_start, within_realtime_end])
            # historical dataset
            else:
                # we'll never need the "historical" dataset if the whole date range is within the REALTIME days
                need_both = within_realtime_start and within_realtime_end
                return not need_both and year in [self._named_storm_covered_data.date_start.year, self._named_storm_covered_data.date_end.year]
        return False


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_TIDES_AND_CURRENTS)
class TidesAndCurrentsProcessorFactory(ProcessorCoreFactory):
    """
    REST APIs:
      - List of stations
          https://opendap.co-ops.nos.noaa.gov/axis/webservices/activestations/response.jsp?v=2&format=xml
      - Station data
          https://tidesandcurrents.noaa.gov/api

        - sample args:
            begin_date=20130101 10:00
            end_date=20130101 10:24
            station=8454000
            product=water_level
            datum=mllw (required for water_level product)
            units=metric
            time_zone=gmt
            application=cwwed
            format=xml
    Datum options: https://tidesandcurrents.noaa.gov/datum_options.html
    """
    API_STATIONS_URL = 'https://tidesandcurrents.noaa.gov/mdapi/latest/webapi/stations.json'
    API_DATA_URL = 'https://tidesandcurrents.noaa.gov/api/datagetter'
    DATUM = 'MLLW'  # required for water level
    FILE_TYPE = 'xml'
    DATE_FORMAT_STR = '%Y%m%d %H:%M'

    # products mapped via (api code name, name)
    # example of stations products: https://tidesandcurrents.noaa.gov/mdapi/v0.6/webapi/stations/1611400/products.json
    PRODUCT_WATER_LEVEL = ('water_level', 'Water Levels',)
    PRODUCT_METEOROLOGICAL_AIR_TEMPERATURE = ('air_temperature', 'Meteorological')
    PRODUCT_METEOROLOGICAL_AIR_PRESSURE = ('air_pressure', 'Meteorological')
    PRODUCT_METEOROLOGICAL_WIND = ('wind', 'Meteorological')
    PRODUCTS = [
        PRODUCT_WATER_LEVEL,
        PRODUCT_METEOROLOGICAL_AIR_TEMPERATURE,
        PRODUCT_METEOROLOGICAL_AIR_PRESSURE,
        PRODUCT_METEOROLOGICAL_WIND,
    ]

    def _processors_data(self) -> List[ProcessorData]:
        processors_data = []

        # fetch and parse the station listings
        stations_response = requests.get(self.API_STATIONS_URL, timeout=10)
        stations_response.raise_for_status()
        stations_json = stations_response.json()
        stations = stations_json['stations']

        # build a list of stations to collect data
        for station in stations:

            lat = station['lat']
            lng = station['lng']
            station_point = Point(x=lng, y=lat)

            # skip this station if it's outside our covered data's geo
            if not self._named_storm_covered_data.geo.contains(station_point):
                continue

            # get a list of products this station offers
            products_request = requests.get(station['products']['self'], timeout=10)
            if products_request.ok:
                station_products = [p['name'] for p in products_request.json()['products']]
            else:
                continue

            # build a list for each product that's available
            for product in self.PRODUCTS:

                # verify product "name" was added to the station's available products
                if product[1] not in station_products:
                    continue

                label = 'station-{}-{}'.format(station['id'], product[0])

                query_args = dict(
                    begin_date=self._named_storm_covered_data.date_start.strftime(self.DATE_FORMAT_STR),
                    end_date=self._named_storm_covered_data.date_end.strftime(self.DATE_FORMAT_STR),
                    station=station['id'],
                    product=product[0],
                    units='metric',
                    time_zone='gmt',
                    application='cwwed',
                    format=self.FILE_TYPE,
                )

                # PRODUCT_WATER_LEVEL only
                if product[0] == self.PRODUCT_WATER_LEVEL[0]:

                    # skip this station if it doesn't offer the right DATUM
                    datum_request = requests.get(station['datums']['self'], timeout=10)
                    if datum_request.ok:
                        if not [d for d in datum_request.json()['datums'] if d['name'] == self.DATUM]:
                            continue
                    else:
                        continue

                    # include "datum" in query args
                    query_args.update({
                        'datum': self.DATUM,
                    })

                    # include "datum" in label
                    label = '{}-{}'.format(label, self.DATUM)

                #
                # success - add station to list
                #

                url = '{}?{}'.format(self.API_DATA_URL, parse.urlencode(query_args))

                processors_data.append(ProcessorData(
                    named_storm_id=self._named_storm.id,
                    provider_id=self._provider.id,
                    url=url,
                    label='{}.{}'.format(label, self.FILE_TYPE),
                    kwargs=self._processor_kwargs(),
                    group=product[1],
                ))

        return processors_data


@register_factory(storm_models.PROCESSOR_DATA_FACTORY_NWM)
class NWMProcessorFactory(ProcessorCoreFactory):
    """
    National Water Model

    TODO - provider isn't fully prepared for CWWED transfer so we're arbitrarily grabbing a current/active directory (i.e today's data)

    Data is on an ftp server:
    Example:
        ftp://ftpprd.ncep.noaa.gov/pub/data/nccf/com/nwm/prod/nwm.20180924/analysis_assim/nwm.t00z.analysis_assim.channel_rt.tm00.conus.nc
    We mostly just want "tm02" files (time minus 2 hour files, valid two hours before cycle time)
    """
    PRODUCT_TIME_SLICE = 'usgs_timeslices'
    PRODUCT_ANALYSIS_ASSIM = 'analysis_assim'
    PRODUCT_FORCING_ANALYSIS_ASSIM = 'forcing_analysis_assim'
    PRODUCT_DIRECTORIES = [PRODUCT_TIME_SLICE, PRODUCT_ANALYSIS_ASSIM, PRODUCT_FORCING_ANALYSIS_ASSIM]

    def _processors_data(self) -> List[ProcessorData]:
        processors_data = []
        ftp = FTP(self._provider_url_parsed.hostname, timeout=20)
        ftp.login()
        base_path = self._provider_url_parsed.path
        directory_dates = ftp.nlst(base_path)
        if directory_dates:
            base_path = directory_dates[-1]  # arbitrarily choosing the most recent date in the interim
            for directory_product in ftp.nlst(base_path):
                if os.path.basename(directory_product) in self.PRODUCT_DIRECTORIES:
                    files = ftp.nlst(directory_product)
                    for file in files:
                        # we only want tm02 files ("time minus 2 hour files, valid two hours before cycle time)
                        if os.path.basename(directory_product) != self.PRODUCT_TIME_SLICE and not os.path.basename(file).startswith('nwm.t02z.'):
                            continue
                        processors_data.append(ProcessorData(
                            named_storm_id=self._named_storm.id,
                            provider_id=self._provider.id,
                            url='ftp://{}{}'.format(self._provider_url_parsed.hostname, file),
                            label=os.path.basename(file),
                            kwargs=self._processor_kwargs(),
                            group=os.path.basename(directory_product),
                        ))

        # filter
        processors_data = self.generic_filter(processors_data)

        return processors_data
