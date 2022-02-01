from django.core.management import BaseCommand
from named_storms.models import NamedStorm, CoveredData


class Command(BaseCommand):
    help = 'Apply covered data records to a new storm'

    def add_arguments(self, parser):
        parser.add_argument('--storm_id', type=int, required=True)

    def handle(self, *args, **options):
        storm = NamedStorm.objects.get(pk=options['storm_id'])
        # verify covered data hasn't been assigned yet for this storm
        if storm.namedstormcovereddata_set.exists():
            raise RuntimeError('Cannot assign covered data since {} already has some assigned'.format(storm))
        # assign all covered data using the storm's dates & geo
        for covered_data in CoveredData.objects.all():
            storm.namedstormcovereddata_set.create(
                covered_data=covered_data,
                date_start=storm.date_start,
                date_end=storm.date_end,
                dates_required=True,
                geo=storm.geo,
            )
            self.stdout.write(self.style.SUCCESS('Assigned {} to {}'.format(covered_data, storm)))
