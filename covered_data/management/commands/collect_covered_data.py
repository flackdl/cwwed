from covered_data.models import NamedStorm, PROCESSOR_DATA_TYPE_SEQUENCE, PROCESSOR_DATA_TYPE_GRID
from django.core.management.base import BaseCommand
from covered_data.processors import GridProcessor, SequenceProcessor


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.all():

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm.name))

            for data in storm.namedstormcovereddata_set.all():

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data.name))

                for provider in data.namedstormcovereddataprovider_set.all().filter(active=True):

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: %s' % provider))

                    if provider.processor.name == PROCESSOR_DATA_TYPE_GRID:
                        processor = GridProcessor(provider)
                    elif provider.processor.name == PROCESSOR_DATA_TYPE_SEQUENCE:
                        processor = SequenceProcessor(provider)
                    else:
                        raise Exception('no processor found for %s' % provider.processor.name)

                    self.stdout.write(self.style.WARNING('\t\tURL: %s' % processor.request_url))

                    processor.fetch()

                    if processor.success:
                        self.stdout.write(self.style.SUCCESS('\t\tSUCCESS'))
                        self.stdout.write(self.style.SUCCESS('\t\tSaved to: %s' % processor.output_path))
                        self.stdout.write(self.style.WARNING('\t\tSkipping additional providers'))
                        break
                    else:
                        self.stdout.write(self.style.ERROR('\t\tFailed'))
                        self.stdout.write(self.style.WARNING('\t\tTrying next provider'))
