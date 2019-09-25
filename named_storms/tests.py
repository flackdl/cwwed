from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_200_OK

from coastal_act.models import CoastalActProject
from named_storms.data.factory import ProcessorBaseFactory
from named_storms.models import NamedStorm


class DataFactoryTestCase(TestCase):
    def setUp(self):
        pass

    def test_decorator(self):
        """Data processors should automatically be registered via decorator"""
        self.assertTrue(len(ProcessorBaseFactory.registered_factories.keys()) > 0, 'Registered processor factories')


class ApiPermissionTestCase(TestCase):
    client = None

    def setUp(self):
        # load dev data
        call_command('loaddata', 'dev-db.json')

        # get the first named storm
        self.named_storm = NamedStorm.objects.all().first()  # type: NamedStorm

        # get the first coastal act project
        self.coastal_act_project = CoastalActProject.objects.all().first()  # type: CoastalActProject

        # create a psa record
        self.named_storm.nsempsa_set.create()

        # get the request client
        self.client = Client()

    def test_coastal_act_projects(self):
        # list
        result = self.client.get(reverse('coastalactproject-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('coastalactproject-detail', args=[self.coastal_act_project.id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

    def test_named_storms(self):
        # list
        result = self.client.get(reverse('namedstorm-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('namedstorm-detail', args=[self.named_storm.id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

    def test_covered_data(self):
        # list
        result = self.client.get(reverse('covereddata-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('covereddata-detail', args=[self.named_storm.covered_data.first().id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

    def test_nsem_psa(self):
        # list
        result = self.client.get(reverse('nsempsa-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('nsempsa-detail', args=[self.named_storm.nsempsa_set.first().id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)
