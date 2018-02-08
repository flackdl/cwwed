from importlib import import_module
from covered_data.models import NamedStorm
from django.core.management.base import BaseCommand
from covered_data.providers import OpenDapProvider


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.all():

            self.stdout.write(self.style.SUCCESS('Named Storm: "%s"' % storm.name))

            for data in storm.namedstormcovereddata_set.all():

                self.stdout.write(self.style.SUCCESS('\tCovered Data: "%s"' % data.name))

                for provider in data.namedstormcovereddataprovider_set.all():

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: "%s"' % provider))

                    # import provider class to perform the fetching
                    module = import_module('covered_data.providers')
                    collector = getattr(module, provider.provider_class)(provider)  # type: OpenDapProvider
                    collector.fetch()

                    self.stdout.write(self.style.WARNING('\t\tURL: "%s"' % collector.request_url))

                    if collector.success:
                        self.stdout.write(self.style.SUCCESS('\t\tSaved to: "%s"' % collector.output_path))
                        self.stdout.write(self.style.WARNING('\t\tSuccess, so skipping additional providers'))
                        break
                    else:
                        self.stdout.write(self.style.ERROR('\t\tFailed'))
                        self.stdout.write(self.style.WARNING('\t\tTrying next provider'))

