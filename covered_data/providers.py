import logging
import requests
from django.conf import settings
from pydap.client import open_url
from requests import HTTPError
from covered_data.models import NamedStormCoveredDataProvider


class OpenDapProvider:
    DEFAULT_DIMENSIONS = {'time', 'longitude', 'latitude'}
    provider = None  # type: NamedStormCoveredDataProvider
    output_path = None  # type: str
    request_url = None  # type: str
    success = None  # type: bool
    protocol = None  # type: str
    response_type = 'nc'

    def __init__(self, provider: NamedStormCoveredDataProvider):
        self.provider = provider

    def fetch(self):
        try:
            self._fetch()
        except (HTTPError,) as e:
            self.success = False
            logging.warning('HTTPError: %s' % str(e))
        except Exception as e:
            self.success = False
            logging.warning('Exception: %s' % str(e))

    def _fetch(self):

        # fetch data
        url = '{}.{}'.format(self.provider.source, self.response_type)
        response = requests.get(url, params=self._get_constraints())
        self.request_url = response.url
        logging.info('URL: %s' % self.request_url)
        response.raise_for_status()

        # store output
        self.output_path = '{}/{}_{}.{}'.format(
            settings.COVERED_DATA_CACHE_DIR,
            self.provider.covered_data.named_storm.name.replace(' ', '-'),
            self.provider.covered_data.name.replace(' ', '-'),
            self.response_type,
        )
        with open(self.output_path, 'wb') as fd:
            fd.write(response.content)

        self.success = response.ok

    def _get_constraints(self):
        constraints = []

        dataset = open_url(self.provider.source)
        variables = set(dataset.keys())
        if not self.DEFAULT_DIMENSIONS.issubset(variables):
            raise Exception('missing expected dimensions')
        # remove the dimensions from the variables
        variables = set(dataset.keys()).difference(self.DEFAULT_DIMENSIONS)

        if self.protocol == 'griddap':

            # time
            # [(2018-02-01)(2018-02-08T12:00:00Z)]
            constraints.append('[({}):({})]'.format(
                self.provider.covered_data.named_storm.date_start.isoformat(),
                self.provider.covered_data.named_storm.date_end.isoformat(),
            ))

            extent = self._storm_extent()

            # latitude
            # [(11)(90.0)]
            constraints.append('[({}):({})]'.format(
                extent[1],
                extent[3],
            ))
            # longitude
            # [(256)(359.5)]
            constraints.append('[({}):({})]'.format(
                extent[0],
                extent[2],
            ))
            return ','.join(['{}{}'.format(v, ''.join(constraints)) for v in variables])

        elif self.protocol == 'tabledap':
            raise NotImplementedError
        else:
            raise Exception('Invalid ERDDAP protocol "{}"'.format(self.protocol))

    def _storm_extent(self):
        # extent/boundaries of storm
        # i.e (-97.55859375, 28.23486328125, -91.0107421875, 33.28857421875)
        extent = self.provider.covered_data.named_storm.geo.extent
        # convert lat/lng to positive-only values (ie. degrees_east and degrees_north)
        # i.e (262.44, 28.23486328125, 268.98, 33.28857421875)
        extent = (
            extent[0] if extent[0] > 0 else 360 + extent[0],
            extent[1] if extent[1] > 0 else 360 + extent[1],
            extent[2] if extent[2] > 0 else 360 + extent[2],
            extent[3] if extent[3] > 0 else 360 + extent[3],
        )
        return extent


class GriddapProvider(OpenDapProvider):
    protocol = 'griddap'


class TabledapProvider(OpenDapProvider):
    protocol = 'tabledap'
