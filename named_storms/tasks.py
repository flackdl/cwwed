from celery import shared_task
from named_storms.models import NamedStorm, PROCESSOR_DATA_SOURCE_NDBC, PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_TYPE_SEQUENCE
from named_storms.processors import NDBCProcessor, GridProcessor, SequenceProcessor


@shared_task
def collect_covered_data(storm_id: int):
    storm = NamedStorm.objects.get(id=storm_id)
    for data in storm.covered_data.filter(active=True):

        for provider in data.covereddataprovider_set.filter(active=True):

            if provider.processor.name == PROCESSOR_DATA_SOURCE_NDBC:
                processor = NDBCProcessor(storm, provider)
            else:
                if provider.data_type == PROCESSOR_DATA_TYPE_GRID:
                    processor = GridProcessor(storm, provider)
                elif provider.data_type == PROCESSOR_DATA_TYPE_SEQUENCE:
                    processor = SequenceProcessor(storm, provider)
                else:
                    raise Exception('no processor found for %s' % provider.processor.name)

            processor.fetch()

            # success - no need to continue with other providers
            if processor.is_success():
                break
    return True
