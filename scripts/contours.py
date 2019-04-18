import os
import gzip
import json
import math
from datetime import datetime
import xarray
import geojson
import matplotlib
from matplotlib import cm, colors
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour
from typing import Callable
from shapely.geometry import Polygon, Point


# TODO - make these values less arbitrary by analyzing the input data density and spatial coverage

GRID_SIZE = 5000
LEVELS = 30

# color bar range
COLOR_STEPS = 10


# atlantic coast
GEO_POLY = Polygon([
    [-77.1240234375, 33.97980872872457],
    [-75.0146484375, 35.24561909420681],
    [-75.4541015625, 37.09023980307208],
    [-74.0478515625, 38.8225909761771],
    [-72.3779296875, 39.977120098439634],
    [-70.224609375, 40.91351257612758],
    [-70.048828125, 42.68243539838623],
    [-74.6630859375, 41.83682786072714],
    [-78.1787109375, 38.89103282648846],
    [-77.607421875, 36.35052700542763],
    [-77.1240234375, 33.97980872872457],
])


def datetime64_to_datetime(dt64):
    unix_epoch = np.datetime64(0, 's')
    one_second = np.timedelta64(1, 's')
    seconds_since_epoch = (dt64 - unix_epoch) / one_second
    return datetime.utcfromtimestamp(seconds_since_epoch)


def build_contours(z: xarray.DataArray, xi: np.ndarray, yi: np.ndarray, triangulation: tri.Triangulation, dt: datetime, cmap: matplotlib.colors.Colormap, mask_geojson: Callable = None):

    # build json file name output
    file_name = '{}.json'.format(dt.isoformat())

    variable_name = z.name

    # interpolate values from triangle data and build a mesh of data
    interpolator = tri.LinearTriInterpolator(triangulation, z)
    Xi, Yi = np.meshgrid(xi, yi)
    zi = interpolator(Xi, Yi)

    # create the contour
    contourf = plt.contourf(xi, yi, zi, LEVELS, cmap=cmap)

    # convert matplotlib contourf to geojson
    geojson_result = json.loads(geojsoncontour.contourf_to_geojson(
        contourf=contourf,
        ndigits=10,
        stroke_width=2,
        fill_opacity=0.5,
        geojson_properties={'variable': variable_name},
    ))

    # mask regions
    if mask_geojson is not None:
        mask_geojson(geojson_result)

    # create output directory if it doesn't exist
    output_path = '/tmp/{}'.format(variable_name)
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # gzip compress geojson output and save to file
    with gzip.GzipFile(os.path.join(output_path, file_name), 'w') as fh:
        fh.write(json.dumps(geojson_result).encode('utf-8'))

    #
    # build color values
    #

    color_values = []

    color_norm = matplotlib.colors.Normalize(vmin=z.min(), vmax=z.max())
    step_intervals = np.linspace(z.min(), z.max(), COLOR_STEPS)

    for step_value in step_intervals:
        # round the step value for ranges greater than COLOR_STEPS
        if z.max() - z.min() >= COLOR_STEPS:
            step_value = math.ceil(step_value)
        hex_value = matplotlib.colors.to_hex(cmap(color_norm(step_value)))
        color_values.append((step_value, hex_value))

    #
    # return manifest entry
    #

    return {
        'date': dt.isoformat(),
        'path': os.path.join(variable_name, file_name),
        'color_bar': color_values,
    }


def build_wind_barbs(x: np.ndarray, y: np.ndarray, wind_speeds: np.ndarray, wind_directions: np.ndarray, dt: datetime):

    coords = np.column_stack([x, y])
    points = [geojson.Point(coord.tolist()) for idx, coord in enumerate(coords)]
    features = [geojson.Feature(geometry=wind_point, properties={'speed': wind_speeds[idx].item(), 'direction': wind_directions[idx].item()}) for idx, wind_point in enumerate(points)]
    wind_geojson = geojson.FeatureCollection(features=features)

    # create output directory if it doesn't exist
    output_path = '/tmp/wind_barbs'
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    file_name = '{}.json'.format(dt.isoformat())

    # gzip compress geojson output and save to file
    with gzip.GzipFile(os.path.join(output_path, file_name), 'w') as fh:
        fh.write(json.dumps(wind_geojson).encode('utf-8'))

    # update manifest
    return {
        'date': dt.isoformat(),
        'path': os.path.join('wind_barbs', file_name),
    }


def water_level_mask_geojson(geojson_result: dict):
    # mask values not greater than zero
    for feature in geojson_result['features'][:]:
        if float(feature['properties']['title']) <= 0:
            geojson_result['features'].remove(feature)


def main():

    manifest = {}

    #
    # wave height
    #

    dataset = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc')
    cmap = matplotlib.cm.get_cmap('jet')
    manifest['hs'] = {'geojson': []}

    # subset geo
    coords = np.column_stack((dataset.longitude, dataset.latitude))
    mask = np.array([Point(coord).within(GEO_POLY) for coord in coords])

    x = dataset.longitude[mask]
    y = dataset.latitude[mask]

    # build delaunay triangles
    triangulation = tri.Triangulation(x, y)

    # build grid constraints
    xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
    yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

    for z in dataset['hs']:

        z = z[mask]

        # capture date and convert to datetime
        dt = datetime64_to_datetime(z.time)

        manifest_entry = build_contours(z, xi, yi, triangulation, dt, cmap, mask_geojson=water_level_mask_geojson)
        manifest['hs']['geojson'].append(manifest_entry)

    #
    # water level
    #

    dataset = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/fort.63.nc', drop_variables=('max_nvdll', 'max_nvell'))
    cmap = matplotlib.cm.get_cmap('jet')
    manifest['zeta'] = {'geojson': []}

    # subset geo
    coords = np.column_stack((dataset.x, dataset.y))
    mask = np.array([Point(coord).within(GEO_POLY) for coord in coords])

    x = dataset.x[mask]
    y = dataset.y[mask]

    # build delaunay triangles
    triangulation = tri.Triangulation(x, y)

    # build grid constraints
    xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
    yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

    for z in dataset['zeta']:

        # capture date and convert to datetime
        dt = datetime64_to_datetime(z.time)

        z = z[mask]

        manifest_entry = build_contours(z, xi, yi, triangulation, dt, cmap, mask_geojson=water_level_mask_geojson)
        manifest['zeta']['geojson'].append(manifest_entry)

    #
    # maximum water level
    #

    dataset = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/maxele.63.nc', drop_variables=('max_nvdll', 'max_nvell'))
    cmap = matplotlib.cm.get_cmap('jet')
    manifest['water_level_max'] = {'geojson': []}

    coords = np.column_stack((dataset.x, dataset.y))
    mask = np.array([Point(coord).within(GEO_POLY) for coord in coords])

    z = dataset['zeta_max'][mask]
    x = dataset.x[mask]
    y = dataset.y[mask]

    # build delaunay triangles
    triangulation = tri.Triangulation(x, y)

    # build grid constraints
    xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
    yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

    # arbitrary datetime placeholder since it's a "maximum level" across the duration of the hurricane
    datetime_placeholder = datetime(2012, 10, 30)

    manifest_entry = build_contours(z, xi, yi, triangulation, datetime_placeholder, cmap)
    manifest['water_level_max']['geojson'].append(manifest_entry)

    #
    # wind
    #

    dataset = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_wnd.nc')
    manifest['wind'] = {'geojson': []}
    manifest['wind_barbs'] = {'geojson': []}

    for date in dataset['time']:

        # capture date and convert to datetime
        dt = datetime64_to_datetime(date)

        # NaN mask
        nan_mask = (~np.isnan(dataset.sel(time=date)['uwnd'])) & (~np.isnan(dataset.sel(time=date)['vwnd']))

        # geo mask
        coords = np.column_stack((dataset.longitude, dataset.latitude))
        geo_mask = np.array([Point(coord).within(GEO_POLY) for coord in coords])

        mask = nan_mask & geo_mask

        # mask and get a subset of data points since we don't want to display a wind barb at every point
        windx_values = dataset.sel(time=date)['uwnd'][mask][::100].values
        windy_values = dataset.sel(time=date)['vwnd'][mask][::100].values
        x = dataset.longitude[mask][::100].values
        y = dataset.latitude[mask][::100].values

        wind_speeds = np.abs(np.hypot(windx_values, windy_values))
        wind_directions = np.arctan2(windx_values, windy_values)

        #
        # barbs
        #

        manifest['wind_barbs']['geojson'].append(build_wind_barbs(x, y, wind_speeds, wind_directions, dt))

        #
        # contours
        #

        cmap = matplotlib.cm.get_cmap('jet')

        # build delaunay triangles
        triangulation = tri.Triangulation(x, y)

        # build grid constraints
        xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
        yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

        wind_speeds_data_array = xarray.DataArray(wind_speeds, name='wind')

        manifest['wind']['geojson'].append(build_contours(wind_speeds_data_array, xi, yi, triangulation, dt, cmap))

    #
    # write manifest
    #

    json.dump(manifest, open('/tmp/manifest.json', 'w'))


if __name__ == '__main__':
    main()
