from named_storms.data.factory import NDBCProcessorFactory, ProcessorFactory
from named_storms.models import NamedStorm, PROCESSOR_DATA_SOURCE_NDBC
from django.core.management.base import BaseCommand

from named_storms.tasks import process_dataset


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.filter(active=True):

            self.stdout.write(self.style.SUCCESS('Named Storm: %s' % storm.name))

            for data in storm.covered_data.filter(active=True):

                self.stdout.write(self.style.SUCCESS('\tCovered Data: %s' % data))

                for provider in data.covereddataprovider_set.filter(active=True):

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: %s' % provider))

                    if provider.processor.name == PROCESSOR_DATA_SOURCE_NDBC:
                        factory = NDBCProcessorFactory(storm, provider)
                    else:
                        factory = ProcessorFactory(storm, provider)

                    for processor_data in factory.processors_data():
                        self.stdout.write(self.style.WARNING('\t\tURL: %s' % processor_data.url))
                        process_dataset.delay(processor_data)

                    # TODO - use callbacks to determine if they all succeeded
                    # TODO - save output to an intermediate location and then swap? timestamp?

                    #for processor in factory.processors():
                    #    self.stdout.write(self.style.WARNING('\t\tURL: %s' % processor.url))

                    #    processor.fetch()

                    #    if processor.success:
                    #        self.stdout.write(self.style.SUCCESS('\t\tSUCCESS'))
                    #        self.stdout.write(self.style.SUCCESS('\t\tSaved to: %s' % processor.output_path))
                    #        self.stdout.write(self.style.WARNING('\t\tSkipping additional providers'))
                    #        # skip additional providers since this was successful
                    #        break
                    #    else:
                    #        self.stdout.write(self.style.ERROR('\t\tFailed'))
                    #        self.stdout.write(self.style.WARNING('\t\tTrying next provider'))
