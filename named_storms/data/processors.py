import os
import tempfile
import shutil
import ssl
import logging
import h5py
import numpy
from typing import List, NamedTuple
import requests
import xarray.backends
from named_storms.models import CoveredDataProvider, NamedStorm, NamedStormCoveredData
from named_storms.utils import named_storm_covered_data_incomplete_path, create_directory


DEFAULT_DIMENSION_TIME = 'time'
DEFAULT_DIMENSION_LATITUDE = 'latitude'
DEFAULT_DIMENSION_LONGITUDE = 'longitude'
DEFAULT_LABEL = 'data'


# using named tuple as data structure which is passed to the processor task.
# this was chosen because it's easily serializable via celery while still offering type-hints
class ProcessorData(NamedTuple):
    named_storm_id: any
    provider_id: any
    url: str
    label: str = None
    group: str = None
    dimension_time: str = None
    dimension_latitude: str = None
    dimension_longitude: str = None
    kwargs: dict = dict()


class BaseProcessor:
    """
    Base Processor from which all processors extend
    """

    _url: str = None
    _success: bool = True
    _output_path: str = None
    _named_storm: NamedStorm = None
    _provider: CoveredDataProvider = None
    _named_storm_covered_data: NamedStormCoveredData = None
    _label: str = None
    _group: str = None
    _data_extension: str = None
    _dimension_time: str = None
    _dimension_latitude: str = None
    _dimension_longitude: str = None
    _dimensions: set = set()
    _kwargs: dict = dict()

    def __init__(self, named_storm: NamedStorm, provider: CoveredDataProvider, url: str, label=None, group=None,
                 dimension_time=None, dimension_latitude=None, dimension_longitude=None, **kwargs):
        self._named_storm = named_storm
        self._provider = provider
        self._url = url
        self._label = label or DEFAULT_LABEL
        self._group = group
        self._dimension_time = dimension_time or DEFAULT_DIMENSION_TIME
        self._dimension_latitude = dimension_latitude or DEFAULT_DIMENSION_LATITUDE
        self._dimension_longitude = dimension_longitude or DEFAULT_DIMENSION_LONGITUDE
        self._dimensions = {self._dimension_time, self._dimension_latitude, self._dimension_longitude}
        self._kwargs = kwargs
        self._named_storm_covered_data = self._named_storm.namedstormcovereddata_set.get(
            covered_data=self._provider.covered_data)

        # conditionally toggle ssl verification
        self._toggle_verify_ssl(enable=self._verify_ssl())

        # create top level staging directory
        create_directory(self._incomplete_path())

        # create output path
        self._output_path = self._get_output_path()

        # store output directory
        create_directory(os.path.dirname(self._output_path))

    def to_dict(self):
        return {
            'output_path': self._output_path,
            'url': self._url,
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
            self._success = False
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

    def _get_output_path(self):
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

    def _covered_data_extent(self) -> tuple:
        # extent/boundaries of covered data
        # i.e (-97.55859375, 28.23486328125, -91.0107421875, 33.28857421875)
        # TODO - we can't assume it's always in "degrees_east"... must read metadata
        extent = self._named_storm_covered_data.geo.extent
        # we need to convert lng to "degrees_east" format (i.e 0-360)
        # i.e (262.44, 28.23486328125, 268.98, 33.28857421875)
        extent = (
            extent[0] if extent[0] > 0 else 360 + extent[0],  # lng
            extent[1],                                        # lat
            extent[2] if extent[2] > 0 else 360 + extent[2],  # lng
            extent[3],                                        # lat
        )
        return extent

    def _provider_start_end_timestamps(self) -> tuple:
        # some datasets define their time stamps using non-unix epochs so allow them to define it themselves
        epoch_stamp = self._provider.epoch_datetime.timestamp()

        cmp_start_stamp = self._named_storm_covered_data.date_start.timestamp() - epoch_stamp
        cmp_end_stamp = self._named_storm_covered_data.date_end.timestamp() - epoch_stamp

        return cmp_start_stamp, cmp_end_stamp

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

    def _post_process(self):
        pass

    def _fetch(self):

        # fetch the actual file
        file_req = requests.get(self._url, stream=True, timeout=10)

        # write to tmp space then move
        _, tmp_file = tempfile.mkstemp()
        with open(tmp_file, 'wb') as f:
            for chunk in file_req.iter_content(chunk_size=1024):
                f.write(chunk)
        # set file permissions -rw-r--r-- (using octal literal notation)
        os.chmod(tmp_file, 0o644)
        shutil.move(tmp_file, self._output_path)

        # run any post processing on the dataset
        self._post_process()


class HierarchicalDataFormatProcessor(GenericFileProcessor):
    # TODO - this isn't doing any filtering yet

    """
    Hierarchical Data Format
    https://en.wikipedia.org/wiki/Hierarchical_Data_Format
    """
    _dataset_file: h5py.File = None

    def _filter_dataset(self):
        pass

    def _post_process(self) -> None:
        # open dataset for reading & writing
        self._dataset_file = h5py.File(self._output_path, 'r+')
        # filter
        self._filter_dataset()
        # close
        self._dataset_file.close()


class BinaryFileProcessor(GenericFileProcessor):
    """
    Parses binary file via numpy.  Expects the `dtype` to be passed in via `kwargs`
    """
    DATA_TYPE_TIME_KEY = 'time'
    DATA_TYPE_LAT_KEY = 'lat'
    DATA_TYPE_LON_KEY = 'lon'
    DATA_TYPE_KWARG_KEY = 'data_type'

    _ndarray: numpy.ndarray = None

    def _fetch(self):
        # download/filter the file
        super()._fetch()
        # skip and remove file if it's an empty dataset
        if len(self._ndarray) == 0:
            logging.info('Skipping dataset with no values')
            os.remove(self._output_path)

    def _post_process(self) -> None:
        # the numpy dtype needs to be a list of tuples so convert it first because celery sends it as a list of lists
        data_type = [(t[0], t[1]) for t in self._kwargs[self.DATA_TYPE_KWARG_KEY]]
        data_type = numpy.dtype(data_type)

        # create the numpy data array from the file using the supplied dtype
        self._ndarray = numpy.fromfile(self._output_path, dtype=data_type)

        # define the start/end timestamps to compare against
        cmp_start_stamp, cmp_end_stamp = self._provider_start_end_timestamps()

        self._ndarray = self._ndarray[self._ndarray[self.DATA_TYPE_TIME_KEY] >= cmp_start_stamp]
        self._ndarray = self._ndarray[self._ndarray[self.DATA_TYPE_TIME_KEY] <= cmp_end_stamp]

        # filter the data down using lat/lon from the storm's extent
        storm_extent = self._covered_data_extent()

        lat_start = storm_extent[1]
        lat_end = storm_extent[3]
        lon_start = storm_extent[0]
        lon_end = storm_extent[2]

        self._ndarray = self._ndarray[self._ndarray[self.DATA_TYPE_LAT_KEY] >= lat_start]
        self._ndarray = self._ndarray[self._ndarray[self.DATA_TYPE_LAT_KEY] <= lat_end]
        self._ndarray = self._ndarray[self._ndarray[self.DATA_TYPE_LON_KEY] >= lon_start]
        self._ndarray = self._ndarray[self._ndarray[self.DATA_TYPE_LON_KEY] <= lon_end]

        # save the file with the filtered data
        self._ndarray.tofile(self._output_path)


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

        # open the dataset url and create the dataset/processor while conditionally disabling ssl verification
        session = self._session()
        session.verify = self._verify_ssl()
        store = xarray.backends.PydapDataStore.open(self._url, session=session)

        # fetch and subset the dataset
        self._dataset = xarray.open_dataset(store, decode_times=False)
        self._dataset = self._slice_dataset()

    def _fetch(self):

        # verify it has values after getting the subset
        if not self._dataset_has_dimension_values():
            logging.info('Skipping dataset with no values for a dimension ({}): %s' % self._url)
            return

        # store as netcdf and close dataset
        self._dataset.to_netcdf(self._output_path)
        self._dataset.close()

    def _slice_dataset(self) -> xarray.Dataset:
        # doesn't have expected dimensions
        if not self._dataset_has_expected_dimensions():
            return self._dataset

        variables = self._all_variables()
        self._verify_dimensions(variables)

        # remove dimensions from variables
        self._variables = list(set(variables).difference(self._dimensions))

        # use the named storm covered data provider start/end dates for constraints
        self._time_start, self._time_end = self._provider_start_end_timestamps()

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
        time_start_idx, time_end_idx = self._constraint_indexes(self._dimension_time, self._time_start, self._time_end)
        lat_start_idx, lat_end_idx = self._constraint_indexes(self._dimension_latitude, self._lat_start, self._lat_end)
        lng_start_idx, lng_end_idx = self._constraint_indexes(self._dimension_longitude, self._lng_start, self._lng_end)

        # build filter args
        filter_kwargs = {
            self._dimension_time: slice(time_start_idx, time_end_idx),
            self._dimension_latitude: slice(lat_start_idx, lat_end_idx),
            self._dimension_longitude: slice(lng_start_idx, lng_end_idx),
        }

        return self._dataset.isel(**filter_kwargs)

    def _dataset_has_dimension_values(self) -> bool:
        # verifies every dimension (i.e "time", "longitude", "latitude") has actual values associated with it
        return all(map(lambda x: len(self._dataset[x]), list(self._dataset.dims)))

    def _dataset_has_expected_dimensions(self) -> bool:
        # returns whether the supplied dimensions exist in the dataset's dimensions
        return self._dimensions.issuperset(list(self._dataset.dims))

    def _dataset_has_expected_dimensions_as_variables(self) -> bool:
        # returns whether the supplied dimensions exist in the dataset's variables
        return self._dimensions.issuperset(list(self._dataset.variables.keys()))

    def _constraint_indexes(self, dimension: str, start: float, end: float) -> tuple:
        """
        return the index range for our constraint values
        """

        # convert numpy array to list for comparison
        values = self._dataset[dimension].values.tolist()

        # find the index range and fallback the start/end index to 0/None, respectively, if it's not in range
        idx_start = next((idx for idx, v in enumerate(values) if v >= start), 0)
        idx_end = next((idx for idx, v in enumerate(values) if v >= end), None)

        return idx_start, idx_end

    def _verify_dimensions(self, variables):
        if not self._dimensions.issubset(variables):
            raise Exception('missing expected dimensions')

    def _all_variables(self):
        raise NotImplementedError

    def _session(self) -> requests.Session:
        session = requests.Session()
        session.verify = self._verify_ssl()
        return session


class GridOpenDapProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        return list(self._dataset.variables.keys())


class SequenceOpenDapProcessor(OpenDapProcessor):

    def _all_variables(self) -> list:
        # TODO - this is a poor assumption on how the sequence data is structured
        # a sequence in a dataset has one attribute which is a Sequence, so extract the variables from that
        keys = list(self._dataset.keys())
        return list(self._dataset[keys[0]].keys())
