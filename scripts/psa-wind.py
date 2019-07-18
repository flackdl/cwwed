import os
import xarray as xr
import numpy as np
import re


wind_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/anil'

ds = xr.Dataset()

for dataset_file in sorted(os.listdir(wind_path)):
    # must be like "wrfout_d01_2012-10-29_14_00.nc", i.e using "domain 1"
    if re.match(r'wrfout_d01_\d{4}-\d{2}-\d{2}_\d{2}_\d{2}.nc', dataset_file):

        # open dataset
        ds_current = xr.open_dataset(os.path.join(wind_path, dataset_file))

        # current max wind speed data array
        da = xr.DataArray(ds_current.spduv10max.isel(time=0))

        if 'wind_speed_max' not in ds:
            ds['wind_speed_max'] = da
        else:
            ds['wind_speed_max'] = np.maximum(ds['wind_speed_max'], da)

# save as netcdf classic because hyrax chokes on 64bit ints
ds.to_netcdf('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy-wind-max.nc', format='NETCDF4_CLASSIC')
