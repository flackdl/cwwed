from importlib import import_module
from covered_data.models import NamedStorm
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.all():

            self.stdout.write(self.style.SUCCESS('Named Storm: "%s"' % storm.name))

            for data in storm.namedstormcovereddata_set.all():

                self.stdout.write(self.style.SUCCESS('\tCovered Data: "%s"' % data.name))

                for provider in data.namedstormcovereddataprovider_set.all():

                    self.stdout.write(self.style.SUCCESS('\t\tProvider: "%s"' % provider))

                    module = import_module('covered_data.providers')
                    collector = getattr(module, provider.provider_class)(provider)
                    collector.fetch()

                    if collector.success:
                        self.stdout.write(self.style.SUCCESS('\t\tSaved to: "%s"' % collector.success))
                    else:
                        self.stdout.write(self.style.WARNING('\t\tSuccess: "%s"' % collector.success))

