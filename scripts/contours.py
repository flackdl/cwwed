import os
import gzip
import json
import math
import sys
from datetime import datetime
import xarray
from geojson import Point, Feature, FeatureCollection
import matplotlib
from matplotlib import cm, colors
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour
from typing import Callable


# TODO - make these values less arbitrary by analyzing the input data density and spatial coverage
GRID_SIZE = 1000
MAX_CIRCUM_RADIUS = .015  # ~ 1 mile
LEVELS = 30

# color bar range
COLOR_STEPS = 10


def datetime64_to_datetime(dt64):
    unix_epoch = np.datetime64(0, 's')
    one_second = np.timedelta64(1, 's')
    seconds_since_epoch = (dt64 - unix_epoch) / one_second
    return datetime.utcfromtimestamp(seconds_since_epoch)


def circum_radius(pa, pb, pc):
    """
    returns circum-circle radius of triangle
    https://sgillies.net/2012/10/13/the-fading-shape-of-alpha.html
    https://en.wikipedia.org/wiki/Circumscribed_circle#/media/File:Circumcenter_Construction.svg
    """
    # lengths of sides of triangle
    a = math.sqrt((pa[0]-pb[0])**2 + (pa[1]-pb[1])**2)
    b = math.sqrt((pb[0]-pc[0])**2 + (pb[1]-pc[1])**2)
    c = math.sqrt((pc[0]-pa[0])**2 + (pc[1]-pa[1])**2)

    # semiperimeter of triangle
    s = (a + b + c)/2.0

    # area of triangle by Heron's formula
    area = math.sqrt(s*(s-a)*(s-b)*(s-c))

    return a*b*c/(4.0*area)


def build_contours(z: xarray.DataArray, x: xarray.DataArray, y: xarray.DataArray, cmap: matplotlib.colors.Colormap, mask_geojson: Callable = None):

    # capture date and convert to datetime
    dt = datetime64_to_datetime(z.time)

    # build json file name output
    file_name = '{}.json'.format(dt.isoformat())

    variable_name = z.name

    # build delaunay triangles
    triang = tri.Triangulation(x, y)

    # build grid constraints
    xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
    yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

    # interpolate values from triangle data and build a mesh of data
    interpolator = tri.LinearTriInterpolator(triang, z)
    Xi, Yi = np.meshgrid(xi, yi)
    zi = interpolator(Xi, Yi)

    # create the contour
    contourf = plt.contourf(xi, yi, zi, LEVELS, cmap=cmap)

    # convert matplotlib contourf to geojson
    geojson_result = json.loads(geojsoncontour.contourf_to_geojson(
        contourf=contourf,
        min_angle_deg=0,
        ndigits=5,
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


def build_wind_barbs(date: xarray.DataArray, ds: xarray.Dataset):

    # capture date and convert to datetime
    dt = datetime64_to_datetime(date)

    #
    # plot barbs
    #

    # get a subset of data points since we don't want to display a wind barb at every point
    windx_values = ds.sel(time=date)['mesh2d_windx'][::100].values
    windy_values = ds.sel(time=date)['mesh2d_windy'][::100].values
    facex_values = ds.mesh2d_face_x[::100].values
    facey_values = ds.mesh2d_face_y[::100].values

    plt.barbs(facex_values, facey_values, windx_values, windy_values)

    #
    # generate geojson
    #

    wind_speeds = np.abs(np.hypot(windx_values, windy_values))
    wind_directions = np.arctan2(windx_values, windy_values)
    coords = np.column_stack([facex_values, facey_values])
    points = [Point(coord.tolist()) for idx, coord in enumerate(coords)]
    features = [Feature(geometry=wind_point, properties={'speed': wind_speeds[idx], 'direction': wind_directions[idx]}) for idx, wind_point in enumerate(points)]
    wind_geojson = FeatureCollection(features=features)

    # create output directory if it doesn't exist
    output_path = '/tmp/wind'
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    file_name = '{}.json'.format(dt.isoformat())

    # gzip compress geojson output and save to file
    with gzip.GzipFile(os.path.join(output_path, file_name), 'w') as fh:
        fh.write(json.dumps(wind_geojson).encode('utf-8'))

    # update manifest
    return {
        'date': dt.isoformat(),
        'path': os.path.join('wind', file_name),
    }


def water_level_mask_geojson(geojson_result: dict):
    # mask values not greater than zero
    for feature in geojson_result['features'][:]:
        if float(feature['properties']['title']) <= 0:
            geojson_result['features'].remove(feature)


def main():

    # open the dataset
    dataset_path = sys.argv[1] if len(sys.argv) > 1 else '/media/bucket/cwwed/OPENDAP/PSA_demo/Sandy_DBay/DBay-run_map.nc'
    #dataset = xarray.open_dataset(dataset_path)
    dataset = xarray.open_dataset(dataset_path, drop_variables=('max_nvdll', 'max_nvell'))

    manifest = {}

    #
    # contours
    #

    # wave height
    cmap = matplotlib.cm.get_cmap('jet')
    manifest['hs'] = {'geojson': []}
    for z in dataset['hs']:
        print(z.time.values)
        x = dataset.longitude
        y = dataset.latitude
        manifest_entry = build_contours(z, x, y, cmap, mask_geojson=water_level_mask_geojson)
        manifest['hs']['geojson'].append(manifest_entry)

    ## inundation
    #cmap = matplotlib.cm.get_cmap('jet')
    #manifest['zeta'] = {'geojson': []}
    #for z in dataset['zeta']:
    #    x = z.x
    #    y = z.y
    #    manifest_entry = build_contours(z, x, y, cmap, mask_geojson=water_level_mask_geojson)
    #    manifest['zeta']['geojson'].append(manifest_entry)

    ## water depth
    #manifest['mesh2d_waterdepth'] = {'geojson': []}
    #cmap = matplotlib.cm.get_cmap('Blues')
    #for z in dataset['mesh2d_waterdepth']:
    #    x = z.mesh2d_face_x
    #    y = z.mesh2d_face_y
    #    manifest_entry = build_contours(z, x, y, cmap)
    #    manifest['mesh2d_waterdepth']['geojson'].append(manifest_entry)

    ## sea surface
    #cmap = matplotlib.cm.get_cmap('jet')
    #manifest['mesh2d_s1'] = {'geojson': []}
    #for z in dataset['mesh2d_s1']:
    #    x = z.mesh2d_face_x
    #    y = z.mesh2d_face_y
    #    manifest_entry = build_contours(z, x, y, cmap, mask_geojson=water_level_mask_geojson)
    #    manifest['mesh2d_s1']['geojson'].append(manifest_entry)

    #
    # wind velocity
    #

    #manifest['wind'] = {'geojson': []}
    #for data in dataset['time']:
    #    manifest['wind']['geojson'].append(build_wind_barbs(data, dataset))

    #
    # write manifest
    #

    json.dump(manifest, open('/tmp/manifest.json', 'w'))


if __name__ == '__main__':
    main()
