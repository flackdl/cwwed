import xarray as xr


water_level_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/fort.63.nc'
wind_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_wnd.nc'
wave_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc'

dataset_water_level = xr.open_dataset(water_level_dataset_path, drop_variables=('max_nvdll', 'max_nvell'))
dataset_wave_height = xr.open_dataset(wave_dataset_path)
dataset_wind = xr.open_dataset(wind_dataset_path)

ds = xr.Dataset(
    {
        'water_level': (['time', 'node'], dataset_water_level.zeta[:257]),
        'wave_height': (['time', 'node'], dataset_wave_height.hs[1:]),
        'uwnd': (['time', 'node'], dataset_wind.uwnd[1:]),
        'vwnd': (['time', 'node'], dataset_wind.vwnd[1:]),
    },
    coords={
        'time': (['time'], dataset_water_level.time[:257]),
        'x': (['node'], dataset_water_level.x),
        'y': (['node'], dataset_water_level.y),
    },
)

ds.to_netcdf('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy.nc')
