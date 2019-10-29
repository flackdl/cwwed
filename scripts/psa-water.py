import xarray as xr
import numpy as np


water_level_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/fort.63.nc'
water_level_max_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/maxele.63.nc'
wave_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc'

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
        'water_level': (['time', 'node'], dataset_water_level.zeta[date_mask(dataset_water_level)]),
        'water_level_max': (['node'], dataset_water_level_max.zeta_max),
        'wave_height': (['time', 'node'], dataset_wave_height.hs[date_mask(dataset_wave_height)]),
    },
    coords={
        # arbitrarily using water level for coord values
        'time': (['time'], dataset_water_level.time[date_mask(dataset_water_level)]),
        'lon': (['node'], dataset_water_level.x),
        'lat': (['node'], dataset_water_level.y),
    },
)

# save as netcdf classic because hyrax chokes on 64bit ints
ds.to_netcdf('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy-water.nc', format='NETCDF4_CLASSIC')
