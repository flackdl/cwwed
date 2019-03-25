import math
import xarray
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import matplotlib.cm
import matplotlib.colors
import geojsoncontour
import numpy as np
import json

GRID_SIZE = 1000
LEVELS = 30
COLOR_STEPS = 10


ds = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/fort.63.nc', drop_variables=('max_nvdll', 'max_nvell'))

z = ds.zeta[0]
z = z[(z.x >= -75.937) & (z.x <= -74.443) & (z.y >= 38.397) & (z.y <= 39.753)]
x = z.x
y = z.y

triang = tri.Triangulation(z.x, z.y)

xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)
interpolator = tri.LinearTriInterpolator(triang, z)
Xi, Yi = np.meshgrid(xi, yi)
zi = interpolator(Xi, Yi)

cmap = matplotlib.cm.get_cmap('jet')

contourf = plt.contourf(xi, yi, zi, LEVELS, cmap=cmap)

geojson = json.loads(geojsoncontour.contourf_to_geojson(
    contourf=contourf,
    stroke_width=2,
    fill_opacity=0.5,
))

color_values = []

color_norm = matplotlib.colors.Normalize(vmin=z.min(), vmax=z.max())
step_intervals = np.linspace(z.min(), z.max(), COLOR_STEPS)

for step_value in step_intervals:
    # round the step value for ranges greater than COLOR_STEPS
    if z.max() - z.min() >= COLOR_STEPS:
        step_value = math.ceil(step_value)
    hex_value = matplotlib.colors.to_hex(cmap(color_norm(step_value)))
    color_values.append((step_value, hex_value))

print(color_values)

json.dump(geojson, open('/tmp/a.json', 'w'))
