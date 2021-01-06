from django.urls import reverse
from rest_framework.status import HTTP_403_FORBIDDEN, HTTP_200_OK

from coastal_act.models import CoastalActProject
from named_storms.tests.base import BaseTest


class ApiPermissionTestCase(BaseTest):

    def setUp(self):
        super().setUp()

        # get the first coastal act project
        self.coastal_act_project = CoastalActProject.objects.all().first()  # type: CoastalActProject

    def test_coastal_act_projects(self):
        # list
        result = self.client.get(reverse('coastalactproject-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('coastalactproject-detail', args=[self.coastal_act_project.id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

        # patch
        result = self.client.patch(reverse('coastalactproject-detail', args=[self.coastal_act_project.id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

    def test_named_storms(self):
        # list
        result = self.client.get(reverse('namedstorm-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('namedstorm-detail', args=[self.named_storm.id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

        # patch
        result = self.client.patch(reverse('namedstorm-detail', args=[self.named_storm.id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

    def test_covered_data(self):
        # list
        result = self.client.get(reverse('covereddata-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('covereddata-detail', args=[self.named_storm.covered_data.first().id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

        # patch
        result = self.client.patch(reverse('covereddata-detail', args=[self.named_storm.covered_data.first().id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

    def test_nsem_psa(self):
        # list
        result = self.client.get(reverse('nsempsa-list'))
        self.assertEqual(result.status_code, HTTP_200_OK)

        # delete
        result = self.client.delete(reverse('nsempsa-detail', args=[self.named_storm.nsempsa_set.first().id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)

        # patch
        result = self.client.patch(reverse('nsempsa-detail', args=[self.named_storm.nsempsa_set.first().id]))
        self.assertEqual(result.status_code, HTTP_403_FORBIDDEN)
