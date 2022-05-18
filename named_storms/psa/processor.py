import os
import time
import logging
import tempfile
from datetime import datetime
from typing import List, Tuple

import geopandas
from shapely import wkt
from shapely import geometry
import matplotlib.colors
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import matplotlib.cm
import pytz
import xarray as xr
import numpy as np
from django.contrib.gis import geos
from django.db import connections

from named_storms.models import NsemPsaManifestDataset, NsemPsaVariable, NsemPsaContour, NsemPsaData
from named_storms.utils import named_storm_nsem_version_path


logger = logging.getLogger('cwwed')

NULL_FILL_VALUE = -9999
CONTOUR_LEVELS = 25  # number of contour levels
COLOR_STEPS = 10  # number of color bar steps
NULL_REPRESENT = r'\N'


class PsaDatasetProcessor:
    dataset: xr.Dataset
    psa_manifest_dataset: NsemPsaManifestDataset

    def __init__(self, psa_manifest_dataset: NsemPsaManifestDataset):
        self.psa_manifest_dataset = psa_manifest_dataset
        self.dataset = xr.open_dataset(os.path.join(
            named_storm_nsem_version_path(self.psa_manifest_dataset.nsem),
            self.psa_manifest_dataset.path)
        )

    def __del__(self):
        # cleanup
        if self.dataset:
            self.dataset.close()

    def ingest_variable(self, variable: str, date: datetime = None):

        assert variable in NsemPsaVariable.VARIABLES, 'unknown variable "{}"'.format(variable)

        # get or create the psa variable
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

        # delete any existing psa variable data in case we're reprocessing this psa
        psa_variable.nsempsacontour_set.filter(date=date).delete()
        psa_variable.nsempsadata_set.filter(date=date).delete()

        # contours
        if psa_variable.geo_type == NsemPsaVariable.GEO_TYPE_POLYGON:

            # max values
            if psa_variable.data_type == NsemPsaVariable.DATA_TYPE_MAX_VALUES:
                # use the first time value if there's a time dimension
                if 'time' in self.dataset[variable].dims:
                    data_array = self.dataset[variable][0]
                else:
                    data_array = self.dataset[variable]

                # save contours
                self._build_contours(psa_variable, data_array)

                # save raw data
                self._save_psa_data(psa_variable, data_array)

            # time series
            else:
                assert date is not None, 'date must be supplied for time-series variable {}'.format(psa_variable)
                data_array = self.dataset.sel(time=date)[variable]

                # save contours
                self._build_contours(psa_variable, data_array, date)

                # save raw data
                self._save_psa_data(psa_variable, data_array, date)

            psa_variable.color_bar = self._color_bar_values(psa_variable, self.dataset[variable].min(), self.dataset[variable].max())

        # wind barbs - only saving point data with wind directions
        elif psa_variable.name == NsemPsaVariable.VARIABLE_DATASET_WIND_DIRECTION:
            assert date is not None, 'date must be supplied for time-series variable {}'.format(psa_variable)
            data_array = self.dataset.sel(time=date)[variable]
            # save raw data
            self._save_psa_data(psa_variable, data_array, date)
        else:
            raise Exception('{}: Unknown variable type {}'.format(self.psa_manifest_dataset, variable))

        psa_variable.meta = self._to_python_values(data_array.attrs)
        psa_variable.save()

    def get_metadata(self):
        # return dataset metadata in python native types
        return self._to_python_values(self.dataset.attrs)

    def get_variable_metadata(self, variable: str):
        # return dataset metadata in python native types
        return self._to_python_values(self.dataset[variable].attrs)

    def _build_contours(self, nsem_psa_variable: NsemPsaVariable, z: xr.DataArray, dt: datetime = None):

        logger.info('{}: building contours for {} at {}'.format(self.psa_manifest_dataset, nsem_psa_variable, dt))

        # structured grid
        if self.psa_manifest_dataset.structured:
            contourf = plt.contourf(self.dataset['lon'], self.dataset['lat'], z, cmap=self._get_color_map(nsem_psa_variable), levels=CONTOUR_LEVELS)
            self._process_contours_gridded(nsem_psa_variable, contourf, dt)

        # unstructured grid - use provided triangulation to contour
        else:

            # adjust mesh topology indexing if this is 0-based or 1-based indexing
            # see https://github.com/ugrid-conventions/ugrid-conventions
            # subtract n from the topology/mesh using "start_index" metadata
            topology = self.dataset[self.psa_manifest_dataset.topology_name]
            topology = np.subtract(
                topology,
                topology.attrs['start_index'],
            )

            # create mask to identify triangles with null values
            tri_nulls = z[topology].isnull()
            # convert to single dimension result of whether any the points in each triangle/row are null
            tri_mask = np.any(tri_nulls, axis=1)

            # build triangulation using supplied mesh connectivity and tri mask
            triangulation = tri.Triangulation(self.dataset.lon, self.dataset.lat, triangles=topology, mask=tri_mask)

            # replace nulls with an arbitrary fill value and then only contour valid levels
            levels = np.linspace(z.min(), z.max(), num=CONTOUR_LEVELS)
            tricontourf = plt.tricontourf(triangulation, z.fillna(NULL_FILL_VALUE), levels=levels, cmap=self._get_color_map(nsem_psa_variable))

            self._process_contours_triangulation(nsem_psa_variable, tricontourf, dt)

    def _process_contours_gridded(self, nsem_psa_variable: NsemPsaVariable, contourf, dt):
        # the polygons that come out of matplotlib's contourf are nicely ordered exteriors with interior rings, so
        # it's very straightforward to build the resulting polygons

        # process matplotlib contourf results
        for i, collection in enumerate(contourf.collections):

            # contour level value and color
            value = contourf.levels[i]
            color = matplotlib.colors.to_hex(self._get_color_map(nsem_psa_variable)(contourf.norm(value)))

            # loop through all polygons that have the same intensity level
            for path in collection.get_paths():

                polygons = path.to_polygons()

                if len(polygons) == 0:
                    logger.warning('skipping invalid polygon contour for {}'.format(nsem_psa_variable))
                    continue

                # the first polygon of the path is the exterior ring while the following are interior rings (holes)
                polygon = geos.Polygon(polygons[0], *polygons[1:])

                self._save_contour(nsem_psa_variable, dt, polygon, value, color)

    def _process_contours_triangulation(self, nsem_psa_variable: NsemPsaVariable, tricontourf, dt):
        # the polygons that come out of matplotlib's tricontourf are unordered and unidentified (exterior vs interior)
        # so we have to calculate which are exterior rings and which interior rings are contained within each exterior

        # process contour results
        for collection_idx, collection in enumerate(tricontourf.collections):

            # contour level value and color
            value = tricontourf.levels[collection_idx]
            color = matplotlib.colors.to_hex(self._get_color_map(nsem_psa_variable)(tricontourf.norm(value)))

            # loop through all polygons that have the same intensity level
            for path in collection.get_paths():

                # don't simplify the paths
                path.should_simplify = False

                path_polygons = path.to_polygons()

                if len(path_polygons) == 0:
                    logger.warning('{}: skipping path with empty polygons for {}'.format(self.psa_manifest_dataset, nsem_psa_variable))
                    continue

                # classify exterior and interior polygons
                exterior_polygons, interior_rings = self.classify_polygons(path_polygons)

                # build all polygons for this path using the calculated interior rings/holes
                for exterior_idx, exterior in enumerate(exterior_polygons):

                    interior_indexes = []

                    # sort interiors by size so we add the right ones first and skip nested ones
                    interior_rings.sort(key=lambda x: geos.Polygon(x).area, reverse=True)

                    # assign interior rings (holes)
                    exterior_interior_rings = []
                    for interior_idx, interior in enumerate(interior_rings):
                        # exterior contains this interior
                        if exterior.contains(interior):
                            # avoid nested rings (i.e. an interior that belongs to another exterior)
                            for exterior_interior_ring in exterior_interior_rings:
                                # skip since an existing hole for this exterior contains this interior so it must be for another exterior
                                if geos.Polygon(exterior_interior_ring).contains(interior):
                                    break
                            # include this interior
                            else:  # for/else
                                interior_indexes.append(interior_idx)
                                exterior_interior_rings.append(interior)

                    # remove used interiors
                    interior_rings = [interior for i, interior in enumerate(interior_rings) if i not in interior_indexes]

                    # build final result polygon
                    polygon = geos.Polygon(exterior[0], *exterior_interior_rings)

                    self._save_contour(nsem_psa_variable, dt, polygon, value, color)

    def _save_contour(self, nsem_psa_variable: NsemPsaVariable, dt: datetime, polygon: geos.Polygon, value: float, color: str):
        # save a contour result

        storm_geo = self.psa_manifest_dataset.nsem.named_storm.geo  # type: geos.GEOSGeometry

        # fix any self-intersecting "bow ties"
        if not polygon.valid:
            polygon = polygon.buffer(0)

        # trim to storm's geo
        polygon = storm_geo.intersection(polygon)

        # skip empty results
        if polygon.empty:
            return

        # create psa result from contour result
        NsemPsaContour.objects.create(
            nsem_psa_variable=nsem_psa_variable,
            date=dt,
            geo=polygon,
            value=value,
            color=color,
        )

    def _save_psa_data(self, psa_variable: NsemPsaVariable, da: xr.DataArray, date=None):
        """
        perform a low level data copy into postgres via it's COPY mechanism which is much more
        efficient than using django's orm (even bulk_create) since it has to serialize every object
        https://www.postgresql.org/docs/9.4/sql-copy.html
        https://www.psycopg.org/docs/cursor.html#cursor.copy_from
        """

        logger.info('{}: saving psa data for {} at {}'.format(self.psa_manifest_dataset, psa_variable, date))

        # define database columns to copy to
        columns = [
            NsemPsaData.nsem_psa_variable.field.attname,
            NsemPsaData.point.field.attname,
            NsemPsaData.value.field.attname,
            NsemPsaData.date.field.attname,
        ]

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
            df['point'] = list(map(lambda p: geometry.Point(p[1], p[0]), list(zip(df['lat'], df['lon']))))
        # coordinates are a pandas MultiIndex so we can directly map them to points
        elif set(df.index.names).issuperset(['lat', 'lon']):
            df['point'] = df.index.map(lambda p: geometry.Point(p[1], p[0]))
        else:
            raise Exception('Expected lat and lon coordinates either as index or columns')

        # create geopandas dataframe and filter to storm's geo
        gdf = geopandas.GeoDataFrame(df)
        gdf = gdf.set_geometry('point')
        gdf = gdf[gdf.within(wkt.loads(self.psa_manifest_dataset.nsem.named_storm.geo.wkt))]

        # reorder gdf columns
        gdf = gdf[['psa_variable_id', 'point', psa_variable.name, 'time']]

        with tempfile.NamedTemporaryFile() as f:

            # write csv results to file-like object
            gdf.to_csv(f.name, header=False, index=False, na_rep=NULL_REPRESENT)
            f.seek(0)  # set file read position back to beginning

            # use default database connection
            with connections['default'].cursor() as cursor:

                start_time = time.time()

                # copy data into table using postgres COPY feature
                cursor.copy_from(f, NsemPsaData._meta.db_table, columns=columns, sep=',', null=NULL_REPRESENT)

                elapsed_time_copy = time.time() - start_time

        logger.info('{dataset}: finished saving psa data for {variable} at {date} (copy time={time_copy:.2f}s)'.format(
            dataset=self.psa_manifest_dataset, variable=psa_variable, date=date, time_copy=elapsed_time_copy))

    def _color_bar_values(self, nsem_psa_variable: NsemPsaVariable, z_min: float, z_max: float):
        # build color bar values

        color_values = []

        color_norm = matplotlib.colors.Normalize(vmin=z_min, vmax=z_max)
        step_intervals = np.linspace(z_min, z_max, COLOR_STEPS)

        for step_value in step_intervals:
            # round the step value for ranges greater than COLOR_STEPS
            if z_max - z_min >= COLOR_STEPS:
                step_value = np.math.ceil(step_value)
            hex_value = matplotlib.colors.to_hex(self._get_color_map(nsem_psa_variable)(color_norm(step_value)))
            color_values.append((step_value, hex_value))

        return color_values

    @staticmethod
    def _get_color_map(psa_variable: NsemPsaVariable):
        color_map_name = psa_variable.get_attribute('color_map')
        return matplotlib.cm.get_cmap(color_map_name)

    @staticmethod
    def _to_python_values(data: dict) -> dict:
        # converts numpy values to python native types
        return dict((key, value.item() if isinstance(value, np.generic) else value) for key, value in data.items())

    @staticmethod
    def signed_area(ring):
        # https://en.wikipedia.org/wiki/Shoelace_formula
        v2 = np.roll(ring, -1, axis=0)
        return np.cross(ring, v2).sum() / 2.0

    @classmethod
    def classify_polygons(cls, polygons) -> Tuple[List[geos.Polygon], List[geos.LinearRing]]:
        # classify polygons based on their area
        exteriors = []
        interiors = []
        for p in polygons:
            if cls.signed_area(p) >= 0:
                exteriors.append(geos.Polygon(p, srid=4326))
            else:
                interiors.append(geos.LinearRing(p))
        return exteriors, interiors

    @staticmethod
    def datetime64_to_datetime(dt64):
        unix_epoch = np.datetime64(0, 's')
        one_second = np.timedelta64(1, 's')
        seconds_since_epoch = (dt64 - unix_epoch) / one_second
        return datetime.utcfromtimestamp(seconds_since_epoch).replace(tzinfo=pytz.utc)
