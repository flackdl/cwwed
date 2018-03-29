from __future__ import absolute_import, unicode_literals
import requests
from django.shortcuts import get_object_or_404
from cwwed.celery import app
from named_storms.data.processors import ProcessorData
from named_storms.models import NamedStorm, CoveredDataProvider
from named_storms.utils import processor_class


DEFAULT_TASK_ARGS = dict(
    autoretry_for=(Exception,),
    default_retry_delay=5,
    max_retries=10,
)


@app.task(**DEFAULT_TASK_ARGS)
def fetch_url(url, verify=True, write_to_path=None):
    """
    :param url: URL to fetch
    :param verify: whether to verify ssl
    :param write_to_path: path to store the output vs returning it
    """
    stream = write_to_path is not None
    response = requests.get(url, verify=verify, stream=stream)
    response.raise_for_status()

    # save content
    if write_to_path is not None:
        with open(write_to_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        return None

    # return content
    return response.content.decode()  # must return bytes for serialization


@app.task(**DEFAULT_TASK_ARGS)
def process_dataset(data: list):
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
