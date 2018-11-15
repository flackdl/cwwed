import math
import sys
from datetime import datetime
import xarray
from matplotlib import animation
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour
from matplotlib.animation import FFMpegWriter
from matplotlib.axes import Axes


# TODO - make these values less arbitrary by analyzing the input data density and spatial coverage
GRID_SIZE = 1000
MAX_CIRCUM_RADIUS = .015  # ~ 1 mile
LEVELS = 30


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


def build_geojson_contours(data, ax: Axes):

    ax.clear()

    z = data
    x = z.mesh2d_face_x[:len(z)]
    y = z.mesh2d_face_y[:len(z)]

    # capture date and convert to datetime
    dt = datetime64_to_datetime(z.time)

    # set title on figure
    ax.set_title(dt.isoformat())

    # build json file name output
    file_name = '{}__{}'.format(z.name, dt.isoformat())

    # convert to numpy arrays
    z = z.values
    x = x.values
    y = y.values

    # build grid constraints
    xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
    yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

    # build delaunay triangles
    triang = tri.Triangulation(x, y)

    # build a list of the triangle coordinates
    tri_coords = []
    for i in range(len(triang.triangles)):
        tri_coords.append(tuple(zip(x[triang.triangles[i]], y[triang.triangles[i]])))

    # filter out large triangles
    large_triangles = [i for i, t in enumerate(tri_coords) if circum_radius(*t) > MAX_CIRCUM_RADIUS]
    mask = [i in large_triangles for i, _ in enumerate(triang.triangles)]
    triang.set_mask(mask)

    # interpolate values from triangle data and build a mesh of data
    interpolator = tri.LinearTriInterpolator(triang, z)
    Xi, Yi = np.meshgrid(xi, yi)
    zi = interpolator(Xi, Yi)

    contourf = ax.contourf(xi, yi, zi, LEVELS, cmap=plt.cm.jet)

    # convert matplotlib contourf to geojson
    geojsoncontour.contourf_to_geojson(
        contourf=contourf,
        min_angle_deg=3.0,
        ndigits=5,
        stroke_width=2,
        fill_opacity=0.5,
        geojson_filepath='/tmp/{}.json'.format(file_name),
    )

    return contourf


if __name__ == '__main__':

    dataset_path = sys.argv[1] if len(sys.argv) > 1 else '/media/bucket/cwwed/THREDDS/PSA_demo/Sandy_DBay/DBay-run_map.nc'

    # open the dataset
    dataset = xarray.open_dataset(dataset_path)

    fig, ax = plt.subplots()

    variables = ['mesh2d_waterdepth', 'mesh2d_windx', 'mesh2d_windy']

    for variable in variables:

        print(variable)

        # build geojson outputs and video animation over time series
        anim = animation.FuncAnimation(
            fig,
            build_geojson_contours,
            frames=dataset[variable],
            fargs=[ax],
        )
        anim.save('/tmp/{}.mp4'.format(variable), writer=FFMpegWriter())
