import os
import xarray as xr
import pandas as pd

src_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/florence/ali/HS_WND_STR_SUBSET.nc'
out_path = os.path.join(os.path.dirname(src_path), 'water-demo.nc')

dates = pd.date_range(start='2018-09-14T00:00:00', end='2018-09-14T20:00:00', freq='1H')

# remove any existing path if it exists
if os.path.exists(out_path):
    os.remove(out_path)

# open dataset
ds_in = xr.open_dataset(src_path)

# map values to be on the hour
water_levels = ds_in['hs'].interp(time=dates)

# create a new dataset with the hourly dates
ds_out = xr.Dataset({
    'water_level': xr.DataArray(water_levels, coords=[dates, ds_in.latitude, ds_in.longitude], dims=["time", "lat", "lon"]),
})

print('Saving to {}'.format(out_path))

# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_path, format='NETCDF4_CLASSIC')
