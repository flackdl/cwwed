import os
import ssl
import errno
import logging
from collections import namedtuple
from typing import List
import requests
from django.conf import settings
from requests import HTTPError
import xarray.backends
from named_storms.models import CoveredDataProvider, NamedStorm, NamedStormCoveredData


ProcessorData = namedtuple(
    'ProcessorData',
    ['named_storm_id', 'provider_id', 'url', 'label'],
)

DEFAULT_DIMENSION_TIME = 'time'
DEFAULT_DIMENSION_LATITUDE = 'latitude'
DEFAULT_DIMENSION_LONGITUDE = 'longitude'
DEFAULT_DIMENSIONS = {
    DEFAULT_DIMENSION_TIME,
    DEFAULT_DIMENSION_LATITUDE,
    DEFAULT_DIMENSION_LONGITUDE,
}


class OpenDapProcessor:
    url: str = None
    output_path: str = None
    success: bool = None

    _named_storm: NamedStorm = None
    _provider: CoveredDataProvider = None
    _dataset: xarray.Dataset = None
    _label: str = None
    _named_storm_covered_data: NamedStormCoveredData = None
    _response_type: str = 'nc'  # netcdf
    _variables: List[str] = None
    _time_start: float = None
    _time_end: float = None
    _lat_start: float = None
    _lat_end: float = None
    _lng_start: float = None
    _lng_end: float = None

    def __init__(self, named_storm: NamedStorm, provider: CoveredDataProvider, url: str, label='default'):
        self._named_storm = named_storm
        self._provider = provider
        self.url = url
        self._label = label
        self._named_storm_covered_data = self._named_storm.namedstormcovereddata_set.get(covered_data=self._provider.covered_data)
        self._toggle_verify_ssl(enable=self._verify_ssl())

        # open the dataset url and create the dataset/processor
        # conditionally disable ssl verification
        session = self._session()
        session.verify = self._verify_ssl()
        store = xarray.backends.PydapDataStore.open(url, session=session)
        # fetch and subset the dataset
        self._dataset = xarray.open_dataset(store, decode_times=False)
        self._dataset = self._slice_dataset()

    def fetch(self):
        try:
            self._fetch()
        except HTTPError as e:
            logging.warning('HTTPError: %s' % str(e))
        except Exception as e:
            logging.warning('Exception: %s' % str(e))
        finally:
            # re-enable ssl
            self._toggle_verify_ssl(enable=True)

    def _fetch(self):

        # verify it has values after getting the subset
        if not self._dataset_has_dimension_values():
            self.success = True
            logging.info('Skipping dataset with no values for a dimension ({}): %s' % self.url)
            return

        # create a directory to house the storm's covered data
        path = self._create_directory('{}/{}/{}'.format(
            settings.COVERED_DATA_CACHE_DIR,
            self._named_storm,
            self._provider.covered_data,
        ))

        self.output_path = '{}/{}.{}'.format(
            path,
            self._label,
            self._response_type,
        )

        # store as netcdf
        self._dataset.to_netcdf(self.output_path)

        self.success = True

    def _slice_dataset(self) -> xarray.Dataset:

        variables = self._all_variables()
        self._verify_dimensions(variables)

        # remove dimensions from variables
        self._variables = list(set(variables).difference(DEFAULT_DIMENSIONS))

        # use the named storm covered data start/end dates for constraints
        self._time_start = self._named_storm_covered_data.date_start.timestamp()
        self._time_end = self._named_storm_covered_data.date_end.timestamp()

        # covered data boundaries
        storm_extent = self._covered_data_extent()

        # lat range
        self._lat_start = storm_extent[1]
        self._lat_end = storm_extent[3]

        # lng range
        self._lng_start = storm_extent[0]
        self._lng_end = storm_extent[2]

        #
        # slice the dimensions
        #

        time_start_idx, time_end_idx = self._grid_constraint_indexes(DEFAULT_DIMENSION_TIME, self._time_start, self._time_end)
        lat_start_idx, lat_end_idx = self._grid_constraint_indexes(DEFAULT_DIMENSION_LATITUDE, self._lat_start, self._lat_end)
        lng_start_idx, lng_end_idx = self._grid_constraint_indexes(DEFAULT_DIMENSION_LONGITUDE, self._lng_start, self._lng_end)

        return self._dataset.isel(
            time=slice(time_start_idx, time_end_idx),
            latitude=slice(lat_start_idx, lat_end_idx),
            longitude=slice(lng_start_idx, lng_end_idx),
        )

    def _dataset_has_dimension_values(self) -> bool:
        return all(map(lambda x: len(self._dataset[x]), list(self._dataset.dims)))

    def _grid_constraint_indexes(self, dimension: str, start: float, end: float) -> tuple:
        # find the index range for our constraint values

        values = self._dataset[dimension].values.tolist()  # convert numpy array to list

        # find the the index range
        # fallback start/end index to 0/None if it's not in range, respectively
        idx_start = next((idx for idx, v in enumerate(values) if v >= start), 0)
        idx_end = next((idx for idx, v in enumerate(values) if v >= end), None)

        return idx_start, idx_end

    def _covered_data_extent(self) -> tuple:
        # extent/boundaries of covered data
        # i.e (-97.55859375, 28.23486328125, -91.0107421875, 33.28857421875)
        extent = self._named_storm_covered_data.geo.extent
        # TODO - we can't assume it's always in "degrees_east"... read metadata
        # however, we need to convert lng to "degrees_east" format (i.e 0-360)
        # i.e (262.44, 28.23486328125, 268.98, 33.28857421875)
        extent = (
            extent[0] if extent[0] > 0 else 360 + extent[0],  # lng
            extent[1],                                        # lat
            extent[2] if extent[2] > 0 else 360 + extent[2],  # lng
            extent[3],                                        # lat
        )
        return extent

    @staticmethod
    def _verify_dimensions(variables):
        if not DEFAULT_DIMENSIONS.issubset(variables):
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

    @staticmethod
    def _verify_ssl() -> bool:
        return True

    def _session(self):
        session = requests.Session()
        session.verify = self._verify_ssl()
        return session

    @staticmethod
    def _toggle_verify_ssl(enable=True):
        if enable:
            ssl._create_default_https_context = ssl.create_default_context
        else:
            ssl._create_default_https_context = ssl._create_unverified_context


class GridProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        return list(self._dataset.variables.keys())


class SequenceProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        # TODO - this is a poor assumption on how the sequence data is structured
        # a sequence in a dataset has one attribute which is a Sequence, so extract the variables from that
        keys = list(self._dataset.keys())
        return list(self._dataset[keys[0]].keys())
