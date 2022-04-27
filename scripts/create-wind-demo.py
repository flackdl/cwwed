import os
import xarray as xr
import re


# sandy
#base_path = '/media/bucket/cwwed/OPENDAP/psa-uploads/sandy/'
# florence
#base_path = '/media/bucket/cwwed/OPENDAP/psa-uploads/florence/'
# ida
base_path = '/media/bucket/cwwed/OPENDAP/psa-uploads/ida/'

src_path = os.path.join(base_path, 'anil')
out_full = os.path.join(base_path, 'wind-demo.nc')
out_minimal = os.path.join(base_path, 'wind-demo-minimal.nc')

# variables to keep from the datasets
VARIABLES_MAP = {
    'time': 'time',
    'lat': 'lat',
    'lon': 'lon',
    #'wspd10m': 'wind_speed',
    'wdir10m': 'wind_direction',
    ## florence
    #'wspd10max': 'wind_gust',
    'windgust_10m': 'wind_gust',
}

ds_out = xr.Dataset()

for dataset_file in sorted(os.listdir(src_path)):

    # must be like "wrfoutd01_*.00.nc", i.e using "domain 1" and on the hour "00"
    if re.match(r'wrfout_?d01_.*.00.nc', dataset_file):

        ## TODO - florence
        ## skip first since it doesn't have the gust available
        #if dataset_file == 'wrfoutd01_2018-09-14_00:00:00.nc':
        #    continue

        print('Processing {}'.format(dataset_file))

        # open dataset
        ds_current = xr.open_dataset(os.path.join(src_path, dataset_file))

        # drop extraneous variables
        ds_current = ds_current.drop_vars(set(ds_current.variables).difference(VARIABLES_MAP.keys()))

        # rename variables
        ds_current = ds_current.rename_vars(VARIABLES_MAP)

        # combine datasets
        ds_out = ds_out.combine_first(ds_current)

        # populate dataset and variable attributes
        if not ds_out.attrs:
            ds_out.attrs = ds_current.attrs
            for variable in VARIABLES_MAP.values():
                ds_out[variable].attrs = ds_current[variable].attrs

# satisfy CF conventions
ds_out['wind_gust'].attrs['standard_name'] = 'wind_speed'
ds_out.attrs['Conventions'] = 'CF-1.6'

# full
print('Saving to {}'.format(out_full))
# save as netcdf classic because hyrax chokes on 64bit ints
ds_out.to_netcdf(out_full, format='NETCDF4_CLASSIC')

# minimal
print('Saving minimal to {}'.format(out_minimal))
ds_out.isel(time=slice(0, 3)).to_netcdf(out_minimal, format='NETCDF4_CLASSIC')
