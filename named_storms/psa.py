import os
import logging
from datetime import datetime
from io import StringIO

import geopandas
from shapely import wkt
from shapely.geometry import Point
import matplotlib.colors
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import matplotlib.cm
import pytz
import xarray as xr
import numpy as np
from django.contrib.gis import geos
from django.db import connections
from django.conf import settings

from named_storms.models import NsemPsaManifestDataset, NsemPsaVariable, NsemPsaContour, NsemPsaData
from named_storms.utils import named_storm_nsem_version_path


logger = logging.getLogger('cwwed')

CONTOUR_LEVELS = 25
COLOR_STEPS = 10  # color bar range

# TODO - make this less arbitrary
GRID_SIZE = 5000

NULL_REPRESENT = r'\N'


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
        """
        manually copy data into postgres via it's COPY mechanism which is much more efficient
        than using django's orm (even bulk_create) since it has to serialize every object
        https://www.postgresql.org/docs/9.4/sql-copy.html
        https://www.psycopg.org/docs/cursor.html#cursor.copy_from
        """

        logger.info('saving psa data for {} at {}'.format(psa_variable, date))

        # define database columns to copy to
        columns = [
            NsemPsaData.nsem_psa_variable.field.attname,
            NsemPsaData.point.field.attname,
            NsemPsaData.value.field.attname,
            NsemPsaData.date.field.attname,
        ]

        # use default database connection
        with connections['default'].cursor() as cursor:

            # create pandas dataframe for csv output
            df = da.to_dataframe()

            # drop nulls
            df = df.dropna()

            # include empty date column placeholder if it doesn't exist
            if date is None:
                df['time'] = None

            # add psa variable column
            df['psa_variable_id'] = psa_variable.id

            # add point column in wkt format using the lat/lon coordinates and handle
            # cases where the lat/lon are either indexes or column values

            # coordinates are individual columns so zip them together
            if set(df.columns).issuperset(['lat', 'lon']):
                df['point'] = list(map(lambda p: Point(p[1], p[0]), list(zip(df['lat'], df['lon']))))
            # coordinates are a pandas MultiIndex so we can directly map them to points
            elif set(df.index.names).issuperset(['lat', 'lon']):
                df['point'] = df.index.map(lambda p: Point(p[1], p[0]))
            else:
                raise Exception('Expected lat and lon coordinates either as index or columns')

            # create geopandas dataframe and filter to storm's geo
            gdf = geopandas.GeoDataFrame(df)
            gdf = gdf.set_geometry('point')
            gdf = gdf[gdf.within(wkt.loads(self.psa_manifest_dataset.nsem.named_storm.geo.wkt))]

            # reorder gdf columns
            gdf = gdf[['psa_variable_id', 'point', psa_variable.name, 'time']]

            with StringIO() as f:

                # write csv results to file-like object
                gdf.to_csv(f, header=False, index=False, na_rep=NULL_REPRESENT)
                f.seek(0)  # set file read position back to beginning

                # copy data into table using postgres COPY feature
                cursor.copy_from(f, NsemPsaData._meta.db_table, columns=columns, sep=',', null=NULL_REPRESENT)

    @staticmethod
    def datetime64_to_datetime(dt64):
        unix_epoch = np.datetime64(0, 's')
        one_second = np.timedelta64(1, 's')
        seconds_since_epoch = (dt64 - unix_epoch) / one_second
        return datetime.utcfromtimestamp(seconds_since_epoch).replace(tzinfo=pytz.utc)

    def ingest(self):
        for variable in self.psa_manifest_dataset.variables:

            # close and reopen dataset for memory cleanup
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
                    self._build_contours(psa_variable, data_array)

                    # save raw data
                    self._save_psa_data(psa_variable, data_array)

                # time series
                elif psa_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES:
                    for date in self.psa_manifest_dataset.nsem.dates:
                        data_array = self.dataset.sel(time=date)[variable]

                        # save contours
                        self._build_contours(psa_variable, data_array, date)

                        # save raw data
                        self._save_psa_data(psa_variable, data_array, date)

                psa_variable.color_bar = self.color_bar_values(self.dataset[variable].min(), self.dataset[variable].max())

            # wind barbs - only saving point data with wind directions
            elif psa_variable.name == NsemPsaVariable.VARIABLE_DATASET_WIND_DIRECTION:
                for date in self.psa_manifest_dataset.nsem.dates:
                    data_array = self.dataset.sel(time=date)[variable]
                    # save raw data
                    self._save_psa_data(psa_variable, data_array, date)

            psa_variable.save()

        logger.info('PSA Dataset {} has been successfully ingested'.format(self.psa_manifest_dataset))

    def _build_contours(self, nsem_psa_variable: NsemPsaVariable, zi: xr.DataArray, dt: datetime = None):

        logger.info('building contours for {} at {}'.format(nsem_psa_variable, dt))

        # TODO - we should only create the triangulation & mesh once per dataset

        # unstructured grid - make a triangulation and interpolate data on a mesh
        if len(zi.shape) == 1:
            # create interpolator from triangulation
            interpolator = tri.LinearTriInterpolator(
                tri.Triangulation(self.dataset.lon, self.dataset.lat), zi)
            # build a mesh of data
            xi, yi = np.meshgrid(
                np.linspace(np.floor(self.dataset.lon.min()), np.ceil(self.dataset.lon.max()), GRID_SIZE),
                np.linspace(np.floor(self.dataset.lat.min()), np.ceil(self.dataset.lat.max()), GRID_SIZE),
            )
            # build contour using interpolated data on mesh
            contourf = plt.contourf(xi, yi, interpolator(xi, yi), levels=CONTOUR_LEVELS, cmap=self.cmap)
        # structured grid
        else:
            contourf = plt.contourf(self.dataset['lon'], self.dataset['lat'], zi, cmap=self.cmap, levels=CONTOUR_LEVELS)

        self._process_contours(nsem_psa_variable, contourf, dt)

    def _process_contours(self, nsem_psa_variable: NsemPsaVariable, contourf, dt=None):

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
