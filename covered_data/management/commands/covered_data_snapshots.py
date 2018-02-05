from covered_data.models import NamedStorm
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Collect Covered Data Snapshots'

    def handle(self, *args, **options):
        for storm in NamedStorm.objects.all():
            self.stdout.write(self.style.SUCCESS('Named Storm: "%s"' % storm.name))
            for data in storm.covereddata_set.all():
                self.stdout.write(self.style.SUCCESS('\tCovered Data: "%s"' % data.name))
                for provider in data.providers.all():
                    self.stdout.write(self.style.SUCCESS('\t\tProvider: "%s"' % provider))
