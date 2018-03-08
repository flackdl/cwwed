from celery import shared_task
from named_storms.models import NamedStorm


@shared_task
def add(x, y):
    return x + y


@shared_task
def collect_covered_data(storm: NamedStorm):
    pass
