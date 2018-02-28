from named_storms.models import NamedStorm, PROCESSOR_DATA_TYPE_SEQUENCE, PROCESSOR_DATA_TYPE_GRID, PROCESSOR_DATA_SOURCE_NDBC
from django.core.management.base import BaseCommand
from named_storms.processors import GridProcessor, SequenceProcessor, NDBCProcessor


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.all():

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm.name))

            for data in storm.namedstormcovereddata_set.all().filter(active=True):

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data.name))

                for provider in data.namedstormcovereddataprovider_set.all().filter(active=True):

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: %s' % provider))

                    if provider.processor.name == PROCESSOR_DATA_SOURCE_NDBC:
                        processor = NDBCProcessor(provider)
                    else:
                        if provider.data_type == PROCESSOR_DATA_TYPE_GRID:
                            processor = GridProcessor(provider)
                        elif provider.data_type == PROCESSOR_DATA_TYPE_SEQUENCE:
                            processor = SequenceProcessor(provider)
                        else:
                            raise Exception('no processor found for %s' % provider.processor.name)

                    for request in processor.data_requests:
                        self.stdout.write(self.style.WARNING('\t\tURL: %s' % request.url))

                    processor.fetch()

                    if processor.is_success():
                        self.stdout.write(self.style.SUCCESS('\t\tSUCCESS'))
                        for request in processor.data_requests:
                            self.stdout.write(self.style.SUCCESS('\t\tSaved to: %s' % request.output_path))
                        self.stdout.write(self.style.WARNING('\t\tSkipping additional providers'))
                        break
                    else:
                        self.stdout.write(self.style.ERROR('\t\tFailed'))
                        self.stdout.write(self.style.WARNING('\t\tTrying next provider'))
