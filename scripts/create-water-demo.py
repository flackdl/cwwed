import os
import xarray as xr


src_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/florence/ali/HS_WND_STR_SUBSET.nc'
out_path = os.path.join(os.path.dirname(src_path), 'water-demo.nc')

DATES = ['2018-09-14T00:00:00', '2018-09-14T01:00:00',
         '2018-09-14T02:00:00', '2018-09-14T03:00:00',
         '2018-09-14T04:00:00', '2018-09-14T05:00:00',
         '2018-09-14T06:00:00', '2018-09-14T07:00:00',
         '2018-09-14T08:00:00', '2018-09-14T09:00:00',
         '2018-09-14T10:00:00', '2018-09-14T11:00:00',
         '2018-09-14T12:00:00', '2018-09-14T13:00:00',
         '2018-09-14T14:00:00', '2018-09-14T15:00:00',
         '2018-09-14T16:00:00', '2018-09-14T17:00:00',
         '2018-09-14T18:00:00', '2018-09-14T19:00:00',
         '2018-09-14T20:00:00',
         ]


# remove any existing path if it exists
if os.path.exists(out_path):
    os.remove(out_path)

# open dataset
ds_in = xr.open_dataset(src_path)

# map values to be on the hour
water_levels = ds_in['hs'].interp(time=DATES)

# create a new dataset with the hourly dates
ds_out = xr.Dataset({
    'water_level': xr.DataArray(water_levels, coords=[DATES, ds_in.latitude, ds_in.longitude], dims=["time", "lat", "lon"]),
})

print('Saving to {}'.format(out_path))

# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_path, format='NETCDF4_CLASSIC')
