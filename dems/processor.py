import os
import re
import rasterio
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.contrib.gis import geos
from dateutil import parser
from ftplib import FTP

from dems.models import DemSource, Dem

logger = get_task_logger(__name__)


"""
Scan for updates to DEMs

Include geographical extent of the tile and its resolution.
We use the date of generation and resolution of a given tile as a criteria to give higher or lower priority to be included in the mesh generation process.

TODO:
    - notifications
    - api
"""


class DemSourceProcessor:
    dem_source: DemSource
    ftp: FTP = None

    def __init__(self, dem_source: DemSource):
        self.dem_source = dem_source

    def update_list(self):
        """
        Scan source and save detected changes
        """
        self.ftp = FTP(self.dem_source.get_host())
        self.ftp.login()

        # get all dem files
        dem_files = self._dem_files(self.dem_source.get_path())

        # added & updated dems
        dems_added = []
        dems_updated = []
        for dem_file in dem_files:

            dem_path = os.path.join(self.dem_source.get_path(), dem_file)

            # get modified date
            modified_result = self.ftp.voidcmd("MDTM {}".format(dem_path))
            modified_stamp = modified_result[4:]  # ie. '213 20191031195737'
            date_modified = timezone.utc.localize(parser.parse(modified_stamp))  # utc
            logger.info('found {} modified at {}'.format(dem_path, date_modified))

            # get or create dem
            dem, was_created = Dem.objects.get_or_create(
                source=self.dem_source,
                path=dem_file,
                defaults=dict(
                    date_updated=date_modified,
                ),
            )
            # added
            if was_created:
                dems_added.append(dem.path)
            # updated
            elif date_modified != dem.date_updated:
                # update date modified
                dem.date_updated = date_modified
                dem.save()
                dems_updated.append(dem.path)

        # removed dems
        existing_dems = self.dem_source.dem_set.values_list('path', flat=True)
        dems_removed = list(set(existing_dems).difference(dem_files))
        self.dem_source.dem_set.filter(path__in=dems_removed).delete()

        # add log entry
        self.dem_source.demsourcelog_set.create(
            date_scanned=timezone.now(),
            dems_added=dems_added,
            dems_updated=dems_updated,
            dems_removed=dems_removed,
        )
        logger.info('added: {}, updated: {}, removed: {}'.format(len(dems_added), len(dems_updated), len(dems_removed)))

    @staticmethod
    def update_dem(dem: Dem):
        # update dem metadata
        with rasterio.open(dem.get_url()) as dataset:  # type: rasterio.io.DatasetReader
            bbox = geos.Polygon.from_bbox(dataset.bounds)
            resolution = dataset.res[0]
            crs = str(dataset.crs)
            # update dem
            dem.boundary = bbox
            dem.resolution = resolution
            dem.crs = crs
            dem.save()

    @staticmethod
    def _is_dir(path: str) -> bool:
        # doesn't end with common extension (3-4 chars after period)
        return path and not re.search(r'\.\w{3,4}$', path)

    @staticmethod
    def _is_dem(path: str) -> bool:
        return path and path.endswith('.tif')

    def _dem_files(self, root_path) -> list:
        logger.info('recursively scanning {}'.format(root_path))
        dem_files = []
        # recursively retrieves files
        paths = self.ftp.nlst(root_path)
        for path in paths:
            if self._is_dir(path):
                dem_files += self._dem_files(path)
            elif self._is_dem(path):
                # capture dem source sub-path
                dem_files.append(Dem.get_sub_path(path, self.dem_source))
        return list(set(dem_files))
