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
        dataset_path = request.GET.get('dataset_path', '')
        absolute_path = os.path.join(settings.CWWED_DATA_DIR, settings.CWWED_OPENDAP_DIR, dataset_path)
        coordinate = request.GET.getlist('coordinate')
        if not absolute_path or not os.path.exists(absolute_path):
            raise exceptions.NotFound('Dataset Path does not exist: {}'.format(absolute_path))
        elif not coordinate or not len(coordinate) == 2:
            raise exceptions.NotFound('Coordinate (2) not supplied')
        try:
            coordinate = tuple(map(float, coordinate))
        except ValueError:
            raise exceptions.NotFound('Coordinate should be floats')

        self._dataset = xr.open_dataset(absolute_path)

        nearest_index = self._nearest_node_index(coordinate)

        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')

        depths = []
        for data in self._dataset.mesh2d_waterdepth:
            # afaik you shouldn't have to manually call load() but it throws an exception otherwise
            data.load()
            data_date = parse_datetime(str(data.time.values))
            depths.append({
                'name': data_date.isoformat(),
                'value': data[nearest_index].values,
            })

        wind_speeds = []
        for idx, data_windx in enumerate(self._dataset.mesh2d_windx):  # arbitrarily using windx as it's symmetrical with windy
            speeds = numpy.arctan2(
                data_windx[nearest_index].values,
                self._dataset['mesh2d_windy'][idx][nearest_index].values,
            )
            data_date = parse_datetime(str(data_windx.time.values))
            wind_speeds.append({
                'name': data_date.isoformat(),
                'value': speeds,
            })

        response = Response({
            'water_depth': depths,
            'wind_speed': wind_speeds,
        })

        return response

    def _nearest_node_index(self, point: tuple):
        coords = numpy.column_stack([self._dataset.nmesh2d_face.mesh2d_face_y, self._dataset.nmesh2d_face.mesh2d_face_x])
        nearest = coords[spatial.KDTree(coords).query(point)[1]]
        found = numpy.where(coords == nearest)
        if found and found[0].any():
            return found[0][0]
        return None

