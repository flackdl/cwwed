import csv
import logging
from celery import chain
from django.core.cache import caches, BaseCache
from django.db.models.functions import Cast
from django.http import JsonResponse, HttpResponse
from django.utils.cache import get_cache_key, learn_cache_key
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.gis import geos
from django.views.decorators.gzip import gzip_page
from django.views.decorators.cache import cache_control
from django.contrib.gis.db.models import Collect, GeometryField
from rest_framework import viewsets
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response

from named_storms.api.filters import NsemPsaDataFilter
from named_storms.api.mixins import UserReferenceViewSetMixin
from named_storms.tasks import (
    archive_nsem_covered_data_task, extract_nsem_psa_task, email_psa_covered_data_complete_task,
    extract_nsem_covered_data_task, create_psa_user_export_task,
    email_psa_user_export_task, validate_nsem_psa_task, email_psa_validated_task)
from named_storms.models import NamedStorm, CoveredData, NsemPsa, NsemPsaVariable, NsemPsaData, NsemPsaUserExport
from named_storms.api.serializers import (
    NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NsemPsaSerializer, NsemPsaVariableSerializer, NsemPsaUserExportSerializer,
)
from named_storms.utils import get_geojson_feature_collection_from_psa_qs


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Named Storms
    """
    queryset = NamedStorm.objects.all()
    serializer_class = NamedStormSerializer
    filterset_fields = ('name',)

    def get_serializer_class(self):
        # return a more detailed representation for a specific storm
        if self.action == 'retrieve':
            return NamedStormDetailSerializer
        return super().get_serializer_class()


class CoveredDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoveredData.objects.all()
    serializer_class = CoveredDataSerializer


class NsemPsaViewSet(viewsets.ModelViewSet):
    """
    Named Storm Event Model ViewSet
    """
    queryset = NsemPsa.objects.all()
    serializer_class = NsemPsaSerializer
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    filterset_fields = ('named_storm__id', 'snapshot_extracted')

    @action(methods=['get'], detail=False, url_path='per-storm')
    def per_storm(self, request):
        # return the most recent/distinct NSEM records per storm
        return Response(NsemPsaSerializer(
            self.queryset.filter(snapshot_extracted=True, validated=True).order_by('named_storm', '-date_returned').distinct('named_storm'),
            many=True, context=self.get_serializer_context()).data)

    def perform_create(self, serializer):
        # save the instance first so we can create a task to archive the covered data snapshot
        obj = serializer.save()

        chain(
            # create a covered data snapshot in object storage for the nsem users to download directly
            archive_nsem_covered_data_task.si(obj.id),
            # send an email to the "nsem" user when the archival is complete
            email_psa_covered_data_complete_task.s(),
            # download and extract archives into file storage so they're available for discovery (i.e opendap)
            extract_nsem_covered_data_task.s(),
        )()

    def perform_update(self, serializer):
        # save the instance first so we can create a task to extract and validate the model output snapshot
        nsem_psa = serializer.save()

        chain(
            # extract the psa
            extract_nsem_psa_task.s(nsem_psa.id),
            # validate once extracted
            validate_nsem_psa_task.si(nsem_psa.id),
            # email validation result
            email_psa_validated_task.si(nsem_psa.id),
        )()


class NsemPsaBaseViewSet(viewsets.ReadOnlyModelViewSet):
    # Named Storm Event Model PSA BASE ViewSet
    #   - expects to be nested under a NamedStormViewSet detail
    storm: NamedStorm = None
    nsem: NsemPsa = None

    def dispatch(self, request, *args, **kwargs):
        storm_id = kwargs.pop('storm_id')

        # get the storm instance
        storm = NamedStorm.objects.filter(id=storm_id)

        # get the storm's most recent & valid nsem
        nsem = NsemPsa.get_last_valid_psa(storm_id=storm_id)

        # validate
        if not storm.exists() or not nsem.exists():
            # returning responses via dispatch isn't part of the drf workflow so manually returning JsonResponse instead
            return JsonResponse(
                status=exceptions.NotFound.status_code,
                data={'detail': exceptions.NotFound.default_detail},
            )

        self.nsem = nsem.first()
        self.storm = storm.first()

        return super().dispatch(request, *args, **kwargs)


class NsemPsaVariableViewSet(NsemPsaBaseViewSet):
    # Named Storm Event Model PSA Variable ViewSet
    #   - expects to be nested under a NamedStormViewSet detail
    serializer_class = NsemPsaVariableSerializer
    filterset_fields = ('name', 'geo_type', 'data_type',)

    def get_queryset(self):
        return self.nsem.nsempsavariable_set.all() if self.nsem else NsemPsaVariable.objects.none()


class NsemPsaTimeSeriesViewSet(NsemPsaBaseViewSet):
    queryset = NsemPsaData.objects.all()  # defined in list()
    pagination_class = None

    def _as_csv(self, results, lat, lon):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="{}-time-series.csv"'.format(self.nsem.named_storm)

        writer = csv.writer(response)
        writer.writerow(['date', 'lat', 'lon', 'name', 'units', 'value'])
        for result in results:
            for i, value in enumerate(result['values']):
                writer.writerow([
                    self.nsem.dates[i],
                    lat,
                    lon,
                    result['variable']['name'],
                    result['variable']['units'],
                    value,
                ])

        return response

    def list(self, request, *args, lat=None, lon=None, **kwargs):

        # validate supplied coordinates
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            raise exceptions.NotFound('lat & lon should be floats')

        point = geos.Point(x=lon, y=lat)

        # find contour data covering bounding boxes
        bbox_query = NsemPsaData.objects.filter(
            nsem_psa_variable__nsem=self.nsem,
            bbox__covers=point,
            nsem_psa_variable__data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            nsem_psa_variable__geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
        ).only('id')

        fields_order = ('nsem_psa_variable__name', 'date')
        fields_values = ('nsem_psa_variable__name', 'value', 'date')

        # find contours covering point from the bbox results
        time_series_query = NsemPsaData.objects.filter(
            id__in=bbox_query,
            geo__covers=point,
            nsem_psa_variable__nsem=self.nsem,
        ).order_by(*fields_order).only(*fields_values).values(*fields_values)

        results = []

        # time-series variables
        variables = self.nsem.nsempsavariable_set.filter(data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES, geo_type=NsemPsaVariable.GEO_TYPE_POLYGON)

        # include data grouped by variable
        for variable in variables:
            result = {
                'variable': NsemPsaVariableSerializer(variable).data,
                'values': [],
            }
            for date in self.nsem.dates:
                # find matching record if it exists
                value = next((v['value'] for v in time_series_query if v['nsem_psa_variable__name'] == variable.name and v['date'] == date), 0)
                result['values'].append(value)
            results.append(result)

        if request.query_params.get('export') == 'csv':
            return self._as_csv(results, lat, lon)

        return Response(results)


@method_decorator(gzip_page, name='dispatch')
@method_decorator(cache_control(max_age=3600), name='dispatch')
class NsemPsaGeoViewSet(NsemPsaBaseViewSet):
    # Named Storm Event Model PSA Geo ViewSet
    #   - expects to be nested under a NamedStormViewSet detail
    #   - returns geojson results

    filterset_class = NsemPsaDataFilter
    pagination_class = None
    CACHE_TIMEOUT = 60 * 60 * 24 * settings.CWWED_CACHE_PSA_GEOJSON_DAYS

    def get_queryset(self):
        """
        group all geometries together by same variable & value which reduces total features
        """
        qs = NsemPsaData.objects.filter(nsem_psa_variable__nsem=self.nsem)
        qs = qs.values(*['value', 'meta', 'color', 'date', 'nsem_psa_variable__name', 'nsem_psa_variable__units'])
        qs = qs.annotate(geom=Collect(Cast('geo', GeometryField())))
        qs = qs.order_by('nsem_psa_variable__name')
        return qs

    def list(self, request, *args, **kwargs):

        # return an empty list if no variable filter is supplied because we can benefit from the DRF filter being presented in the API view
        if 'nsem_psa_variable' not in request.query_params:
            return Response([])

        # return cached data if it exists
        cache = caches['psa_geojson']  # type: BaseCache
        cache_key = get_cache_key(request, key_prefix=settings.CACHE_MIDDLEWARE_KEY_PREFIX, method='GET', cache=cache)
        cached_response = cache.get(cache_key)
        if cached_response:
            logging.info('returning cached response for {}'.format(cache_key))
            return HttpResponse(cached_response, content_type='application/json')

        self._validate()

        queryset = self.filter_queryset(self.get_queryset())
        geojson = get_geojson_feature_collection_from_psa_qs(queryset)
        response = HttpResponse(geojson, content_type='application/json')

        # cache result
        cache_key = learn_cache_key(
            request, response, cache_timeout=self.CACHE_TIMEOUT, key_prefix=settings.CACHE_MIDDLEWARE_KEY_PREFIX, cache=cache)
        cache.set(cache_key, geojson, self.CACHE_TIMEOUT)

        return response

    def _validate(self):

        # verify the requested variable exists
        nsem_psa_variable_query = self.nsem.nsempsavariable_set.filter(id=self.request.query_params['nsem_psa_variable'])
        if not nsem_psa_variable_query.exists():
            raise exceptions.ValidationError('No data exists for variable "{}"'.format(self.request.query_params['variable']))

        # verify if the variable requires a date filter
        if nsem_psa_variable_query[0].data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES and not self.request.query_params.get('date'):
            raise exceptions.ValidationError({'date': ['required for this type of variable']})


class NsemPsaUserExportViewSet(UserReferenceViewSetMixin, viewsets.ModelViewSet):
    serializer_class = NsemPsaUserExportSerializer
    queryset = NsemPsaUserExport.objects.all()

    def get_queryset(self):
        # only include objects the requesting user owns
        if self.request.user.is_authenticated:
            return NsemPsaUserExport.objects.filter(user=self.request.user)
        else:
            return NsemPsaUserExport.objects.none()

    def perform_create(self, serializer):
        super().perform_create(serializer)

        # create tasks to build the export and email the user when complete
        chain(
            create_psa_user_export_task.s(nsem_psa_user_export_id=serializer.instance.id),
            email_psa_user_export_task.si(nsem_psa_user_export_id=serializer.instance.id),
        ).apply_async()


class NsemPsaUserExportNestedViewSet(NsemPsaBaseViewSet, NsemPsaUserExportViewSet):
    # Named Storm Event Model PSA User Export
    #   - expects to be nested under a NamedStormViewSet detail

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['nsem'] = self.nsem
        return context
