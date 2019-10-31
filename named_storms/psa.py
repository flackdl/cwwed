import os
import logging
from datetime import datetime
import matplotlib.colors
import matplotlib.pyplot as plt
import matplotlib.cm
import pytz
import xarray as xr
import numpy as np
from django.contrib.gis import geos

from named_storms.models import NsemPsaManifestDataset, NsemPsaVariable, NsemPsaData
from named_storms.utils import named_storm_nsem_version_path


logger = logging.getLogger('cwwed')

COLOR_STEPS = 10  # color bar range


class PsaDataset:
    cmap = matplotlib.cm.get_cmap('jet')

    def __init__(self, psa_manifest_dataset: NsemPsaManifestDataset):
        self.psa_manifest_dataset = psa_manifest_dataset
        self.dataset: xr.Dataset = xr.open_dataset(os.path.join(
            named_storm_nsem_version_path(self.psa_manifest_dataset.nsem),
            psa_manifest_dataset.path)
        )

    @staticmethod
    def datetime64_to_datetime(dt64):
        unix_epoch = np.datetime64(0, 's')
        one_second = np.timedelta64(1, 's')
        seconds_since_epoch = (dt64 - unix_epoch) / one_second
        return datetime.utcfromtimestamp(seconds_since_epoch).replace(tzinfo=pytz.utc)

    def ingest(self):
        for variable in self.dataset.variables:

            if variable == NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED:
                psa_variable, _ = self.psa_manifest_dataset.nsem.nsempsavariable_set.get_or_create(
                    name=variable,
                    defaults=dict(
                        geo_type=NsemPsaVariable.get_variable_attribute(NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED, 'geo_type'),
                        data_type=NsemPsaVariable.get_variable_attribute(NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED, 'data_type'),
                        element_type=NsemPsaVariable.get_variable_attribute(NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED, 'element_type'),
                        units=NsemPsaVariable.get_variable_attribute(NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED, 'units'),
                    )
                )

                #
                # contours
                #

                for date in self.dataset['time']:
                    # capture date and convert to datetime
                    dt = self.datetime64_to_datetime(date)

                    wind_speeds = self.dataset.sel(time=date)[variable].values

                    wind_speeds_data_array = xr.DataArray(wind_speeds, name='wind')

                    self.build_contours_structured(psa_variable, wind_speeds_data_array, dt)

                psa_variable.color_bar = self.color_bar_values(self.dataset[variable].min(), self.dataset[variable].max())

    def build_contours_structured(self, nsem_psa_variable: NsemPsaVariable, zi: xr.DataArray, dt: datetime = None):

        logger.info('building contours (structured) for {} at {}'.format(nsem_psa_variable, dt))

        # create the contour
        contourf = plt.contourf(self.dataset.lon, self.dataset.lat, zi, cmap=self.cmap)

        self.build_contours(nsem_psa_variable, contourf, dt)

    def build_contours(self, nsem_psa_variable: NsemPsaVariable, contourf, dt=None):

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
                    'color': matplotlib.colors.to_hex(self.cmap(contourf.norm(value))),
                })

        # build new psa results from contour results
        for result in results:
            NsemPsaData(
                nsem_psa_variable=nsem_psa_variable,
                date=dt,
                geo=result['polygon'],
                bbox=geos.Polygon.from_bbox(result['polygon'].extent),
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
