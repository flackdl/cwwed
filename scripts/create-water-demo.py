import os
import xarray as xr
import pandas as pd

base_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/florence/ali/'
wave_height_src_path = os.path.join(base_path, 'HS_WND_STR_SUBSET.nc')
water_level_src_path = os.path.join(base_path, 'WATERLEVEL_CURRENT_STR_SUBSET.nc')
out_path = os.path.join(base_path, 'water-demo.nc')

# remove existing output path if it exists
if os.path.exists(out_path):
    os.remove(out_path)

# dates to use to mirror the wind dataset
dates = pd.date_range(start='2018-09-14T01', end='2018-09-14T20', freq='1H', tz='UTC')

# open datasets
ds_wave = xr.open_dataset(wave_height_src_path)
# this one has invalid CF times (we'll decode afterwards)
ds_water = xr.open_dataset(water_level_src_path, decode_times=False)

# select wave and water level max
wave_height = ds_wave['hs'].sel(time=dates)
water_level_max = ds_water['zeta_max']

# since the water dataset has invalid seconds-since, we define the base date here
water_base_date = pd.to_datetime(ds_water.time.attrs['base_date'], format='%d-%b-%Y %H:%M:%S %Z')

# define the start and end times to filter
min_time = (dates[0] - water_base_date).total_seconds()
max_time = (dates[-1] - water_base_date).total_seconds()

# filter time and water level to the desired dates
water_level = ds_water.zeta[(ds_water.time <= max_time) & (ds_water.time >= min_time)]
times = ds_water.time[(ds_water.time <= max_time) & (ds_water.time >= min_time)]

# redefine water dataset with updated values and decode cf values
ds_water = xr.Dataset({"water_level": water_level, "time": times})
ds_water = xr.decode_cf(ds_water)

# create a new dataset with the variables
ds_out = xr.Dataset({
    'wave_height': xr.DataArray(wave_height, coords=[times, ds_wave.latitude, ds_wave.longitude], dims=["time", "lat", "lon"]),
    'water_level': xr.DataArray(ds_water['water_level'], coords=[times, ds_water.latitude, ds_water.longitude], dims=["time", "lat", "lon"]),
    'water_level_max': xr.DataArray(water_level_max, coords=[ds_water.latitude, ds_water.longitude], dims=["lat", "lon"]),
})

# update time to standard attributes
ds_out['time'].attrs['units'] = 'seconds since {}'.format(water_base_date)
ds_out['time'].attrs['base_date'] = water_base_date.isoformat()

print('Saving to {}'.format(out_path))

# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_path, format='NETCDF4_CLASSIC')
