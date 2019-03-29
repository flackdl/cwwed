import os
import numpy
import time
import logging
import xarray as xr
from scipy import spatial
from django.conf import settings
from django.utils.dateparse import parse_datetime
from rest_framework import views, exceptions
from rest_framework.response import Response


class PSAFilterView(views.APIView):

    def get(self, request):

        coordinate = request.GET.getlist('coordinate')
        if not coordinate or not len(coordinate) == 2:
            raise exceptions.NotFound('Coordinate (2) not supplied')
        try:
            coordinate = tuple(map(float, coordinate))
        except ValueError:
            raise exceptions.NotFound('Coordinate should be floats')

        water_level_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/adcirc/fort.63.nc'
        wind_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_wnd.nc'
        wave_dataset_path = '/media/bucket/cwwed/OPENDAP/PSA_demo/WW3/wave-side/ww3.ExplicitCD.2012_hs.nc'

        path_prefix = os.path.join(settings.CWWED_DATA_DIR, settings.CWWED_OPENDAP_DIR)

        dataset_water_level = xr.open_dataset(os.path.join(path_prefix, water_level_dataset_path), drop_variables=('max_nvdll', 'max_nvell'))
        dataset_wave_height = xr.open_dataset(os.path.join(path_prefix, wave_dataset_path))
        dataset_wind = xr.open_dataset(os.path.join(path_prefix, wind_dataset_path))

        now = time.time()

        # TODO - using the same mask and "nearest_index" since the datasets so far are identical in the geographic areas they consume
        xmask = (dataset_water_level.x <= coordinate[1] + .5) & (dataset_water_level.x >= coordinate[1] - .5)
        ymask = (dataset_water_level.y <= coordinate[0] + .5) & (dataset_water_level.y >= coordinate[0] - .5)
        mask = xmask & ymask

        nearest_index = self._nearest_node_index(dataset_water_level.x, dataset_water_level.y, mask, coordinate)
        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')

        logging.info('Nearest ({}): {}'.format(nearest_index, time.time() - now))

        #
        # water level
        #

        now = time.time()

        water_levels = []
        for date in dataset_water_level.time[:257][::12]:
            water_level = dataset_water_level.zeta.sel(time=date, node=nearest_index)
            data_date = parse_datetime(str(date.time.values))
            water_levels.append({
                'name': data_date.isoformat(),
                'value': water_level.values,
            })
        dataset_water_level.close()

        logging.info('Water Level: {}'.format(time.time() - now))

        #
        # wave height
        #

        now = time.time()

        wave_heights = []
        for date in dataset_wave_height.time[1:][::12]:
            data_date = parse_datetime(str(date.time.values))
            wave_height = dataset_wave_height.hs.sel(time=date, node=nearest_index)
            wave_heights.append({
                'name': data_date.isoformat(),
                'value': wave_height.values,
            })
        dataset_wave_height.close()

        logging.info('Wave Height: {}'.format(time.time() - now))

        #
        # wind
        #

        now = time.time()

        wind_speeds = []
        for date in dataset_wind.time[1:][::12]:
            data_windx = dataset_wind.uwnd.sel(time=date, node=nearest_index)
            data_windy = dataset_wind.vwnd.sel(time=date, node=nearest_index)
            speeds = numpy.arctan2(
                numpy.abs(data_windx.values),
                numpy.abs(data_windy.values),
            )
            data_date = parse_datetime(str(data_windx.time.values))
            wind_speeds.append({
                'name': data_date.isoformat(),
                'value': speeds,
            })
        dataset_wind.close()

        logging.info('Wind: {}'.format(time.time() - now))

        response = Response({
            'water_level': water_levels,
            'wave_height': wave_heights,
            'wind_speed': wind_speeds,
        })

        return response

    @staticmethod
    def _nearest_node_index(x: xr.DataArray, y: xr.DataArray, mask: xr.DataArray, coord: tuple):
        coords = numpy.column_stack([y[mask], x[mask]])
        all_coords = numpy.column_stack([y, x])
        nearest = coords[spatial.KDTree(coords).query(coord)[1]]
        found = numpy.where(all_coords == nearest)
        if found and found[0].any():
            return found[0][0]
        return None

