import os
import numpy
import xarray as xr
from scipy import spatial
from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import views, exceptions
from rest_framework.response import Response


class PSAFilterView(views.APIView):

    def get(self, request):
        path_prefix = os.path.join(settings.CWWED_DATA_DIR, settings.CWWED_OPENDAP_DIR)

        water_level_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/fort.63.nc'
        wind_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_wnd.nc'
        wave_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc'

        coordinate = request.GET.getlist('coordinate')
        if not coordinate or not len(coordinate) == 2:
            raise exceptions.NotFound('Coordinate (2) not supplied')
        try:
            coordinate = tuple(map(float, coordinate))
        except ValueError:
            raise exceptions.NotFound('Coordinate should be floats')

        #
        # water level
        #

        dataset_water_level = xr.open_dataset(os.path.join(path_prefix, water_level_dataset_path), drop_variables=('max_nvdll', 'max_nvell'))
        water_levels = []
        nearest_index = self._nearest_node_index(dataset_water_level.y, dataset_water_level.x, coordinate)
        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')
        for data in dataset_water_level.zeta:
            data_date = parse_datetime(str(data.time.values))
            water_levels.append({
                'name': data_date.isoformat(),
                'value': data[nearest_index].values,
            })

        #
        # wave height
        #

        dataset_wave_height = xr.open_dataset(os.path.join(path_prefix, wave_dataset_path))
        wave_heights = []
        nearest_index = self._nearest_node_index(dataset_wave_height.latitude, dataset_wave_height.longitude, coordinate)
        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')
        for data in dataset_wave_height.hs:
            data_date = parse_datetime(str(data.time.values))
            wave_heights.append({
                'name': data_date.isoformat(),
                'value': data[nearest_index].values,
            })

        #
        # wind
        #

        dataset_wind = xr.open_dataset(os.path.join(path_prefix, wind_dataset_path))
        wind_speeds = []
        nearest_index = self._nearest_node_index(dataset_wind.latitude, dataset_wind.longitude, coordinate)
        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')
        for idx, data_windx in enumerate(dataset_wind.uwnd):  # arbitrarily using u component as it's symmetrical with the v component
            speeds = numpy.arctan2(
                numpy.abs(data_windx[nearest_index].values),
                numpy.abs(dataset_wind['vwnd'][idx][nearest_index].values),
            )
            data_date = parse_datetime(str(data_windx.time.values))
            wind_speeds.append({
                'name': data_date.isoformat(),
                'value': speeds,
            })

        response = Response({
            'water_level': water_levels,
            'wave_height': wave_heights,
            'wind_speed': wind_speeds,
        })

        return response

    @staticmethod
    def _nearest_node_index(x: xr.DataArray, y: xr.DataArray, point: tuple):
        coords = numpy.column_stack([y, x])
        nearest = coords[spatial.KDTree(coords).query(point)[1]]
        found = numpy.where(coords == nearest)
        if found and found[0].any():
            return found[0][0]
        return None

