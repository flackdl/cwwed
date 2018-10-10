import os
import errno
import shutil
from urllib import parse
from django.http.request import HttpRequest
from django.contrib.auth.models import User
from django.conf import settings
from django.core.files import File

from cwwed import slack
from named_storms.models import (
    CoveredDataProvider, NamedStorm, NSEM, CoveredData, PROCESSOR_DATA_SOURCE_FILE_GENERIC, PROCESSOR_DATA_SOURCE_FILE_BINARY, PROCESSOR_DATA_SOURCE_DAP,
    PROCESSOR_DATA_SOURCE_FILE_HDF,
)


def slack_channel(message: str, channel='#errors'):
    slack.chat.post_message(channel, message)


def create_directory(path, remove_if_exists=False):
    if remove_if_exists:
        shutil.rmtree(path, ignore_errors=True)
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return path


def processor_class(provider: CoveredDataProvider):
    """
    Returns a processor class from a provider instance
    """
    from named_storms.data.processors import GridOpenDapProcessor, GenericFileProcessor, BinaryFileProcessor, HierarchicalDataFormatProcessor
    sources = {
        PROCESSOR_DATA_SOURCE_FILE_BINARY: BinaryFileProcessor,
        PROCESSOR_DATA_SOURCE_FILE_GENERIC: GenericFileProcessor,
        PROCESSOR_DATA_SOURCE_FILE_HDF: HierarchicalDataFormatProcessor,
        PROCESSOR_DATA_SOURCE_DAP: GridOpenDapProcessor,
    }
    match = sources.get(provider.processor_source)
    if match is None:
        raise Exception('Unknown processor source')
    return match


def processor_factory_class(provider: CoveredDataProvider):
    """
    Each factory is decorated/registered to map it's name to itself which helps us map the two later on during processing
    :return: ProcessorCoreFactory class/sub-class for a particular provider
    """
    # import locally to prevent circular dependencies
    from named_storms.data.factory import ProcessorBaseFactory
    return ProcessorBaseFactory.registered_factories[provider.processor_factory]


def root_data_path() -> str:
    return settings.CWWED_DATA_DIR


def named_storm_path(named_storm: NamedStorm) -> str:
    """
    Returns a path to a storm's data (top level directory)
    """
    return os.path.join(
        root_data_path(),
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
        root_data_path(),
        settings.CWWED_COVERED_DATA_INCOMPLETE_DIR_NAME,
        named_storm.name,
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
    Copies source to destination using object storage and returns the path
    """
    from cwwed.storage_backends import S3ObjectStoragePrivate  # local import prevents circular dependency

    # copy path to default storage
    with File(open(source_path, 'rb')) as fd:
        storage = S3ObjectStoragePrivate()

        # remove any existing storage
        if storage.exists(destination_path):
            storage.delete(destination_path)
        storage.save(destination_path, fd)

    return destination_path


def get_superuser_emails():
    return [u.email for u in User.objects.filter(is_superuser=True) if u.email]


def get_thredds_url_root(request: HttpRequest) -> str:
    return '{}://{}'.format(
        request.scheme,
        os.path.join(
            request.get_host(),
            'thredds',
            'catalog',
            'cwwed',
        ))


def get_thredds_url_named_storm_root(request: HttpRequest, named_storm: NamedStorm) -> str:
    return os.path.join(
        get_thredds_url_root(request),
        parse.quote(named_storm.name),
    )


def get_thredds_url_nsem_root(request: HttpRequest, nsem: NSEM) -> str:
    return os.path.join(
        get_thredds_url_named_storm_root(request, nsem.named_storm),
        parse.quote(settings.CWWED_NSEM_DIR_NAME),
        'v{}'.format(nsem.id),
    )


def get_thredds_url_nsem(request: HttpRequest, nsem: NSEM) -> str:
    return os.path.join(
        get_thredds_url_nsem_root(request, nsem),
        'catalog.html',
    )


def get_thredds_url_nsem_psa(request: HttpRequest, nsem: NSEM) -> str:
    return os.path.join(
        get_thredds_url_nsem_root(request, nsem),
        parse.quote(settings.CWWED_NSEM_PSA_DIR_NAME),
        'catalog.html',
    )


def get_thredds_url_nsem_covered_data_root(request: HttpRequest, nsem: NSEM) -> str:
    return os.path.join(
        get_thredds_url_nsem_root(request, nsem),
        parse.quote(settings.CWWED_COVERED_DATA_DIR_NAME),
    )


def get_thredds_url_nsem_covered_data(request: HttpRequest, nsem: NSEM, covered_data: CoveredData) -> str:
    return os.path.join(
        get_thredds_url_nsem_covered_data_root(request, nsem),
        parse.quote(covered_data.name),
        'catalog.html',
    )
