import xarray as xr
import numpy as np


water_level_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/fort.63.nc'
water_level_max_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/maxele.63.nc'
wind_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_wnd.nc'
wave_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc'

dataset_water_level = xr.open_dataset(water_level_dataset_path, drop_variables=('max_nvdll', 'max_nvell'))
dataset_water_level_max = xr.open_dataset(water_level_max_dataset_path, drop_variables=('max_nvdll', 'max_nvell'))
dataset_wave_height = xr.open_dataset(wave_dataset_path)
dataset_wind = xr.open_dataset(wind_dataset_path)


def date_mask(dataset: xr.Dataset):
    return (
            (dataset['time'] >= np.datetime64('2012-10-27')) &
            (dataset['time'] <= np.datetime64('2012-11-01 23:00:00'))
    )


ds = xr.Dataset(
    {
        'water_level': (['time', 'node'], dataset_water_level.zeta[date_mask(dataset_water_level)]),
        'water_level_max': (['node'], dataset_water_level_max.zeta_max),
        'wave_height': (['time', 'node'], dataset_wave_height.hs[date_mask(dataset_wave_height)]),
        'uwnd': (['time', 'node'], dataset_wind.uwnd[date_mask(dataset_wind)]),
        'vwnd': (['time', 'node'], dataset_wind.vwnd[date_mask(dataset_wind)]),
    },
    coords={
        # arbitrarily using water level for coord values
        'time': (['time'], dataset_water_level.time[date_mask(dataset_water_level)]),
        'x': (['node'], dataset_water_level.x),
        'y': (['node'], dataset_water_level.y),
    },
)

# save as netcdf classic because hyrax chokes on 64bit ints
ds.to_netcdf('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy.nc', format='NETCDF4_CLASSIC')
