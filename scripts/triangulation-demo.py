import json
import xarray as xr
import numpy as np
import geojson
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation

ds_original = xr.open_dataset('/home/danny/Desktop/cwwed/sandy/water-demo.nc')

# create a new dataset with one variable and the mesh connectivity
ds = xr.Dataset()
ds['water_level'] = ds_original.water_level[0]
ds['element'] = ds_original.element

# clip to small geo
# small atlantic city
#bottom_left = (39.28541975943743, -74.6136474609375)  # (y, x)
#top_right = (39.41922073655956, -74.3170166015625)  # (y, x)
bottom_left = (38.53957267203905, -75.66009521484375)
top_right = (39.91605629078665, -74.0753173828125)

z = ds.water_level.where(
    (ds.lon >= bottom_left[1]) &  # xmin
    (ds.lat >= bottom_left[0]) &  # ymin
    (ds.lon <= top_right[1]) &  # xmax
    (ds.lat <= top_right[0]),  # ymax
)

# create mask to remove triangles with null values
tri_mask = z[ds.element].isnull()
# single column result of whether all the points in each triangle/row are non-null
tri_mask = np.all(tri_mask, axis=1)

# create triangulation using mask
tri = Triangulation(ds.lon, ds.lat, ds.element, mask=tri_mask)

# save contour figure
contourf = plt.tricontourf(tri, z.fillna(0))
plt.savefig('/home/danny/Downloads/a.png')

# build triangle polygons
tri_coords = []
for triangle in tri.triangles[~tri_mask]:
    coord_indexes = np.append(triangle, [triangle[0]])  # include closing point of polygon
    tri_coords.append(
        np.column_stack([
            tri.x[coord_indexes],
            tri.y[coord_indexes],
        ]).tolist()
    )

multiple_polygon = geojson.MultiPolygon([tuple(tri_coords)])
json.dump(multiple_polygon, open('/home/danny/Downloads/a.json', 'w'))
