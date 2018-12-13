import os
import numpy
import xarray as xr
from scipy import spatial
from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import views, exceptions
from rest_framework.response import Response


class PSAFilterView(views.APIView):

    _dataset: xr.Dataset = None

    def get(self, request):
        path = request.GET.get('path')
        absolute_path = os.path.join(settings.CWWED_DATA_DIR, settings.CWWED_OPENDAP_DIR, path)
        coordinate = request.GET.getlist('coordinate')
        coordinate = coordinate[1], coordinate[0]  # swap to lat, lon
        if not absolute_path or not os.path.exists(absolute_path):
            raise exceptions.NotFound('Path does not exist: {}'.format(absolute_path))
        elif not coordinate or not len(coordinate) == 2:
            raise exceptions.NotFound('Coordinate (2) not supplied')
        try:
            coordinate = tuple(map(float, coordinate))
        except ValueError:
            raise exceptions.NotFound('Coordinate should be floats')

        self._dataset = xr.open_dataset(absolute_path)
        depths = []

        nearest_index = self._nearest_node_index(coordinate)

        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')

        for data in self._dataset.mesh2d_waterdepth:
            # afaik you shouldn't have to manually call load() but it throws an exception otherwise
            data.load()
            depth_date = parse_datetime(str(data.time.values))
            depths.append({
                'name': depth_date.isoformat(),
                'series': data[nearest_index].values,
            })

        response = Response({
            'water_depth': depths,
        })

        return response

    def _nearest_node_index(self, point: tuple):
        coords = numpy.column_stack([self._dataset.nmesh2d_face.mesh2d_face_x, self._dataset.nmesh2d_face.mesh2d_face_y])
        nearest = coords[spatial.KDTree(coords).query(point)[1]]
        found = numpy.where(coords == nearest)
        if found and found[0].any():
            return found[0][0]
        return None

