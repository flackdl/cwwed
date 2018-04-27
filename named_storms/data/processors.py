import os
import tempfile
import shutil
import ssl
import logging
from typing import List, NamedTuple
import requests
import xarray.backends
from named_storms.models import CoveredDataProvider, NamedStorm, NamedStormCoveredData
from named_storms.utils import named_storm_covered_data_incomplete_path, create_directory


# using named tuple as data structure which is passed to the processor task.
# this was chosen because it's easily serializable via celery while still offering type-hints
class ProcessorData(NamedTuple):
    named_storm_id: any
    provider_id: any
    url: str
    label: str = None
    group: str = None


DEFAULT_DIMENSION_TIME = 'time'
DEFAULT_DIMENSION_LATITUDE = 'latitude'
DEFAULT_DIMENSION_LONGITUDE = 'longitude'
DEFAULT_DIMENSIONS = {
    DEFAULT_DIMENSION_TIME,
    DEFAULT_DIMENSION_LATITUDE,
    DEFAULT_DIMENSION_LONGITUDE,
}

DEFAULT_LABEL = 'data'


class BaseProcessor:
    url: str = None
    output_path: str = None
    success: bool = True

    _named_storm: NamedStorm = None
    _provider: CoveredDataProvider = None
    _named_storm_covered_data: NamedStormCoveredData = None
    _label: str = None
    _group: str = None
    _data_extension: str = None

    def __init__(self, named_storm: NamedStorm, provider: CoveredDataProvider, url: str, label=None, group=None):
        self._named_storm = named_storm
        self._provider = provider
        self.url = url
        self._label = label or DEFAULT_LABEL
        self._group = group
        self._named_storm_covered_data = self._named_storm.namedstormcovereddata_set.get(
            covered_data=self._provider.covered_data)
        self._toggle_verify_ssl(enable=self._verify_ssl())

        # create top level staging directory
        create_directory(self._incomplete_path())

        # create dataset directory
        self.output_path = self._output_path()
        create_directory(os.path.dirname(self.output_path))

    def to_dict(self):
        return {
            'output_path': self.output_path,
            'url': self.url,
            'label': self._label,
            'group': self._group,
            'named_storm': str(self._named_storm),
            'covered_data': str(self._named_storm_covered_data),
            'provider': str(self._provider),
        }

    def fetch(self):
        try:
            self._fetch()
        except Exception as e:
            self.success = False
            logging.exception(e)
            raise

    def _fetch(self):
        raise NotImplementedError

    def _incomplete_path(self):
        # return path for the staging/incomplete directory
        return os.path.join(
            named_storm_covered_data_incomplete_path(self._named_storm),
            self._named_storm_covered_data.covered_data.name,
        )

    def _output_path(self):
        paths = [
            self._incomplete_path(),
        ]

        # conditionally create a secondary "group" directory to house this dataset
        if self._group:
            paths.append(self._group)

        file_name = self._label

        # include extension if it was declared
        if self._data_extension:
            file_name = '{}.{}'.format(file_name, self._data_extension)

        paths.append(file_name)

        return os.path.join(*paths)

    @staticmethod
    def _toggle_verify_ssl(enable=True):
        """
        Monkey patch ssl verification
        """
        if enable:
            ssl._create_default_https_context = ssl.create_default_context
        else:
            ssl._create_default_https_context = ssl._create_unverified_context

    @staticmethod
    def _verify_ssl() -> bool:
        return True


class GenericFileProcessor(BaseProcessor):

    def _fetch(self):

        # fetch the actual file
        file_req = requests.get(self.url, stream=True, timeout=10)

        # write to tmp space then move
        _, tmp_file = tempfile.mkstemp()
        with open(tmp_file, 'wb') as f:
            for chunk in file_req.iter_content(chunk_size=1024):
                f.write(chunk)
        # set file permissions
        os.chmod(tmp_file, 420)  # -rw-r--r--
        shutil.move(tmp_file, self.output_path)


class OpenDapProcessor(BaseProcessor):

    _dataset: xarray.Dataset = None
    _data_extension: str = 'nc'  # netcdf
    _variables: List[str] = None
    _time_start: float = None
    _time_end: float = None
    _lat_start: float = None
    _lat_end: float = None
    _lng_start: float = None
    _lng_end: float = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # open the dataset url and create the dataset/processor
        # conditionally disable ssl verification
        session = self._session()
        session.verify = self._verify_ssl()
        store = xarray.backends.PydapDataStore.open(self.url, session=session)

        # fetch and subset the dataset
        self._dataset = xarray.open_dataset(store, decode_times=False)
        self._dataset = self._slice_dataset()

    def _fetch(self):

        # verify it has values after getting the subset
        if not self._dataset_has_dimension_values():
            logging.info('Skipping dataset with no values for a dimension ({}): %s' % self.url)
            return

        # store as netcdf and close dataset
        self._dataset.to_netcdf(self.output_path)
        self._dataset.close()

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

        # find the array indexes for our slices so we can take advantage of opendap's server side processing vs loading everything into memory
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

    def _session(self):
        session = requests.Session()
        session.verify = self._verify_ssl()
        return session


class GridProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        return list(self._dataset.variables.keys())


class SequenceProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        # TODO - this is a poor assumption on how the sequence data is structured
        # a sequence in a dataset has one attribute which is a Sequence, so extract the variables from that
        keys = list(self._dataset.keys())
        return list(self._dataset[keys[0]].keys())
