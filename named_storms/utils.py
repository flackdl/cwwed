import os
import errno
import shutil
import tarfile
from django.conf import settings

from named_storms.models import PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_TYPE_SEQUENCE, CoveredDataProvider, NamedStorm, NSEM


def remove_directory(path):
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def create_directory(path, remove_if_exists=False):
    if remove_if_exists:
        remove_directory(path)
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return path


def processor_class(provider: CoveredDataProvider):
    """
    Returns a processor class for a provider
    """
    from named_storms.data.processors import GridProcessor, SequenceProcessor, GenericFileProcessor
    if provider.data_type == PROCESSOR_DATA_TYPE_GRID:
        return GridProcessor
    elif provider.data_type == PROCESSOR_DATA_TYPE_SEQUENCE:
        return SequenceProcessor
    else:
        return GenericFileProcessor


def named_storm_path(named_storm: NamedStorm):
    """
    Returns a path to a storm's data (top level directory)
    """
    return os.path.join(
        settings.CWWED_DATA_DIR,
        named_storm.name,
    )


def named_storm_covered_data_path(named_storm: NamedStorm):
    """
    Returns a path to a storm's covered data
    """
    return os.path.join(
        named_storm_path(named_storm),
        settings.CWWED_COVERED_DATA_DIR_NAME,
    )


def named_storm_covered_data_incomplete_path(named_storm: NamedStorm):
    """
    Returns a path to a storm's temporary/incomplete covered data
    """
    return os.path.join(
        named_storm_covered_data_path(named_storm),
        settings.CWWED_COVERED_DATA_INCOMPLETE_DIR_NAME,
    )


def named_storm_nsem_path(nsem: NSEM):
    """
    Returns a path to a storm's NSEM product
    """
    return os.path.join(
        named_storm_path(nsem.named_storm),
        settings.CWWED_NSEM_DIR_NAME,
    )


def named_storm_nsem_version_path(nsem: NSEM):
    """
    Returns a path to a storm's NSEM product's version
    """
    return os.path.join(
        named_storm_nsem_path(nsem),
        'v{}'.format(nsem.id))


def archive_nsem_covered_data(nsem: NSEM):
    """
    Archives all the covered data for a storm to pass off to the external NSEM
    """

    # retrieve all the successful covered data by querying the logs
    # sort by date descending and retrieve unique results
    logs = nsem.named_storm.namedstormcovereddatalog_set.filter(success=True).order_by('-date')
    if not logs.exists():
        return None
    logs_to_archive = []
    for log in logs:
        if log.covered_data.name not in [l.covered_data.name for l in logs_to_archive]:
            logs_to_archive.append(log)

    # create archive path, i.e "Harvey/NSEM/v3/" and open the archive file for writing
    archive_path = named_storm_nsem_version_path(nsem)
    create_directory(archive_path)
    archive_file = os.path.join(archive_path, settings.CWWED_NSEM_ARCHIVE_INPUT_NAME)
    tar = tarfile.open(archive_file, mode=settings.CWWED_NSEM_ARCHIVE_WRITE_MODE)

    # add each snapshot to the archive
    for log in logs_to_archive:
        tar.add(log.snapshot, arcname=os.path.basename(log.snapshot))
    tar.close()

    return archive_file
