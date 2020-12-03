import os

import xarray as xr
import numpy as np

out_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/sandy/'
out_full = os.path.join(out_path, 'water-demo.nc')
out_minimal = os.path.join(out_path, 'water-demo-minimal.nc')

water_level_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/sandy/WW3/adcirc/fort.63.nc'
water_level_max_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/sandy/WW3/adcirc/maxele.63.nc'
wave_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/sandy/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc'

dataset_water_level = xr.open_dataset(water_level_dataset_path, drop_variables=('max_nvdll', 'max_nvell'))
dataset_water_level_max = xr.open_dataset(water_level_max_dataset_path, drop_variables=('max_nvdll', 'max_nvell'))
dataset_wave_height = xr.open_dataset(wave_dataset_path)


def date_mask(dataset: xr.Dataset):
    start = '2012-10-29 13:00:00'
    end = '2012-10-30 09:00:00'
    return (
            (dataset['time'] >= np.datetime64(start)) &
            (dataset['time'] <= np.datetime64(end))
    )


ds = xr.Dataset(
    {
        'water_level': (
            ['time', 'node'],
            dataset_water_level.zeta[date_mask(dataset_water_level)],
            dataset_water_level.zeta.attrs,
        ),
        'water_level_max': (
            ['node'],
            dataset_water_level_max.zeta_max,
            dataset_water_level_max.zeta_max.attrs
        ),
        'wave_height': (
            ['time', 'node'],
            dataset_wave_height.hs[date_mask(dataset_wave_height)],
            dataset_wave_height.hs.attrs,
        ),
        'element': dataset_water_level.element,
    },
    coords={
        # arbitrarily using water level for coord values
        'time': (
            ['time'],
            dataset_water_level.time[date_mask(dataset_water_level)],
            dataset_water_level.time.attrs,
        ),
        'lon': (
            ['node'],
            dataset_water_level.x,
            dataset_water_level.x.attrs,
        ),
        'lat': (
            ['node'],
            dataset_water_level.y,
            dataset_water_level.y.attrs,
        ),
    },
    attrs=dataset_water_level.attrs,
)

#
# satisfy CF conventions
#

# remove invalid "units" attribute from "element" topology
if 'units' in ds.element.attrs:
    del ds.element.attrs['units']
# remove invalid "cf_role" attribute from "element" topology
if 'cf_role' in ds.element.attrs:
    del ds.element.attrs['cf_role']
# remove conflicting case-sensitive "conventions" UGRID attribute
if 'UGRID' in ds.attrs.get('Conventions', ''):
    del ds.attrs['Conventions']
# remove "positive" attribute from lat/lon
# "(4.3): Invalid value for positive attribute"
del ds.lon.attrs['positive']
del ds.lat.attrs['positive']

# fix invalid "water_level_max" standard name by copying from water level
ds.water_level_max.attrs['standard_name'] = ds.water_level.attrs['standard_name']

# full
print('Saving full to {}'.format(out_full))
ds.to_netcdf(out_full, format='NETCDF4_CLASSIC')  # save as netcdf classic because hyrax chokes on 64bit ints

# minimal
print('Saving minimal to {}'.format(out_minimal))
ds.isel(time=slice(0, 3)).to_netcdf(out_minimal, format='NETCDF4_CLASSIC')
