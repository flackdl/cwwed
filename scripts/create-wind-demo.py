import os
import xarray as xr
import re


src_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/florence/anil/'
out_path = os.path.join(os.path.dirname(src_path), 'wind-demo.nc')

# variables to keep from the datasets
VARIABLES = {'time', 'lat', 'lon', 'wspd10m', 'wdir10m', 'wspd10max'}

# remove any existing path if it exists
if os.path.exists(out_path):
    os.remove(out_path)

ds_out = xr.Dataset()

for dataset_file in sorted(os.listdir(src_path)):

    # must be like "wrfoutd01_2012-10-29_14_00.nc", i.e using "domain 1"
    if re.match(r'wrfoutd01_\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}.nc', dataset_file):

        # skip first since it doesn't have the gust available
        if dataset_file == 'wrfoutd01_2018-09-14_00:00:00.nc':
            continue

        print('Processing {}'.format(dataset_file))

        # open dataset
        ds_current = xr.open_dataset(os.path.join(src_path, dataset_file))

        # drop extraneous variables
        ds_current = ds_current.drop_vars(set(ds_current.variables).difference(VARIABLES))

        # rename variables
        ds_current = ds_current.rename_vars({
            'wspd10m': 'wind_speed',
            'wdir10m': 'wind_direction',
            'wspd10max': 'wind_gust',
        })

        # combine datasets
        ds_out = ds_out.combine_first(ds_current)

print('Saving to {}'.format(out_path))

# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_path, format='NETCDF4_CLASSIC')
