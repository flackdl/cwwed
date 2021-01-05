import xarray as xr
from datetime import datetime


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
