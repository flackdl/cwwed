import xarray
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour

GRID_SIZE = 1000  # make this less arbitrary

dataset = xarray.open_dataset('/media/bucket/cwwed/THREDDS/PSA_demo/Sandy_DBay/DBay-run_map.nc')

depths = dataset['mesh2d_waterdepth'][0]

z = depths[::20]
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

# filter out triangles (WIP)
#mask = x[triang.triangles].max(axis=1) - x[triang.triangles].min(axis=1) > .03
#triang.set_mask(mask)

# interpolate values from triangle data and build a mesh of data
interpolator = tri.LinearTriInterpolator(triang, z)
Xi, Yi = np.meshgrid(xi, yi)
zi = interpolator(Xi, Yi)

# plot
figure = plt.figure()
ax = figure.add_subplot(111)
contourf = ax.contourf(xi, yi, zi, cmap=plt.cm.jet)

# convert matplotlib contourf to geojson
gjson = geojsoncontour.contourf_to_geojson(
    contourf=contourf,
    min_angle_deg=3.0,
    ndigits=3,
    stroke_width=2,
    fill_opacity=0.5,
    geojson_filepath='/tmp/a.json',
)
