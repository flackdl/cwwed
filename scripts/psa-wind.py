import os
import xarray as xr
import numpy as np
import re


path_root = '/media/bucket/cwwed/OPENDAP/PSA_demo'
wind_path = os.path.join(path_root, 'anil')

datasets = []
ds_max = xr.Dataset()

for dataset_file in sorted(os.listdir(wind_path)):
    # must be like "wrfout_d01_2012-10-29_14_00.nc", i.e using "domain 1"
    match = re.match(r'wrfout_d01_(?P<date>\d{4}-\d{2}-\d{2}_\d{2}_\d{2}).nc', dataset_file)
    if match:
        # open dataset
        ds_current = xr.open_dataset(os.path.join(wind_path, dataset_file))

        # create new dataset with just the variables we want
        ds_updated = xr.Dataset({
            'wind_speed_max': ds_current['spduv10max'],
            'wind_speed': ds_current['wspd10m'],
            'wind_direction': ds_current['wdir10m'],
        })

        # fix cf conventions
        ds_updated['wind_speed_max'].attrs['standard_name'] = 'wind_speed'

        datasets.append(ds_updated)

        # current max wind speed data array
        da = xr.DataArray(ds_updated['wind_speed_max'].isel(time=0))

        if 'wind_speed_max' not in ds_max:
            ds_max['wind_speed_max'] = da
        else:
            ds_max['wind_speed_max'] = np.maximum(ds_max['wind_speed_max'], da)


# save netcdf's in classic format because hyrax/opendap chokes on 64bit ints

# save max ds
ds_max.to_netcdf(os.path.join(path_root, 'sandy-wind-max.nc'), format='NETCDF4_CLASSIC')

# save combined ds
ds_combined = xr.concat(datasets, 'time')  # type: xr.Dataset
ds_combined.to_netcdf(os.path.join(path_root, 'sandy-wind-combined.nc'), format='NETCDF4_CLASSIC')

# save a two-day psa demo
ds_demo = xr.concat([ds_combined.isel(time=1), ds_combined.isel(time=2)], 'time')  # type: xr.Dataset
ds_demo.to_netcdf(os.path.join(path_root, 'sandy-wind-demo.nc'), format='NETCDF4_CLASSIC')
