import xarray
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour

dataset = xarray.open_dataset('/media/bucket/cwwed/THREDDS/PSA_demo/Sandy_DBay/DBay-run_map.nc')

depths = dataset['mesh2d_waterdepth'][0]

z = depths[::20][:2000]
x = z.mesh2d_face_x
y = z.mesh2d_face_y

xi = np.linspace(-76, -74, 2000)
yi = np.linspace(38, 41, 2000)

triang = tri.Triangulation(x, y)
interpolator = tri.LinearTriInterpolator(triang, z)
Xi, Yi = np.meshgrid(xi, yi)
zi = interpolator(Xi, Yi)

figure = plt.figure()
ax = figure.add_subplot(111)
contourf = ax.contourf(xi, yi, zi, cmap=plt.cm.jet)

# Convert matplotlib contourf to geojson
gjson = geojsoncontour.contourf_to_geojson(
    contourf=contourf,
    min_angle_deg=3.0,
    ndigits=3,
    stroke_width=2,
    fill_opacity=0.5,
    geojson_filepath='/tmp/a.json',
)
