import math
import geojson
import xarray
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour
from geojson import MultiPolygon, Polygon


def circum_r(pa, pb, pc):
    """
    returns circum-circle radii of triangles
    """
    # Lengths of sides of triangle
    a = math.sqrt((pa[0]-pb[0])**2 + (pa[1]-pb[1])**2)
    b = math.sqrt((pb[0]-pc[0])**2 + (pb[1]-pc[1])**2)
    c = math.sqrt((pc[0]-pa[0])**2 + (pc[1]-pa[1])**2)

    # Semiperimeter of triangle
    s = (a + b + c)/2.0

    # Area of triangle by Heron's formula
    area = math.sqrt(s*(s-a)*(s-b)*(s-c))

    return a*b*c/(4.0*area)


GRID_SIZE = 1000  # make this less arbitrary
MAX_CIRCUM_RADIUS = .02

dataset = xarray.open_dataset('/media/bucket/cwwed/THREDDS/PSA_demo/Sandy_DBay/DBay-run_map.nc')

# data from a single point in time
depths = dataset['mesh2d_waterdepth'][0]

#z = depths[::20]  # make the point data less dense
z = depths
x = z.mesh2d_face_x
y = z.mesh2d_face_y

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

# filter out triangles (WIP)
bad_triangles = [i for i, t in enumerate(tri_coords) if circum_r(*t) > MAX_CIRCUM_RADIUS]
mask = [i in bad_triangles for i, _ in enumerate(triang.triangles)]
triang.set_mask(mask)

# interpolate values from triangle data and build a mesh of data
interpolator = tri.LinearTriInterpolator(triang, z)
Xi, Yi = np.meshgrid(xi, yi)
zi = interpolator(Xi, Yi)

# debug - save the triangulation as geojson
# TODO - factor in masked triangles
polygons = [Polygon(coords + (coords[0],)) for coords in tri_coords]  # append the first coord to complete the polygon
geojson.dump(MultiPolygon([polygons]), open('/tmp/geo.json', 'w'))

# plot
figure = plt.figure()
ax = figure.add_subplot(111)
contourf = ax.contourf(xi, yi, zi, cmap=plt.cm.jet)
plt.savefig('/tmp/a.png')

# convert matplotlib contourf to geojson
gjson = geojsoncontour.contourf_to_geojson(
    contourf=contourf,
    min_angle_deg=3.0,
    ndigits=3,
    stroke_width=2,
    fill_opacity=0.5,
    geojson_filepath='/tmp/a.json',
)
