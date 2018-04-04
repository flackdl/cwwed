from __future__ import absolute_import, unicode_literals
import shutil
import os
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from cwwed.celery import app
from named_storms.data.processors import ProcessorData
from named_storms.models import NamedStorm, CoveredDataProvider, CoveredData, NamedStormCoveredDataLog
from named_storms.utils import processor_class, named_storm_covered_data_archive_path

RETRY_ARGS = dict(
    autoretry_for=(Exception,),
    default_retry_delay=5,
    max_retries=10,
)


@app.task(**RETRY_ARGS)
def fetch_url_task(url, verify=True, write_to_path=None):
    """
    :param url: URL to fetch
    :param verify: whether to verify ssl
    :param write_to_path: path to store the output vs returning it
    """
    stream = write_to_path is not None
    response = requests.get(url, verify=verify, timeout=10, stream=stream)
    response.raise_for_status()

    # save content
    if write_to_path is not None:
        with open(write_to_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return None

    # return content
    return response.content.decode()  # must return bytes for serialization


@app.task(**RETRY_ARGS)
def process_dataset_task(data: list):
    """
    Run the dataset processor
    """
    processor_data = ProcessorData(*data)
    named_storm = get_object_or_404(NamedStorm, pk=processor_data.named_storm_id)
    provider = get_object_or_404(CoveredDataProvider, pk=processor_data.provider_id)
    processor_cls = processor_class(provider)
    processor = processor_cls(
        named_storm=named_storm,
        provider=provider,
        url=processor_data.url,
        label=processor_data.label,
        group=processor_data.group,
    )
    processor.fetch()
    return processor.to_dict()


@app.task  # no retry
def archive_named_storm_covered_data(named_storm_id, covered_data_id, log_id):
    """
    :param named_storm_id: id for a NamedStorm record
    :param covered_data_id: id for a CoveredData record
    :param log_id: id for a NamedStormCoveredDataLog
    """
    named_storm = get_object_or_404(NamedStorm, pk=named_storm_id)
    covered_data = get_object_or_404(CoveredData, pk=covered_data_id)
    log = get_object_or_404(NamedStormCoveredDataLog, pk=log_id)
    archive_path = named_storm_covered_data_archive_path(named_storm, covered_data)

    # create archive
    path = shutil.make_archive(
        base_name=archive_path,
        format=settings.CWWED_COVERED_DATA_ARCHIVE_TYPE,
        root_dir=os.path.dirname(archive_path),
        base_dir=covered_data.name,
    )

    # save the output in the log
    log.snapshot = path
    log.save()

    return path
