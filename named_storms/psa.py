import os
import time
import logging
from datetime import datetime
from io import StringIO

import matplotlib.colors
import matplotlib.pyplot as plt
import matplotlib.cm
import pytz
import xarray as xr
import numpy as np
import geohash
from django.contrib.gis import geos
from django.db import connections
from django.conf import settings
from django.utils import timezone

from named_storms.models import NsemPsaManifestDataset, NsemPsaVariable, NsemPsaContour, NsemPsaData
from named_storms.utils import named_storm_nsem_version_path


logger = logging.getLogger('cwwed')

CONTOUR_LEVELS = 25
COLOR_STEPS = 10  # color bar range


class PsaDataset:
    cmap = matplotlib.cm.get_cmap('jet')
    dataset: xr.Dataset = None

    def __init__(self, psa_manifest_dataset: NsemPsaManifestDataset):
        self.psa_manifest_dataset = psa_manifest_dataset

    def _toggle_dataset(self):
        # close and reopen for memory saving purposes

        # close if already open
        if self.dataset:
            self.dataset.close()

        # open dataset
        self.dataset = xr.open_dataset(os.path.join(
            named_storm_nsem_version_path(self.psa_manifest_dataset.nsem),
            self.psa_manifest_dataset.path)
        )

    def _save_psa_data(self, psa_variable: NsemPsaVariable, da: xr.DataArray, date=None):
        # manually copy data into postgres via it's COPY mechanism which is much more efficient
        # than using django's orm (even bulk_create) since it has to serialize every object
        # https://www.postgresql.org/docs/9.4/sql-copy.html
        # https://www.psycopg.org/docs/cursor.html#cursor.copy_from

        logger.info('Saving psa data for {} at {}'.format(psa_variable, date))

        # define database columns to copy to
        columns = [
            NsemPsaData.nsem_psa_variable.field.attname,
            NsemPsaData.point.field.attname,
            NsemPsaData.geo_hash.field.attname,
            NsemPsaData.value.field.attname,
        ]
        if date is not None:
            columns.append(NsemPsaData.date.field.attname)

        # use default database connection
        with connections['default'].cursor() as cursor:

            latitudes = da.lat.values
            longitudes = da.lon.values

            # build rows of csv values to copy
            results = []
            for i, row in enumerate(da):

                start_time = time.time()

                for j, data in enumerate(row):

                    # handle differing shapes of data
                    if da.dims.index('lat') < da.dims.index('lon'):
                        lat = latitudes[i].item()
                        lon = longitudes[j].item()
                    else:
                        lat = latitudes[j].item()
                        lon = longitudes[i].item()

                    point = geos.Point(lon, lat, srid=4326)
                    point_geo_hash = geohash.encode(lat, lon, precision=20)  # postgres defaults to precision of 20

                    if date is not None:
                        results.append("{}\t{}\t{}\t{}\t{}\n".format(
                            psa_variable.id, point, point_geo_hash, data.item(), date))
                    else:
                        results.append("{}\t{}\t{}\t{}\n".format(
                            psa_variable.id, point, point_geo_hash, data.item()))
                logger.info("row %s: %s seconds" % (i, time.time() - start_time))

            logger.info('writing lines...')

            # write results to file-like object
            f = StringIO()
            f.writelines(results)
            f.seek(0)  # read back to start of file

            logger.info('copying...')

            # copy data into table using postgres COPY feature
            cursor.copy_from(f, NsemPsaData._meta.db_table, columns=columns)

            # run ANALYZE for query planning
            cursor.execute('ANALYZE {}'.format(NsemPsaData._meta.db_table))

            # close file string
            f.close()

    @staticmethod
    def datetime64_to_datetime(dt64):
        unix_epoch = np.datetime64(0, 's')
        one_second = np.timedelta64(1, 's')
        seconds_since_epoch = (dt64 - unix_epoch) / one_second
        return datetime.utcfromtimestamp(seconds_since_epoch).replace(tzinfo=pytz.utc)

    def ingest(self):
        for variable in self.psa_manifest_dataset.variables:

            # close and reopen dataset
            self._toggle_dataset()

            assert variable in NsemPsaVariable.VARIABLES, 'unknown variable "{}"'.format(variable)
            logger.info('Processing dataset variable {} for {}'.format(variable, self.psa_manifest_dataset))

            psa_variable, _ = self.psa_manifest_dataset.nsem.nsempsavariable_set.get_or_create(
                name=variable,
                defaults=dict(
                    geo_type=NsemPsaVariable.get_variable_attribute(variable, 'geo_type'),
                    data_type=NsemPsaVariable.get_variable_attribute(variable, 'data_type'),
                    element_type=NsemPsaVariable.get_variable_attribute(variable, 'element_type'),
                    units=NsemPsaVariable.get_variable_attribute(variable, 'units'),
                    auto_displayed=NsemPsaVariable.get_variable_attribute(variable, 'auto_displayed'),
                )
            )

            # deleting any existing psa data in debug/development only
            if settings.DEBUG:
                psa_variable.nsempsacontour_set.all().delete()
                psa_variable.nsempsadata_set.all().delete()

            # contours
            if psa_variable.geo_type == NsemPsaVariable.GEO_TYPE_POLYGON:

                # max values
                if psa_variable.data_type == NsemPsaVariable.DATA_TYPE_MAX_VALUES:
                    # use the first time value if there's a time dimension at all
                    if 'time' in self.dataset[variable].dims:
                        data_array = self.dataset[variable][0]
                    else:
                        data_array = self.dataset[variable]

                    # save contours
                    self.build_contours_structured(psa_variable, data_array)

                    # save raw data
                    self._save_psa_data(psa_variable, data_array)

                # time series
                elif psa_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
                    for date in self.psa_manifest_dataset.nsem.dates:
                        data_array = self.dataset.sel(time=date)[variable]

                        # save contours
                        self.build_contours_structured(psa_variable, data_array, date)

                        # save raw data
                        self._save_psa_data(psa_variable, data_array, date)

                psa_variable.color_bar = self.color_bar_values(self.dataset[variable].min(), self.dataset[variable].max())

            # TODO - saving barbs like this isn't necessary anymore
            # wind barbs
            #elif variable == NsemPsaVariable.VARIABLE_DATASET_WIND_DIRECTION and psa_variable.geo_type == NsemPsaVariable.GEO_TYPE_WIND_BARB:

            #    for date in self.psa_manifest_dataset.nsem.dates:

            #        # masked values and subset so we're not displaying every single point
            #        subset = 10
            #        wind_speeds = np.array(self.dataset.sel(time=date)[NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED][::subset, ::subset])
            #        wind_directions = np.array(self.dataset.sel(time=date)[NsemPsaVariable.VARIABLE_DATASET_WIND_DIRECTION][::subset, ::subset])
            #        xi = np.array(self.dataset['lon'][::subset, ::subset])
            #        yi = np.array(self.dataset['lat'][::subset, ::subset])

            #        # save barbs
            #        self.build_wind_barbs(psa_variable, wind_directions, wind_speeds, xi, yi, date)

            #        # save raw data
            #        data_array = self.dataset.sel(time=date)[variable]
            #        self._save_psa_data(psa_variable, data_array, date)

            psa_variable.save()

        self.psa_manifest_dataset.nsem.processed = True
        self.psa_manifest_dataset.nsem.date_processed = timezone.now()
        self.psa_manifest_dataset.nsem.save()

        logger.info('PSA Dataset {} has been successfully ingested'.format(self.psa_manifest_dataset))

    def build_contours_structured(self, nsem_psa_variable: NsemPsaVariable, zi: xr.DataArray, dt: datetime = None):

        logger.info('building contours for {} at {}'.format(nsem_psa_variable, dt))

        # create the contour
        contourf = plt.contourf(self.dataset['lon'], self.dataset['lat'], zi, cmap=self.cmap, levels=CONTOUR_LEVELS)

        self.build_contours(nsem_psa_variable, contourf, dt)

    def build_contours(self, nsem_psa_variable: NsemPsaVariable, contourf, dt=None):

        results = []

        # process matplotlib contourf results
        for i, collection in enumerate(contourf.collections):

            # contour level value
            value = contourf.levels[i]

            # loop through all polygons that have the same intensity level
            for path in collection.get_paths():

                polygons = path.to_polygons()

                if len(polygons) == 0:
                    logger.warning('Invalid polygon contour for {}'.format(nsem_psa_variable))
                    continue

                # the first polygon of the path is the exterior ring while the following are interior rings (holes)
                polygon = geos.Polygon(polygons[0], *polygons[1:])

                results.append({
                    'polygon': polygon,
                    'value': value,
                    'color': matplotlib.colors.to_hex(self.cmap(contourf.norm(value))),
                })

        # build new psa results from contour results
        for result in results:
            NsemPsaContour(
                nsem_psa_variable=nsem_psa_variable,
                date=dt,
                geo=result['polygon'],
                value=result['value'],
                color=result['color'],
            ).save()

    def build_wind_barbs(self, nsem_psa_variable: NsemPsaVariable, wind_directions: np.ndarray, wind_speeds: np.ndarray, xi: np.ndarray, yi: np.ndarray, dt: datetime):

        logger.info('building barbs at {}'.format(dt))

        for i in range(len(wind_directions)):
            for j, direction in enumerate(wind_directions[i]):
                if np.ma.is_masked(direction):
                    continue
                point = geos.Point(float(xi[i][j]), float(yi[i][j]), srid=4326)
                NsemPsaContour(
                    nsem_psa_variable=nsem_psa_variable,
                    date=dt,
                    geo=point,
                    value=wind_speeds[i][j].astype('float'),  # storing speed here for simpler time-series queries
                    meta={
                        'speed': {'value': wind_speeds[i][j].astype('float'), 'units': NsemPsaVariable.UNITS_METERS_PER_SECOND},
                        'direction': {'value': direction.astype('float'), 'units': NsemPsaVariable.UNITS_DEGREES},
                    }
                ).save()

    def color_bar_values(self, z_min: float, z_max: float):
        # build color bar values

        color_values = []

        color_norm = matplotlib.colors.Normalize(vmin=z_min, vmax=z_max)
        step_intervals = np.linspace(z_min, z_max, COLOR_STEPS)

        for step_value in step_intervals:
            # round the step value for ranges greater than COLOR_STEPS
            if z_max - z_min >= COLOR_STEPS:
                step_value = np.math.ceil(step_value)
            hex_value = matplotlib.colors.to_hex(self.cmap(color_norm(step_value)))
            color_values.append((step_value, hex_value))

        return color_values
