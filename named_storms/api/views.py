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

        x_coords = ds.x[:].values
        y_coords = ds.y[:].values

        # create a mask of coordinates near the supplied coordinate to make the "nearest neighbor" faster
        xmask = (x_coords <= coordinate[1] + .5) & (x_coords >= coordinate[1] - .5)
        ymask = (y_coords <= coordinate[0] + .5) & (y_coords >= coordinate[0] - .5)
        mask = xmask & ymask

        now = time.time()

        # find the "nearest neighbor" node
        nearest_index = self._nearest_node_index(x_coords, y_coords, mask, coordinate)

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

        x_wind_speeds = None
        y_wind_speeds = None

        # NOTE: wind data isn't evenly distributed so we have to iteratively look for the nearest location
        # where it has at least some values
        while x_coords.any():
            x_wind_speeds = ds.uwnd[::2, nearest_index].values
            y_wind_speeds = ds.vwnd[::2, nearest_index].values
            # has values
            if not numpy.all(numpy.isnan(x_wind_speeds)):
                break
            # no values - find next nearest node
            else:
                x_coords = numpy.delete(x_coords, nearest_index)
                y_coords = numpy.delete(y_coords, nearest_index)
                xmask = (x_coords <= coordinate[1] + .5) & (x_coords >= coordinate[1] - .5)
                ymask = (y_coords <= coordinate[0] + .5) & (y_coords >= coordinate[0] - .5)
                mask = xmask & ymask
                nearest_index = self._nearest_node_index(x_coords, y_coords, mask, coordinate)

        wind_speeds = numpy.arctan2(
            numpy.abs(x_wind_speeds),
            numpy.abs(y_wind_speeds),
        )

        logging.info('Wind (s): {}'.format(time.time() - now))

        ds.close()

        response = Response({
            'dates': dates,
            # convert NaN to zero
            'water_level': numpy.nan_to_num(water_levels),
            'wave_height': numpy.nan_to_num(wave_heights),
            'wind_speed': numpy.nan_to_num(wind_speeds),
        })

        return response

    @staticmethod
    def _nearest_node_index(x: numpy.ndarray, y: numpy.ndarray, mask: numpy.ndarray, coord: tuple):
        coords = numpy.column_stack([y[mask], x[mask]])
        all_coords = numpy.column_stack([y, x])
        nearest = coords[spatial.KDTree(coords).query(coord)[1]]
        found = numpy.where(all_coords == nearest)
        if found and found[0].any():
            return found[0][0]
        return None

