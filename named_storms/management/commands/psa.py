import logging
import os
import re
import math
from datetime import datetime
import pytz
import xarray
import matplotlib
from django.contrib.gis import geos
from django.contrib.gis.db.models.functions import GeoHash
from named_storms.models import NsemPsa, NsemPsaData, NamedStorm, NsemPsaVariable
from matplotlib import cm, colors
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import numpy as np
from typing import Callable
from shapely.geometry import Polygon, Point
from django.core.management import BaseCommand
from named_storms.tasks import cache_psa_geojson_task


# TODO - make these values less arbitrary by analyzing the input data density and spatial coverage
GRID_SIZE = 5000
COLOR_STEPS = 10  # color bar range
LANDFALL_POLY = Polygon([  # mid atlantic coast
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

WIND_PATH = '/media/bucket/cwwed/OPENDAP/PSA_demo/anil/'

ARG_VARIABLE_WATER_LEVEL_MAX = 'water_level_max'
ARG_VARIABLE_WATER_LEVEL = 'water_level'
ARG_VARIABLE_WAVE_HEIGHT = 'wave_height'
ARG_VARIABLE_WIND_BARBS = 'wind_barbs'
ARG_VARIABLE_WIND_SPEED = 'wind_speed'
ARG_VARIABLE_WIND_SPEED_MAX = 'wind_speed_max'

ARG_VARIABLES = [
    ARG_VARIABLE_WATER_LEVEL_MAX,
    ARG_VARIABLE_WATER_LEVEL,
    ARG_VARIABLE_WAVE_HEIGHT,
    ARG_VARIABLE_WIND_BARBS,
    ARG_VARIABLE_WIND_SPEED,
    ARG_VARIABLE_WIND_SPEED_MAX,
]

ARG_TO_VARIABLE = {
    ARG_VARIABLE_WATER_LEVEL_MAX: 'Water Level Maximum',
    ARG_VARIABLE_WATER_LEVEL: 'Water Level',
    ARG_VARIABLE_WAVE_HEIGHT: 'Wave Height',
    ARG_VARIABLE_WIND_BARBS: 'Wind Barbs',
    ARG_VARIABLE_WIND_SPEED: 'Wind Speed',
    ARG_VARIABLE_WIND_SPEED_MAX: 'Wind Speed Maximum',
}


class Command(BaseCommand):
    help = 'Create Post Storm Assessment'

    storm: NamedStorm = None
    nsem: NsemPsa = None
    triangulation: tri.Triangulation = None
    dataset_unstructured: xarray.Dataset = None
    dataset_structured: xarray.Dataset = None
    xi: np.ndarray = None
    yi: np.ndarray = None
    mask_unstructured: np.ndarray = None
    mask_structured: np.ndarray = None

    # storing min/max wind speed since dataset is multiple files
    _wind_speed_min = None
    _wind_speed_max = None

    def handle(self, *args, **options):

        self.storm = NamedStorm.objects.get(name='Sandy')
        # default to the most recent extracted version
        self.nsem = self.storm.nsempsa_set.filter(snapshot_extracted=True).order_by('-id').first()

        # wind data is a structured dataset
        wind_arg_variables = {ARG_VARIABLE_WIND_SPEED, ARG_VARIABLE_WIND_SPEED_MAX, ARG_VARIABLE_WIND_BARBS}.intersection(options['variable'])

        # water data is an unstructured dataset
        water_arg_variables = {ARG_VARIABLE_WATER_LEVEL_MAX, ARG_VARIABLE_WATER_LEVEL, ARG_VARIABLE_WAVE_HEIGHT}.intersection(options['variable'])

        if wind_arg_variables:
            wind_variables = [variable for arg, variable in ARG_TO_VARIABLE.items() if arg in wind_arg_variables]
            wind_dataset_paths = sorted(os.listdir(WIND_PATH))

            # build the mask from the first dataset since the domain isn't currently changing
            ds = xarray.open_dataset(os.path.join(WIND_PATH, wind_dataset_paths[0]))
            self.mask_structured = np.array([
                [not Point(coord).within(LANDFALL_POLY) for coord in np.column_stack([ds.lon[i], ds.lat[i]])]
                for i in range(len(ds.lat))
            ])

            # delete existing variables
            if options['delete']:
                self.nsem.nsempsavariable_set.filter(nsem=self.nsem, name__in=wind_variables).delete()

            if ARG_VARIABLE_WIND_SPEED_MAX in wind_arg_variables:
                self.dataset_structured = xarray.open_dataset(os.path.join('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy-wind-max.nc'))
                self.process_wind_speed_max()

            for dataset_file in wind_dataset_paths:
                # must be like "wrfout_d01_2012-10-29_14_00.nc", i.e on the hour since we're doing hourly right now, and using "domain 1"
                if re.match(r'wrfout_d01_2012-10-\d{2}_\d{2}_00.nc', dataset_file):
                    # open dataset and define landfall mask
                    self.dataset_structured = xarray.open_dataset(os.path.join(WIND_PATH, dataset_file))

                    if ARG_VARIABLE_WIND_SPEED in wind_arg_variables:
                        self.process_wind_speed()
                    if ARG_VARIABLE_WIND_BARBS in wind_arg_variables:
                        self.process_wind()
        elif water_arg_variables:
            water_variables = [variable for arg, variable in ARG_TO_VARIABLE.items() if arg in water_arg_variables]

            # delete any previous psa results for this nsem
            if options['delete']:
                self.nsem.nsempsavariable_set.filter(nsem=self.nsem, name__in=water_variables).delete()

            self.dataset_unstructured = xarray.open_dataset('/media/bucket/cwwed/OPENDAP/PSA_demo/sandy-water.nc')

            # TODO - need an authoritative dataset to define the date range for a hurricane
            # save the datetime's on our nsem instance
            #self.nsem.dates = [self.datetime64_to_datetime(d) for d in self.dataset_unstructured.time.values]
            #self.nsem.save()

            logging.info('creating geo mask')

            # create a mask to subset data from the landfall geo's convex hull
            # NOTE: using the geo's convex hull prevents sprawling triangles during triangulation
            self.mask_unstructured = np.array([Point(coord).within(LANDFALL_POLY.convex_hull) for coord in np.column_stack((self.dataset_unstructured.x, self.dataset_unstructured.y))])

            x = self.dataset_unstructured.x[self.mask_unstructured]
            y = self.dataset_unstructured.y[self.mask_unstructured]

            logging.info('building triangulation')

            # build delaunay triangles
            self.triangulation = tri.Triangulation(x, y)

            logging.info('masking triangulation')

            # mask triangles outside geo
            tri_mask = [not LANDFALL_POLY.contains((Polygon(np.column_stack((x[triangle].values, y[triangle].values))))) for triangle in self.triangulation.triangles]
            self.triangulation.set_mask(tri_mask)

            # build grid constraints
            self.xi = np.linspace(np.floor(x.min()), np.ceil(x.max()), GRID_SIZE)
            self.yi = np.linspace(np.floor(y.min()), np.ceil(y.max()), GRID_SIZE)

            if ARG_VARIABLE_WATER_LEVEL_MAX in water_arg_variables:
                self.process_water_level_max()
            if ARG_VARIABLE_WATER_LEVEL in water_arg_variables:
                self.process_water_level()
            if ARG_VARIABLE_WAVE_HEIGHT in water_arg_variables:
                self.process_wave_height()

        # pre-cache all geojson api endpoints
        cache_psa_geojson_task.delay(self.nsem.named_storm.id)

    @staticmethod
    def water_level_mask_results(results: list):
        # mask values not greater than zero
        for result in results:
            if result['value'] <= 0:
                results.remove(result)

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

    def build_contours_structured(self, nsem_psa_variable: NsemPsaVariable, zi: xarray.DataArray, cmap: matplotlib.colors.Colormap, dt: datetime = None,
                                  mask_contours: Callable = None):

        lat_masked = np.ma.masked_array(self.dataset_structured.lat, self.mask_structured)
        lon_masked = np.ma.masked_array(self.dataset_structured.lon, self.mask_structured)
        zi_masked = np.ma.masked_array(zi, self.mask_structured)

        logging.info('building contours (structured) for {} at {}'.format(nsem_psa_variable, dt))

        # create the contour
        contourf = plt.contourf(lon_masked, lat_masked, zi_masked, cmap=cmap)

        self.build_contours(nsem_psa_variable, contourf, dt, mask_contours)

    def build_contours_unstructured(self, nsem_psa_variable: NsemPsaVariable, z: xarray.DataArray, cmap: matplotlib.colors.Colormap, dt: datetime = None,
                                    mask_contours: Callable = None):

        logging.info('building contours (unstructured) for {} at {}'.format(nsem_psa_variable, dt))

        # interpolate values from triangle data and build a mesh of data
        interpolator = tri.LinearTriInterpolator(self.triangulation, z)
        Xi, Yi = np.meshgrid(self.xi, self.yi)
        zi = interpolator(Xi, Yi)

        # create the contour
        contourf = plt.contourf(self.xi, self.yi, zi, cmap=cmap)

        self.build_contours(nsem_psa_variable, contourf, dt, mask_contours)

    def build_contours(self, nsem_psa_variable: NsemPsaVariable, contourf, dt=None, mask_contours: Callable = None):

        cmap = contourf.get_cmap()

        results = []

        # process matplotlib contourf results
        for collection_idx, collection in enumerate(contourf.collections):

            # contour level's value
            value = contourf.levels[collection_idx]

            # loop through all polygons that have the same intensity level
            for path in collection.get_paths():

                polygons = path.to_polygons()

                # the first polygon of the path is the exterior ring while the following are interior rings (holes)
                polygon = geos.Polygon(polygons[0], *polygons[1:])

                results.append({
                    'polygon': polygon,
                    'value': value,
                    'color': matplotlib.colors.to_hex(cmap(contourf.norm(value))),
                })

        # conditionally mask contours using supplied callable
        if mask_contours is not None:
            mask_contours(results)

        # build new psa results from contour results
        for result in results:
            NsemPsaData(
                nsem_psa_variable=nsem_psa_variable,
                # TODO - use UTC
                date=dt,
                geo=result['polygon'],
                bbox=geos.Polygon.from_bbox(result['polygon'].extent),
                value=result['value'],
                color=result['color'],
            ).save()

    def build_wind_barbs(self, nsem_psa_variable: NsemPsaVariable, wind_directions: np.ndarray, wind_speeds: np.ndarray, xi: np.ndarray, yi: np.ndarray,
                         dt: datetime):
        """
        expects structured data
        """

        logging.info('building barbs at {}'.format(dt))

        for i in range(len(wind_directions)):
            for j, direction in enumerate(wind_directions[i]):
                if np.ma.is_masked(direction):
                    continue
                point = geos.Point(float(xi[i][j]), float(yi[i][j]), srid=4326)
                NsemPsaData(
                    nsem_psa_variable=nsem_psa_variable,
                    # TODO - use UTC
                    date=dt,
                    geo=point,
                    geo_hash=GeoHash(point),
                    value=wind_speeds[i][j].astype('float'),  # storing speed here for simpler time-series queries
                    meta={
                        'speed': {'value': wind_speeds[i][j].astype('float'), 'units': NsemPsaVariable.UNITS_METERS_PER_SECOND},
                        'direction': {'value': direction.astype('float'), 'units': NsemPsaVariable.UNITS_DEGREES},
                    }
                ).save()

    def process_wave_height(self):

        cmap = matplotlib.cm.get_cmap('jet')

        # create psa variable to assign data
        nsem_psa_variable = NsemPsaVariable(
            nsem=self.nsem,
            name='Wave Height',
            color_bar=self.color_bar_values(self.dataset_unstructured['wave_height'].min(), self.dataset_unstructured['wave_height'].max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            element_type=NsemPsaVariable.ELEMENT_WATER,
            units=NsemPsaVariable.UNITS_METERS,
        )
        nsem_psa_variable.save()

        for z in self.dataset_unstructured['wave_height']:
            z = z[self.mask_unstructured]

            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(z.time)

            self.build_contours_unstructured(nsem_psa_variable, z, cmap, dt, mask_contours=self.water_level_mask_results)

    def process_water_level(self):

        cmap = matplotlib.cm.get_cmap('jet')

        # create psa variable to assign data
        nsem_psa_variable = NsemPsaVariable(
            nsem=self.nsem,
            name='Water Level',
            color_bar=self.color_bar_values(self.dataset_unstructured['water_level'].min(), self.dataset_unstructured['water_level'].max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            element_type=NsemPsaVariable.ELEMENT_WATER,
            units=NsemPsaVariable.UNITS_METERS,
        )
        nsem_psa_variable.save()

        for z in self.dataset_unstructured['water_level']:
            z = z[self.mask_unstructured]

            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(z.time)

            self.build_contours_unstructured(nsem_psa_variable, z, cmap, dt, mask_contours=self.water_level_mask_results)

    def process_water_level_max(self):

        cmap = matplotlib.cm.get_cmap('jet')

        z = self.dataset_unstructured['water_level_max'][self.mask_unstructured]

        # create psa variable to assign data
        nsem_psa_variable = NsemPsaVariable(
            nsem=self.nsem,
            name='Water Level Maximum',
            color_bar=self.color_bar_values(z.min(), z.max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_MAX_VALUES,
            element_type=NsemPsaVariable.ELEMENT_WATER,
            units=NsemPsaVariable.UNITS_METERS,
            auto_displayed=True,
        )
        nsem_psa_variable.save()

        self.build_contours_unstructured(nsem_psa_variable, z, cmap, mask_contours=self.water_level_mask_results)

    def process_wind_speed_max(self):

        cmap = matplotlib.cm.get_cmap('jet')

        z = np.ma.masked_array(self.dataset_structured['wind_speed_max'], self.mask_structured)

        # create psa variable to assign data
        nsem_psa_variable = NsemPsaVariable(
            nsem=self.nsem,
            name='Wind Speed Maximum',
            color_bar=self.color_bar_values(z.min(), z.max(), cmap),
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
            data_type=NsemPsaVariable.DATA_TYPE_MAX_VALUES,
            element_type=NsemPsaVariable.ELEMENT_WIND,
            units=NsemPsaVariable.UNITS_METERS_PER_SECOND,
            auto_displayed=True,
        )
        nsem_psa_variable.save()

        self.build_contours_structured(nsem_psa_variable, z, cmap)

    def process_wind_speed(self):

        cmap = matplotlib.cm.get_cmap('jet')

        # create psa variable to assign data
        nsem_psa_variable_speed, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Wind Speed',
            defaults=dict(
                geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
                data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
                element_type=NsemPsaVariable.ELEMENT_WIND,
                units=NsemPsaVariable.UNITS_METERS_PER_SECOND,
            ),
        )

        #
        # contours
        #

        for date in self.dataset_structured['time']:
            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(date)

            wind_speeds = self.dataset_structured.sel(time=date)['spduv10max'].values

            wind_speeds_data_array = xarray.DataArray(wind_speeds, name='wind')

            self._wind_speed_min = min(wind_speeds_data_array.min(), self._wind_speed_min) if self._wind_speed_min is not None else wind_speeds_data_array.min()
            self._wind_speed_max = max(wind_speeds_data_array.max(), self._wind_speed_max) if self._wind_speed_max is not None else wind_speeds_data_array.max()

            self.build_contours_structured(nsem_psa_variable_speed, wind_speeds_data_array, cmap, dt)

        nsem_psa_variable_speed.color_bar = self.color_bar_values(self._wind_speed_min, self._wind_speed_max, cmap)
        nsem_psa_variable_speed.save()

    def process_wind(self):

        # create psa variable to assign data
        nsem_psa_variable_barbs, _ = NsemPsaVariable.objects.get_or_create(
            nsem=self.nsem,
            name='Wind',
            defaults=dict(
                geo_type=NsemPsaVariable.GEO_TYPE_WIND_BARB,
                data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
                units=NsemPsaVariable.UNITS_DEGREES,  # wind barbs actually store two units (speed & direction) in the psa data itself
            ),
        )

        nsem_psa_variable_barbs.save()

        for date in self.dataset_structured['time']:
            # capture date and convert to datetime
            dt = self.datetime64_to_datetime(date)

            # masked values and subset so we're not displaying every single point
            subset = 10
            wind_speeds = np.ma.masked_array(self.dataset_structured.sel(time=date)['wspd10m'][::subset, ::subset], self.mask_structured[::subset, ::subset])
            wind_directions = np.ma.masked_array(self.dataset_structured.sel(time=date)['wdir10m'][::subset, ::subset], self.mask_structured[::subset, ::subset])
            xi = np.ma.masked_array(self.dataset_structured['lon'][::subset, ::subset], self.mask_structured[::subset, ::subset])
            yi = np.ma.masked_array(self.dataset_structured['lat'][::subset, ::subset], self.mask_structured[::subset, ::subset])

            #
            # barbs
            #

            self.build_wind_barbs(nsem_psa_variable_barbs, wind_directions, wind_speeds, xi, yi, dt)

    def add_arguments(self, parser):

        parser.add_argument(
            '--variable',
            required=True,
            choices=ARG_VARIABLES,
            action='append',
            help='Which variables to process',
        )

        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete existing variables and data',
        )
