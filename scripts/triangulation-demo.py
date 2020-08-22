import json
import xarray as xr
import numpy as np
import geojson
from matplotlib.tri import Triangulation

ds = xr.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy/WW3/adcirc/fort.63.nc', drop_variables=['max_nvdll', 'max_nvell'])
# filter to single date and zeta variable
ds = ds.zeta[0].to_dataset()

# y, x
# large
bottom_left = (33.215177641346756, -79.20178761268342)
top_right = (35.24061087693086, -76.23547901893342)

ds = ds.where(
    (ds.x >= bottom_left[1]) &  # xmin
    (ds.y >= bottom_left[0]) &  # ymin
    (ds.x <= top_right[1]) &  # xmax
    (ds.y <= top_right[0]),  # ymax
    drop=True)

null_mask = ds.zeta.isnull()
tri = Triangulation(ds.x[~null_mask], ds.y[~null_mask])
tri_coords = []
for triangles in tri.triangles:
    coords_idx = np.append(triangles, [triangles[0]])  # include closing point of polygon
    tri_coords.append(
        np.column_stack([
            tri.x[coords_idx],
            tri.y[coords_idx],
        ]).tolist()
    )

multiple_polygon = geojson.MultiPolygon([tri_coords])
json.dump(multiple_polygon, open('/home/danny/Downloads/a.json', 'w'))
#feature = geojson.Feature(geometry=multiple_polygon)
#feature_collection = geojson.FeatureCollection(features=[feature])
#json.dump(feature_collection, open('/home/danny/Downloads/a.json', 'w'))
