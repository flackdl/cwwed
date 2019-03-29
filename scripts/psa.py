import time
import xarray as xr
import numpy
from django.utils.dateparse import parse_datetime


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
        'x': (['x'], dataset_water_level.x),
        'y': (['y'], dataset_water_level.y),
    },
)

nearest_index = 1633019

wind_speeds = []
x_winds = []
y_winds = []

now = time.time()

for idx, date in enumerate(ds.time):
    data_date = parse_datetime(str(date.values))
    data_windx = ds.uwnd.isel(time=idx, node=nearest_index)
    data_windy = ds.vwnd.isel(time=idx, node=nearest_index)

    x_winds.append(data_windx)
    y_winds.append(data_windy)

print('list: {}'.format(time.time() - now))

now = time.time()

numpy.arctan2(
    numpy.abs(x_winds),
    numpy.abs(y_winds),
)

print('calc: {}'.format(time.time() - now))
