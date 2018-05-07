import os
import errno
import shutil
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

from named_storms.models import (
    PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_TYPE_SEQUENCE, CoveredDataProvider, NamedStorm, NSEM, CoveredData,
)


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


def named_storm_path(named_storm: NamedStorm) -> str:
    """
    Returns a path to a storm's data (top level directory)
    """
    return os.path.join(
        settings.CWWED_DATA_DIR,
        settings.CWWED_THREDDS_DIR,
        named_storm.name,
    )


def named_storm_covered_data_path(named_storm: NamedStorm) -> str:
    """
    Returns a path to a storm's covered data
    """
    return os.path.join(
        named_storm_path(named_storm),
        settings.CWWED_COVERED_DATA_DIR_NAME,
    )


def named_storm_covered_data_incomplete_path(named_storm: NamedStorm) -> str:
    """
    Returns a path to a storm's temporary/incomplete covered data
    """
    return os.path.join(
        named_storm_covered_data_path(named_storm),
        settings.CWWED_COVERED_DATA_INCOMPLETE_DIR_NAME,
    )


def named_storm_covered_data_archive_path(named_storm: NamedStorm, covered_data: CoveredData) -> str:
    """
    Returns a path to a storm's covered data archive
    """
    return os.path.join(
        named_storm_covered_data_path(named_storm),
        covered_data.name,
    )


def named_storm_nsem_path(nsem: NSEM) -> str:
    """
    Returns a path to a storm's NSEM product
    """
    return os.path.join(
        named_storm_path(nsem.named_storm),
        settings.CWWED_NSEM_DIR_NAME,
    )


def named_storm_nsem_version_path(nsem: NSEM) -> str:
    """
    Returns a path to a storm's NSEM product's version
    """
    return os.path.join(
        named_storm_nsem_path(nsem),
        'v{}'.format(nsem.id))


def copy_path_to_default_storage(source_path: str, destination_path: str):
    """
    Copies source to destination using "default_storage" and returns the path
    """
    # copy path to default storage
    with File(open(source_path, 'rb')) as fd:

        # remove any existing storage
        if default_storage.exists(destination_path):
            default_storage.delete(destination_path)
        default_storage.save(destination_path, fd)

    return destination_path
