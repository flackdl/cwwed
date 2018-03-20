import os
import errno
import shutil
from django.conf import settings
from named_storms.models import PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_TYPE_SEQUENCE, CoveredDataProvider, NamedStorm


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
    Returns a processor class for a provider or throws an exception if not found
    """
    from named_storms.data.processors import GridProcessor, SequenceProcessor
    if provider.data_type == PROCESSOR_DATA_TYPE_GRID:
        return GridProcessor
    elif provider.data_type == PROCESSOR_DATA_TYPE_SEQUENCE:
        return SequenceProcessor
    else:
        raise Exception('no processor class found for data type %s' % provider.data_type)


def named_storm_covered_data_path(named_storm: NamedStorm):
    """
    Returns a path to a storm's covered data
    """
    return '{}/{}/{}'.format(
        settings.CWWED_DATA_DIR,
        named_storm,
        settings.CWWED_COVERED_DATA_DIR_NAME,
    )


def named_storm_covered_data_incomplete_path(named_storm: NamedStorm):
    """
    Returns a path to a storm's temporary/incomplete covered data
    """
    return '{}/{}'.format(
        named_storm_covered_data_path(named_storm),
        settings.CWWED_COVERED_DATA_INCOMPLETE_DIR_NAME,
    )


def named_storm_covered_data_archive_path(named_storm: NamedStorm):
    """
    Returns a path to a storm's covered data archive
    """
    return '{}/{}'.format(
        named_storm_covered_data_path(named_storm),
        settings.CWWED_COVERED_DATA_ARCHIVE_DIR_NAME,
    )
