import os
import xarray as xr
import pandas as pd

base_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/florence/ali/'
wave_height_src_path = os.path.join(base_path, 'HS_WND_STR_SUBSET.nc')
water_level_src_path = os.path.join(base_path, 'WATERLEVEL_CURRENT_STR_SUBSET.nc')
out_path = os.path.join(base_path, 'water-demo.nc')

dates = pd.date_range(start='2018-09-14T00:00:00', end='2018-09-14T20:00:00', freq='1H')

# remove any existing path if it exists
if os.path.exists(out_path):
    os.remove(out_path)

# open datasets
ds_wave = xr.open_dataset(wave_height_src_path)
ds_water = xr.open_dataset(water_level_src_path)

# map values to be on the hour
wave_height = ds_wave['hs'].interp(time=dates)
water_level = ds_water['zeta'].interp(time=dates)

# create a new dataset with the hourly dates
ds_out = xr.Dataset({
    'wave_height': xr.DataArray(wave_height, coords=[dates, ds_wave.latitude, ds_wave.longitude], dims=["time", "lat", "lon"]),
    'water_level': xr.DataArray(water_level, coords=[dates, ds_water.latitude, ds_water.longitude], dims=["time", "lat", "lon"]),
})

print('Saving to {}'.format(out_path))

# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_path, format='NETCDF4_CLASSIC')
