import re
from celery.utils.log import get_task_logger
from dataclasses import dataclass
from urllib.parse import urlparse
from django.utils import timezone
from dateutil import parser
from ftplib import FTP

from dems.models import DemSource, Dem

logger = get_task_logger(__name__)


@dataclass
class DemSourceProcessor:
    dem_source: DemSource
    ftp: FTP = None

    def update(self):
        # connect to dem source
        parsed = urlparse(self.dem_source.url)
        host = parsed.hostname
        path = parsed.path
        self.ftp = FTP(host)
        self.ftp.login()

        # get all dem files
        dem_files = self._dem_files(path)
        logger.info(dem_files)

        # added & updated dems
        dems_added = []
        dems_updated = []
        for dem_file in dem_files:
            modified_result = self.ftp.voidcmd("MDTM {}".format(dem_file))
            modified_stamp = modified_result[4:]  # ie. '213 20191031195737'
            date_modified = timezone.utc.localize(parser.parse(modified_stamp))  # utc
            logger.info('{} was modified: {}'.format(dem_file, date_modified))
            dem, was_created = Dem.objects.update_or_create(
                source=self.dem_source,
                path=dem_file,
                date_updated=date_modified,
            )
            if was_created:
                dems_added.append(dem.path)
            else:
                dems_updated.append(dem.path)

        # removed dems
        source_dems = self.dem_source.dem_set.values_list('path', flat=True)
        dems_removed = list(set(source_dems).difference(dem_files))

        # add log entry
        self.dem_source.demsourcelog_set.create(
            date_scanned=timezone.now(),
            dems_added=dems_added,
            dems_updated=dems_updated,
            dems_removed=dems_removed,
        )

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
                dem_files.append(path)
        return list(set(dem_files))

