import numpy
import time
import logging
import xarray as xr
from scipy import spatial
from django.utils.dateparse import parse_datetime
from rest_framework import views, exceptions
from rest_framework.response import Response


class PSAFilterView(views.APIView):

    def get(self, request):

        # validate the supplied coordinate
        coordinate = request.GET.getlist('coordinate')
        if not coordinate or not len(coordinate) == 2:
            raise exceptions.NotFound('Coordinate (2) not supplied')
        try:
            coordinate = tuple(map(float, coordinate))
        except ValueError:
            raise exceptions.NotFound('Coordinate should be floats')

        # open the dataset
        ds = xr.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy.nc')

        # create a mask "near" the coordinate to make the "nearest neighbor" faster
        xmask = (ds.x <= coordinate[1] + .5) & (ds.x >= coordinate[1] - .5)
        ymask = (ds.y <= coordinate[0] + .5) & (ds.y >= coordinate[0] - .5)
        mask = xmask & ymask

        now = time.time()

        # find the "nearest neighbor" node
        nearest_index = self._nearest_node_index(ds.x, ds.y, mask, coordinate)

        logging.info('Nearest (idx={}) (s): {}'.format(nearest_index, time.time() - now))

        if nearest_index is None:
            raise exceptions.NotFound('No data found at this location')

        #
        # dates
        #

        dates = []
        for date in ds.time[::2]:
            dates.append(parse_datetime(str(date.values)))

        #
        # water level
        #

        now = time.time()

        water_levels = ds.water_level[::2, nearest_index].values

        logging.info('Water Level (s): {}'.format(time.time() - now))

        #
        # wave height
        #

        now = time.time()

        wave_heights = ds.wave_height[::2, nearest_index].values

        logging.info('Wave Height (s): {}'.format(time.time() - now))

        #
        # wind
        #

        now = time.time()

        x_wind_speeds = ds.uwnd[::2, nearest_index].values
        y_wind_speeds = ds.vwnd[::2, nearest_index].values

        wind_speeds = numpy.arctan2(
            numpy.abs(x_wind_speeds),
            numpy.abs(y_wind_speeds),
        )

        logging.info('Wind (s): {}'.format(time.time() - now))

        ds.close()

        response = Response({
            'water_level': [dict(name=name, value=value) for name, value in zip(dates, water_levels)],
            'wave_height': [dict(name=name, value=value) for name, value in zip(dates, wave_heights)],
            'wind_speed': [dict(name=name, value=value) for name, value in zip(dates, wind_speeds)],
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

