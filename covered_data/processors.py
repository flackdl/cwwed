import os
import errno
import logging
import requests
import urllib.parse
from django.conf import settings
from pydap.client import open_url
from pydap.model import DatasetType
from requests import HTTPError
from covered_data.models import NamedStormCoveredDataProvider, PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_TYPE_SEQUENCE


class OpenDapProcessor:
    DEFAULT_DIMENSION_TIME = 'time'
    DEFAULT_DIMENSION_LATITUDE = 'latitude'
    DEFAULT_DIMENSION_LONGITUDE = 'longitude'
    DEFAULT_DIMENSIONS = {DEFAULT_DIMENSION_TIME, DEFAULT_DIMENSION_LONGITUDE, DEFAULT_DIMENSION_LATITUDE}

    dataset = None  # type: DatasetType
    provider = None  # type: NamedStormCoveredDataProvider
    output_path = None  # type: str
    success = None  # type: bool
    data_type = None  # type: str
    response_type = 'nc'
    response_code = None  # type: int
    request_url = None  # type: str

    def __init__(self, provider: NamedStormCoveredDataProvider):
        self.provider = provider
        self.request_url = urllib.parse.unquote('{}.{}?{}'.format(
            self.provider.url, self.response_type, self._constraints()))

    def fetch(self):
        try:
            self._fetch()
        except HTTPError as e:
            self.success = False
            logging.warning('HTTPError: %s' % str(e))
        except Exception as e:
            self.success = False
            logging.warning('Exception: %s' % str(e))

    def _fetch(self):

        # fetch data with constraints
        response = requests.get(self.request_url, stream=True)

        self.response_code = response.status_code
        response.raise_for_status()

        # create a directory to house the storm's covered data
        path = self._create_directory('{}/{}'.format(
            settings.COVERED_DATA_CACHE_DIR,
            self.provider.covered_data.named_storm,
        ))

        # store output
        self.output_path = '{}/{}.{}'.format(
            path,
            self.provider.covered_data.name,
            self.response_type,
        )
        with open(self.output_path, 'wb') as fd:
            # stream the content so it's more efficient
            for block in response.iter_content(chunk_size=1024):
                fd.write(block)

        self.success = response.ok

    def _constraints(self) -> str:

        constraints = []

        self.dataset = open_url(self.provider.url)
        variables = self._variables()

        self._verify_dimensions(variables)

        # remove dimensions from variables
        variables = list(set(variables).difference(self.DEFAULT_DIMENSIONS))

        # use the covered data start/end dates for constraints
        time_start = self.provider.covered_data.date_start.timestamp()
        time_end = self.provider.covered_data.date_end.timestamp()

        # covered data boundaries
        storm_extent = self._covered_data_extent()

        # lat range
        lat_start = storm_extent[1]
        lat_end = storm_extent[3]

        # lng range
        lng_start = storm_extent[0]
        lng_end = storm_extent[2]

        if self.data_type == PROCESSOR_DATA_TYPE_GRID:

            #
            # time
            # [x:y]
            #

            # find the the index range
            time_start_idx, time_end_idx = self._grid_constraint_indexes('time', time_start, time_end)

            constraints.append('[{}:{}]'.format(
                time_start_idx,
                time_end_idx,
            ))

            #
            # latitude
            # [x:y]
            #

            # find the index range
            lat_start_idx, lat_end_idx = self._grid_constraint_indexes('latitude', lat_start, lat_end)

            constraints.append('[{}:{}]'.format(
                lat_start_idx,
                lat_end_idx,
            ))

            #
            # longitude
            # [x:y]
            #

            # find the index range
            lng_start_idx, lng_end_idx = self._grid_constraint_indexes('longitude', lng_start, lng_end)

            constraints.append('[{}:{}]'.format(
                lng_start_idx,
                lng_end_idx,
            ))

            return ','.join(['{}{}'.format(v, ''.join(constraints)) for v in variables])

        elif self.data_type == PROCESSOR_DATA_TYPE_SEQUENCE:
            projection = ','.join(list(self.DEFAULT_DIMENSIONS) + variables)
            constraints = '&'.join([
                '{}{}{}'.format(self.DEFAULT_DIMENSION_TIME, '>=', time_start),
                '{}{}{}'.format(self.DEFAULT_DIMENSION_TIME, '<=', time_end),
                '{}{}{}'.format(self.DEFAULT_DIMENSION_LONGITUDE, '>=', lng_start),
                '{}{}{}'.format(self.DEFAULT_DIMENSION_LONGITUDE, '<=', lng_end),
                '{}{}{}'.format(self.DEFAULT_DIMENSION_LATITUDE, '>=', lat_start),
                '{}{}{}'.format(self.DEFAULT_DIMENSION_LATITUDE, '<=', lat_end),
            ])
            return '{}&{}'.format(projection, constraints)
        else:
            raise Exception('Invalid data_type "{}"'.format(self.data_type))

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

    def _variables(self):
        raise NotImplementedError

    @staticmethod
    def _create_directory(path):
        try:
            os.makedirs(path)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise
        return path


class GridProcessor(OpenDapProcessor):
    data_type = 'grid'

    def _variables(self) -> list:
        return list(self.dataset.keys())


class SequenceProcessor(OpenDapProcessor):
    data_type = 'sequence'

    def _variables(self) -> list:
        # a sequence in a dataset has one attribute which is a Sequence, so extract the variables from that
        keys = list(self.dataset.keys())
        return list(self.dataset[keys[0]].keys())
