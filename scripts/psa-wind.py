import os
import xarray as xr
import numpy as np
import re


wind_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/anil'

ds_max = xr.Dataset()

for dataset_file in sorted(os.listdir(wind_path)):
    # must be like "wrfout_d01_2012-10-29_14_00.nc", i.e using "domain 1"
    match = re.match(r'wrfout_d01_(?P<date>\d{4}-\d{2}-\d{2}_\d{2}_\d{2}).nc', dataset_file)
    if match:
        # open dataset
        ds_current = xr.open_dataset(os.path.join(wind_path, dataset_file))

        # create new dataset with just the variables we want
        ds_updated = xr.Dataset({
            'spduv10max': ds_current['spduv10max'],
            'wspd10m': ds_current['wspd10m'],
            'wdir10m': ds_current['wdir10m'],
        })

        # fix cf conventions
        ds_updated['spduv10max'].attrs['standard_name'] = 'wind_speed'

        # save updated ds
        ds_updated.to_netcdf('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy-wind_{}.nc'.format(match['date']))

        # current max wind speed data array
        da = xr.DataArray(ds_updated['spduv10max'].isel(time=0))

        if 'wind_speed_max' not in ds_max:
            ds_max['wind_speed_max'] = da
        else:
            ds_max['wind_speed_max'] = np.maximum(ds_max['wind_speed_max'], da)

# save as netcdf classic because hyrax chokes on 64bit ints
ds_max.to_netcdf('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy-wind-max.nc', format='NETCDF4_CLASSIC')
