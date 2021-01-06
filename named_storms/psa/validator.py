import xarray as xr
from datetime import datetime

from named_storms.models import NsemPsaVariable


class PsaDatasetValidator:
    ds: xr.Dataset = None
    required_coords = {'time', 'lat', 'lon'}

    def __init__(self, ds: xr.Dataset):
        self.ds = ds

    def is_valid_coords(self) -> bool:
        return self.required_coords.issubset(list(self.ds.coords))

    def is_valid_variables(self, variables: list) -> bool:
        return set(variables).issubset(list(self.ds.data_vars))

    def is_valid_date(self, date: datetime) -> bool:
        try:
            self.ds.sel(time=date.isoformat())
        except KeyError:
            return False
        return True

    def is_valid_structured(self) -> bool:
        # make sure variables have the right dimension for a structured grid
        for variable in NsemPsaVariable.get_time_series_variables():
            # choose first time and make sure it has at least 2 dimensions (x, y)
            if variable in self.ds:
                shape = len(self.ds[variable].isel(time=0).shape)
                if shape < 2:
                    return False
        return True

    def is_valid_unstructured_topology(self, topology_name: str) -> bool:
        # validate the specified topology name is present in the dataset
        return topology_name in self.ds

    def is_valid_unstructured_start_index(self, topology_name: str) -> bool:
        # 0-based vs 1-based indexing for mesh connectivity
        # http://ugrid-conventions.github.io/ugrid-conventions/#zero-or-one-based-indexing
        return topology_name in self.ds and 'start_index' in self.ds[topology_name].attrs
