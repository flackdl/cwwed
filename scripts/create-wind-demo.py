import os
import xarray as xr
import re


base_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/sandy/'
src_path = os.path.join(base_path, 'anil')
#src_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/florence/anil/'
out_full = os.path.join(base_path, 'wind-demo.nc')
out_minimal = os.path.join(base_path, 'wind-demo-minimal.nc')

# variables to keep from the datasets
VARIABLES = {'time', 'lat', 'lon', 'wspd10m', 'wdir10m'}
# TODO - florence
#VARIABLES = {'time', 'lat', 'lon', 'wspd10m', 'wdir10m', 'wspd10max'}

ds_out = xr.Dataset()

for dataset_file in sorted(os.listdir(src_path)):

    # must be like "wrfoutd01_*.nc", i.e using "domain 1"
    if re.match(r'wrfout_?d01_.*.nc', dataset_file):

        # TODO - florence
        # skip first since it doesn't have the gust available
        #if dataset_file == 'wrfoutd01_2018-09-14_00:00:00.nc':
        #    continue

        print('Processing {}'.format(dataset_file))

        # open dataset
        ds_current = xr.open_dataset(os.path.join(src_path, dataset_file))

        # drop extraneous variables
        ds_current = ds_current.drop_vars(set(ds_current.variables).difference(VARIABLES))

        # rename variables
        ds_current = ds_current.rename_vars({
            'wspd10m': 'wind_speed',
            'wdir10m': 'wind_direction',
            # TODO - florence
            #'wspd10max': 'wind_gust',
        })

        # combine datasets
        ds_out = ds_out.combine_first(ds_current)

# full
print('Saving to {}'.format(out_full))
# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_full, format='NETCDF4_CLASSIC')

# minimal
print('Saving minimal to {}'.format(out_minimal))
ds_out.isel(time=slice(0, 3)).to_netcdf(out_minimal, format='NETCDF4_CLASSIC')
