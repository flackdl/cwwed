import ssl
import os
import errno
import logging
import xmltodict
from typing import List
import requests
from urllib import parse
from django.conf import settings
from pydap.client import open_url
from pydap.model import DatasetType
from requests import HTTPError
from named_storms.models import NamedStormCoveredDataProvider


class DataRequest:
    url: str = None
    response_code: int = None
    output_path: str = None
    success: bool = None

    def __init__(self, url):
        self.url = url


class OpenDapProcessor:
    DEFAULT_DIMENSION_TIME = 'time'
    DEFAULT_DIMENSION_LATITUDE = 'latitude'
    DEFAULT_DIMENSION_LONGITUDE = 'longitude'
    DEFAULT_DIMENSIONS = {
        DEFAULT_DIMENSION_TIME,
        DEFAULT_DIMENSION_LATITUDE,
        DEFAULT_DIMENSION_LONGITUDE,
    }
    dataset: DatasetType = None
    provider: NamedStormCoveredDataProvider = None
    response_type: str = 'nc'
    response_code: int = None
    data_requests: List[DataRequest] = None

    _variables: List[str] = None
    _time_start: float = None
    _time_end: float = None
    _lat_start: float = None
    _lat_end: float = None
    _lng_start: float = None
    _lng_end: float = None

    def __init__(self, provider: NamedStormCoveredDataProvider):
        self.provider = provider
        self.data_requests = self._data_requests()

    def fetch(self):
        try:
            self._fetch()
        except HTTPError as e:
            logging.warning('HTTPError: %s' % str(e))
        except Exception as e:
            logging.warning('Exception: %s' % str(e))

    def is_success(self):
        return all([r.success for r in self.data_requests])

    def _data_requests(self):
        return [
            DataRequest(
                url=parse.unquote('{}.{}?{}'.format(self.provider.url, self.response_type, self._build_query()))
            )
        ]

    def _fetch(self):

        for data_request in self.data_requests:

            # fetch data
            response = requests.get(data_request.url, stream=True)

            data_request.response_code = response.status_code
            response.raise_for_status()

            # create a directory to house the storm's covered data
            path = self._create_directory('{}/{}'.format(
                settings.COVERED_DATA_CACHE_DIR,
                self.provider.covered_data.named_storm,
            ))

            # store output
            data_request.output_path = '{}/{}.{}'.format(
                path,
                self.provider.covered_data.name,
                self.response_type,
            )
            with open(data_request.output_path, 'wb') as fd:
                # stream the content so it's more efficient
                for block in response.iter_content(chunk_size=1024):
                    fd.write(block)

            data_request.success = response.ok

    def _build_query(self) -> str:

        self.dataset = open_url(self.provider.url)
        variables = self._all_variables()

        self._verify_dimensions(variables)

        # remove dimensions from variables
        self._variables = list(set(variables).difference(self.DEFAULT_DIMENSIONS))

        # use the covered data start/end dates for constraints
        self._time_start = self.provider.covered_data.date_start.timestamp()
        self._time_end = self.provider.covered_data.date_end.timestamp()

        # covered data boundaries
        storm_extent = self._covered_data_extent()

        # lat range
        self._lat_start = storm_extent[1]
        self._lat_end = storm_extent[3]

        # lng range
        self._lng_start = storm_extent[0]
        self._lng_end = storm_extent[2]

        return self._query()

    def _grid_constraint_indexes(self, dimension: str, start: float, end: float) -> tuple:
        # find the index range for our constraint values

        values = self.dataset[dimension][:].data.tolist()  # convert numpy array to list

        # find the the index range
        idx_start = next(idx for idx, v in enumerate(values) if v >= start)
        idx_end = next(idx for idx, v in enumerate(values) if v >= end)

        return idx_start, idx_end

    def _covered_data_extent(self) -> tuple:
        # extent/boundaries of covered data
        # i.e (-97.55859375, 28.23486328125, -91.0107421875, 33.28857421875)
        extent = self.provider.covered_data.geo.extent
        # TODO - we can't assume it's always in this format... must read metadata
        # however, we need to convert lng to "degrees_east" format (i.e 0-360)
        # i.e (262.44, 28.23486328125, 268.98, 33.28857421875)
        extent = (
            extent[0] if extent[0] > 0 else 360 + extent[0],  # lng
            extent[1],                                        # lat
            extent[2] if extent[2] > 0 else 360 + extent[2],  # lng
            extent[3],                                        # lat
        )
        return extent

    def _verify_dimensions(self, variables):
        if not self.DEFAULT_DIMENSIONS.issubset(variables):
            raise Exception('missing expected dimensions')

    def _all_variables(self):
        raise NotImplementedError

    @staticmethod
    def _create_directory(path):
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise
        return path

    def _query(self):
        raise NotImplementedError


class GridProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        return list(self.dataset.keys())

    def _query(self):
        constraints = []

        #
        # time
        # [x:y]
        #

        # find the the index range
        time_start_idx, time_end_idx = self._grid_constraint_indexes(self.DEFAULT_DIMENSION_TIME, self._time_start, self._time_end)

        constraints.append('[{}:{}]'.format(
            time_start_idx,
            time_end_idx,
        ))

        #
        # latitude
        # [x:y]
        #

        # find the index range
        lat_start_idx, lat_end_idx = self._grid_constraint_indexes(self.DEFAULT_DIMENSION_LATITUDE, self._lat_start, self._lat_end)

        constraints.append('[{}:{}]'.format(
            lat_start_idx,
            lat_end_idx,
        ))

        #
        # longitude
        # [x:y]
        #

        # find the index range
        lng_start_idx, lng_end_idx = self._grid_constraint_indexes(self.DEFAULT_DIMENSION_LONGITUDE, self._lng_start, self._lng_end)

        constraints.append('[{}:{}]'.format(
            lng_start_idx,
            lng_end_idx,
        ))

        return ','.join(['{}{}'.format(v, ''.join(constraints)) for v in self._variables])


class SequenceProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        # TODO - this is a poor assumption on how the sequence data is structured
        # a sequence in a dataset has one attribute which is a Sequence, so extract the variables from that
        keys = list(self.dataset.keys())
        return list(self.dataset[keys[0]].keys())

    def _query(self):
        projection = ','.join(list(self.DEFAULT_DIMENSIONS) + self._variables)
        constraints = '&'.join([
            '{}{}{}'.format(self.DEFAULT_DIMENSION_TIME, '>=', self._time_start),
            '{}{}{}'.format(self.DEFAULT_DIMENSION_TIME, '<=', self._time_end),
            '{}{}{}'.format(self.DEFAULT_DIMENSION_LONGITUDE, '>=', self._lng_start),
            '{}{}{}'.format(self.DEFAULT_DIMENSION_LONGITUDE, '<=', self._lng_end),
            '{}{}{}'.format(self.DEFAULT_DIMENSION_LATITUDE, '>=', self._lat_start),
            '{}{}{}'.format(self.DEFAULT_DIMENSION_LATITUDE, '<=', self._lat_end),
        ])
        return '{}&{}'.format(projection, constraints)


class NDBCProcessor(GridProcessor):

    def _data_requests(self):
        """
        https://dods.ndbc.noaa.gov/
        The NDBC has a THREDDS catalog which includes datasets for each station where the station format is 5 characters, i.e "20cm4".
        The datasets inside each station includes historical data and the most recent (45 days) data.  There is no overlap.
            - Historical data is in the format "20cm4h2014.nc"
            - Current data is in the format "20cm4h9999.nc"
        NOTE: NDBC's SSL certs are either self hosted or not in the os's bundle, so let's just not verify.
        """
        catalog = xmltodict.parse(requests.get(self.provider.url, verify=False).content)
        station_urls = []
        dataset_urls = []

        for catalog_ref in catalog['catalog']['dataset']['catalogRef']:
            station_urls.append('{}/{}'.format(
                os.path.dirname(self.provider.url),
                parse.urlparse(catalog_ref['@xlink:href']).path),
            )

        for station_url in station_urls:
            station = xmltodict.parse(requests.get(station_url, verify=False).content)
            station_dataset_urls = []
            for dataset in station['catalog']['dataset']['dataset']:
                print(dataset)
                station_dataset_urls.append(dataset['@name'])
            #print(station_dataset_urls)

        return [
        ]
