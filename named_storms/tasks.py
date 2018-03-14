from __future__ import absolute_import, unicode_literals
import requests
from django.shortcuts import get_object_or_404
from cwwed.celery import app
from named_storms.data.processors import ProcessorData
from named_storms.models import NamedStorm, CoveredDataProvider
from named_storms.utils import processor_class


@app.task(autoretry_for=(Exception,), ignore_result=True)
def fetch_url(url, verify=True):
    response = requests.get(url, verify=verify)
    response.raise_for_status()
    return response.content.decode()  # must return bytes for serialization


@app.task(autoretry_for=(Exception,), default_retry_delay=5, max_retries=10)
def process_dataset(data: list):
    """
    :rtype data: list of values for ProcessorData
    :return:
    """
    data = ProcessorData(*data)
    named_storm = get_object_or_404(NamedStorm, pk=data.named_storm_id)
    provider = get_object_or_404(CoveredDataProvider, pk=data.provider_id)
    processor_cls = processor_class(provider)
    processor = processor_cls(
        named_storm=named_storm,
        provider=provider,
        url=data.url,
        label=data.label,
    )
    processor.fetch()
    return processor.output_path
