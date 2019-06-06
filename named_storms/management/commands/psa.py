import json
import logging
import math
from datetime import datetime
import pytz
import xarray
import matplotlib
from django.contrib.gis import geos
from named_storms.models import NSEM, NsemPsaData, NamedStorm, NsemPsaVariable
from matplotlib import cm, colors
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
import geojsoncontour
from typing import Callable
from shapely.geometry import Polygon, Point
from django.core.management import BaseCommand


# TODO - make these values less arbitrary by analyzing the input data density and spatial coverage
GRID_SIZE = 5000
CONTOUR_LEVELS = 30

COLOR_STEPS = 10  # color bar range

# mid atlantic coast
GEO_POLY = Polygon([
    [-78.50830078125, 33.76088200086917],
    [-77.82714843749999, 33.815666308702774],
    [-77.607421875, 34.161818161230386],
    [-77.1240234375, 34.52466147177172],
    [-76.46484375, 34.615126683462194],
    [-75.78369140625, 34.97600151317588],
    [-75.30029296875, 35.44277092585766],
    [-75.34423828125, 35.871246850027966],
    [-75.65185546874999, 36.43896124085945],
    [-75.8056640625, 37.09023980307208],
    [-75.30029296875, 37.735969208590504],
    [-74.99267578125, 38.16911413556086],
    [-74.8828125, 38.59970036588819],
    [-74.7509765625, 38.92522904714054],
    [-74.37744140625, 39.26628442213066],
    [-73.93798828125, 39.80853604144591],
    [-73.7841796875, 40.463666324587685],
    [-72.61962890625, 40.66397287638688],
    [-71.8505859375, 40.88029480552824],
    [-71.34521484375, 41.1455697310095],
    [-69.85107421874999, 41.21172151054787],
    [-69.78515625, 41.52502957323801],
    [-69.76318359375, 42.00032514831621],
    [-70.48828125, 42.17968819665961],
    [-71.65283203125, 42.01665183556825],
    [-72.97119140625, 41.60722821271717],
    [-74.28955078125, 41.42625319507269],
    [-75.21240234375, 40.34654412118006],
    [-76.31103515625, 39.70718665682654],
    [-77.3876953125, 39.04478604850143],
    [-77.49755859375, 38.324420427006544],
    [-77.47558593749999, 37.61423141542417],
    [-77.2119140625, 36.66841891894786],
    [-77.080078125, 35.69299463209881],
    [-77.431640625, 34.92197103616377],
    [-78.50830078125, 33.76088200086917],
])


class Command(BaseCommand):
    help = 'Create Post Storm Assessments'

    storm: NamedStorm = None
    nsem: NSEM = None
    triangulation: tri.Triangulation = None
    dataset: xarray.Dataset = None
    xi: np.ndarray = None
    yi: np.ndarray = None
    mask: np.ndarray = None

    def handle(self, *args, **options):

        logging.info('opening dataset')

        self.dataset = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy.nc')

        logging.info('creating geo mask')

        # create a mask to subset data from the geo's convex hull
        # NOTE: using the geo's convex hull prevents sprawling triangles during triangulation
        self.mask = np.array([Point(coord).within(GEO_POLY.convex_hull) for coord in np.column_stack((self.dataset.x, self.dataset.y))])

        x = self.dataset.x[self.mask]
        y = self.dataset.y[self.mask]

        logging.info('building triangulation')

        # build delaunay triangles
        self.triangulation = tri.Triangulation(x, y)

        logging.info('masking triangulation')

        # mask triangles outside geo
        tri_mask = [not GEO_POLY.contains((Polygon(np.column_stack((x[triangle].values, y[triangle].values))))) for triangle in self.triangulation.triangles]
        self.triangulation.set_mask(tri_mask)

        # build grid constraints
        self.xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
        self.yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

        self.storm = NamedStorm.objects.get(name='Sandy')
        self.nsem = self.storm.nsem_set.order_by('-id')[0]

        # save the datetime's on our nsem instance
        self.nsem.dates = [self.datetime64_to_datetime(d) for d in self.dataset.time.values]
        self.nsem.save()

        # delete any previous psa results for this nsem
        self.nsem.nsempsavariable_set.filter(nsem=self.nsem).delete()

        self.process_water_level_max()
        self.process_water_level()
        self.process_wave_height()
        self.process_wind()

    @staticmethod
    def water_level_mask_geojson(geojson_result: dict):
        # mask values not greater than zero
        for feature in geojson_result['features'][:]:
            if float(feature['properties']['title']) <= 0:
                geojson_result['features'].remove(feature)

    @staticmethod
    def color_bar_values(z_min: float, z_max: float, cmap: matplotlib.colors.Colormap):
        # build color bar values

        color_values = []

        color_norm = matplotlib.colors.Normalize(vmin=z_min, vmax=z_max)
        step_intervals = np.linspace(z_min, z_max, COLOR_STEPS)

        for step_value in step_intervals:
            # round the step value for ranges greater than COLOR_STEPS
            if z_max - z_min >= COLOR_STEPS:
                step_value = math.ceil(step_value)
            hex_value = matplotlib.colors.to_hex(cmap(color_norm(step_value)))
            color_values.append((step_value, hex_value))

        return color_values

    @staticmethod
    def datetime64_to_datetime(dt64):
        unix_epoch = np.datetime64(0, 's')
        one_second = np.timedelta64(1, 's')
        seconds_since_epoch = (dt64 - unix_epoch) / one_second
        return datetime.utcfromtimestamp(seconds_since_epoch).replace(tzinfo=pytz.utc)

    def build_contours(self, nsem_psa_variable: NsemPsaVariable, z: xarray.DataArray, cmap: matplotlib.colors.Colormap, dt: datetime = None, mask_geojson: Callable = None):

        logging.info('building contours for {} at {}'.format(nsem_psa_variable, dt))

        # interpolate values from triangle data and build a mesh of data
        interpolator = tri.LinearTriInterpolator(self.triangulation, z)
        Xi, Yi = np.meshgrid(self.xi, self.yi)
        zi = interpolator(Xi, Yi)

        # create the contour
        contourf = plt.contourf(self.xi, self.yi, zi, CONTOUR_LEVELS, cmap=cmap)

        # convert matplotlib contourf to geojson
        geojson_result = json.loads(geojsoncontour.contourf_to_geojson(contourf=contourf, ndigits=10))

        # mask regions
        if mask_geojson is not None:
            mask_geojson(geojson_result)

        # build new psa results from geojson output
        for feature in geojson_result['features']:
            # save individual contours as separate polygons
            for coords in feature['geometry']['coordinates'][0]:
                polygon = geos.Polygon(coords)
                NsemPsaData(
                    nsem_psa_variable=nsem_psa_variable,
                    date=dt,
                    geo=polygon,
                    bbox=geos.Polygon.from_bbox(polygon.extent),
                    value=feature['properties']['title'],
                    color=feature['properties']['fill'],
                ).save()

    def build_wind_barbs(self, nsem_psa_variable: NsemPsaVariable, wind_directions: np.ndarray, wind_speeds: np.ndarray, dt: datetime):

        logging.info('building barbs at {}'.format(dt))

        nan_mask = ~np.isnan(wind_directions)

        # get a subset so we're not displaying every single point
        wind_directions = wind_directions[nan_mask][::50]
        wind_speeds = wind_speeds[nan_mask][::50]
        x = self.dataset.x[self.mask][nan_mask][::50].values
        y = self.dataset.y[self.mask][nan_mask][::50].values

        for i, direction in enumerate(wind_directions):
            NsemPsaData(
                nsem_psa_variable=nsem_psa_variable,
                date=dt,
                geo=geos.Point(x[i], y[i]),
                value=direction,  # we're storing speed and direction in "meta" but this is a required field
                meta={
                    'speed': {'value': wind_speeds[i].astype('float'), 'units': NsemPsaVariable.UNITS_METERS_PER_SECOND},
                    'direction': {'value': direction.astype('float'), 'units': NsemPsaVariable.UNITS_RADIAN},
                }
            ).save()

    def process_wave_height(self):

        cmap = matplotlib.cm.get_cmap('jet')

        # create psa variable to assign data
        nsem_psa_variable, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Wave Height',
            color_bar=self.color_bar_values(self.dataset['wave_height'].min(), self.dataset['wave_height'].max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            units=NsemPsaVariable.UNITS_METERS,
        )
        nsem_psa_variable.save()

        for z in self.dataset['wave_height']:

            z = z[self.mask]

            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(z.time)

            self.build_contours(nsem_psa_variable, z, cmap, dt, mask_geojson=self.water_level_mask_geojson)

    def process_water_level(self):

        cmap = matplotlib.cm.get_cmap('jet')

        # create psa variable to assign data
        nsem_psa_variable, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Water Level',
            color_bar=self.color_bar_values(self.dataset['water_level'].min(), self.dataset['water_level'].max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            units=NsemPsaVariable.UNITS_METERS,
        )
        nsem_psa_variable.save()

        for z in self.dataset['water_level']:

            z = z[self.mask]

            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(z.time)

            self.build_contours(nsem_psa_variable, z, cmap, dt, mask_geojson=self.water_level_mask_geojson)

    def process_water_level_max(self):

        cmap = matplotlib.cm.get_cmap('jet')

        z = self.dataset['water_level_max'][self.mask]

        # create psa variable to assign data
        nsem_psa_variable, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Water Level Max',
            color_bar=self.color_bar_values(z.min(), z.max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_MAX_VALUES,
            units=NsemPsaVariable.UNITS_METERS,
            auto_displayed=True,
        )
        nsem_psa_variable.save()

        self.build_contours(nsem_psa_variable, z, cmap, mask_geojson=self.water_level_mask_geojson)

    def process_wind(self):

        cmap = matplotlib.cm.get_cmap('jet')

        # create psa variables to assign data
        nsem_psa_variable_barbs, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Wind Barbs',
            geo_type=NsemPsaVariable.GEO_TYPE_WIND_BARB,
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            units=NsemPsaVariable.UNITS_RADIAN,  # placeholder since wind barbs use two units (speed & direction)
            auto_displayed=True,
        )

        nsem_psa_variable_speed, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Wind Speed',
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            units=NsemPsaVariable.UNITS_METERS_PER_SECOND,
            auto_displayed=True,
        )

        nsem_psa_variable_barbs.save()
        nsem_psa_variable_speed.save()

        min_speed = None
        max_speed = None

        for date in self.dataset['time']:

            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(date)

            # get masked values
            windx_values = self.dataset.sel(time=date)['uwnd'][self.mask].values
            windy_values = self.dataset.sel(time=date)['vwnd'][self.mask].values

            wind_speeds = np.abs(np.hypot(windx_values, windy_values))
            wind_directions = np.arctan2(windx_values, windy_values)

            #
            # barbs
            #

            self.build_wind_barbs(nsem_psa_variable_barbs, wind_directions, wind_speeds, dt)

            #
            # contours
            #

            wind_speeds_data_array = xarray.DataArray(wind_speeds, name='wind')

            min_speed = min(wind_speeds_data_array.min(), min_speed) if min_speed is not None else wind_speeds_data_array.min()
            max_speed = max(wind_speeds_data_array.max(), max_speed) if max_speed is not None else wind_speeds_data_array.max()

            self.build_contours(nsem_psa_variable_speed, wind_speeds_data_array, cmap, dt)

        nsem_psa_variable_speed.color_bar = self.color_bar_values(min_speed, max_speed, cmap)
        nsem_psa_variable_speed.save()
