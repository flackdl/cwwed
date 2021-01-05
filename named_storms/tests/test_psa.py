import tempfile
import xarray as xr
import numpy as np
from cfchecker import cfchecks
from django.utils.dateparse import parse_datetime

from named_storms.tests.base import BaseTest
from named_storms.psa.validator import PsaDatasetValidator


class PSATest(BaseTest):
    def setUp(self):
        super().setUp()

    def test_cf_conventions(self):
        ds = xr.Dataset()
        ds.attrs['Conventions'] = 'UGRID-0.9.0'  # invalid
        ds['element'] = np.random.random(10)
        ds['element'].attrs['units'] = 'nondenominational'  # invalid
        ds_path = self._save_ds(ds)
        results = self._cf_check_results(ds_path)
        self.assertTrue(len(results['global']['ERROR']) > 0, 'Should have CF Convention errors')
        self.assertTrue(len(results['variables']['element']['ERROR']) > 0, 'Should have CF Convention errors')

    def test_variables(self):
        ds = xr.Dataset({'water_level': xr.DataArray()})
        validator = PsaDatasetValidator(ds)
        self.assertTrue(validator.is_valid_variables(['water_level']), 'Missing expected variables')
        self.assertFalse(validator.is_valid_variables(['WRONG']), 'Should be missing expected variables')

    def test_coordinates(self):
        ds_valid = xr.Dataset(
            coords={
                "time": self.nsem_psa.dates,
                "lat": [],
                "lon": [],
            },
        )
        validator = PsaDatasetValidator(ds_valid)
        self.assertTrue(validator.is_valid_coords(), 'Missing coordinate variables')

        ds_invalid = xr.Dataset(
            coords={
                "A": [],  # wrong
                "B": [],  # wrong
                "C": [],  # wrong
            },
        )
        validator = PsaDatasetValidator(ds_invalid)
        self.assertFalse(validator.is_valid_coords(), 'Should be missing coordinate variables')

    def test_dates(self):
        ds = xr.Dataset(coords={"time": self.nsem_psa.dates})

        valid_date = parse_datetime('2012-10-29T13:00:00')
        invalid_date = parse_datetime('1800-01-01T01:00:00')

        validator = PsaDatasetValidator(ds)
        self.assertTrue(validator.is_valid_date(valid_date), 'Invalid date')
        self.assertFalse(validator.is_valid_date(invalid_date), 'Valid date')

    def _cf_check_results(self, ds_path: str):
        cf_check = cfchecks.CFChecker(silent=True)
        cf_check.checker(ds_path)
        return cf_check.results

    def _save_ds(self, ds: xr.Dataset) -> str:
        with tempfile.NamedTemporaryFile(suffix='.nc', delete=False) as fh:
            ds.to_netcdf(fh.name)
            return fh.name


