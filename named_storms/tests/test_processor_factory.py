from django.test import TestCase
from named_storms.data.factory import ProcessorBaseFactory


class DataFactoryTestCase(TestCase):
    def setUp(self):
        pass

    def test_decorator(self):
        """Data processors should automatically be registered via decorator"""
        self.assertTrue(len(ProcessorBaseFactory.registered_factories.keys()) > 0, 'Registered processor factories')
