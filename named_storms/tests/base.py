from django.test import TestCase, Client
from django.core.management import call_command

from named_storms.models import NamedStorm, NsemPsa


class BaseTest(TestCase):
    client = None

    def setUp(self):
        # load dev data
        call_command('loaddata', 'dev-db.json')

        # get the first named storm
        self.named_storm = NamedStorm.objects.all().first()  # type: NamedStorm

        self.nsem_psa = NsemPsa.get_last_valid_psa(self.named_storm.id)

        # get the request client
        self.client = Client()
