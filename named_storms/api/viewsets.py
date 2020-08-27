import csv
import logging
from celery import chain, group
from django.contrib.gis.db.models.functions import Intersection, Distance, GeoHash
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
from rest_framework import viewsets, mixins
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from named_storms.api.filters import NsemPsaContourFilter
from named_storms.api.mixins import UserReferenceViewSetMixin
from named_storms.tasks import (
    create_named_storm_covered_data_snapshot_task, extract_nsem_psa_task, email_nsem_user_covered_data_complete_task,
    extract_named_storm_covered_data_snapshot_task, create_psa_user_export_task,
    email_psa_user_export_task, validate_nsem_psa_task, email_psa_validated_task, ingest_nsem_psa_task,
    email_psa_ingested_task, cache_psa_geojson_task,
)
from named_storms.models import NamedStorm, CoveredData, NsemPsa, NsemPsaVariable, NsemPsaContour, NsemPsaUserExport, NamedStormCoveredDataSnapshot, NsemPsaData
from named_storms.api.serializers import (
    NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NsemPsaSerializer, NsemPsaVariableSerializer, NsemPsaUserExportSerializer,
    NamedStormCoveredDataSnapshotSerializer)
from named_storms.utils import get_geojson_feature_collection_from_psa_qs

logger = logging.getLogger('cwwed')


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Named Storms
    """
    queryset = NamedStorm.objects.all()
    serializer_class = NamedStormSerializer
    filterset_fields = ('name',)
    search_fields = ('name',)

    def get_serializer_class(self):
        # return a more detailed representation for a specific storm
        if self.action == 'retrieve':
            return NamedStormDetailSerializer
        return super().get_serializer_class()


class CoveredDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoveredData.objects.all()
    serializer_class = CoveredDataSerializer


class NamedStormCoveredDataSnapshotViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    """
    Named Storm Covered Data Snapshot ViewSet
    """
    queryset = NamedStormCoveredDataSnapshot.objects.all()
    serializer_class = NamedStormCoveredDataSnapshotSerializer
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    filterset_fields = ('named_storm',)

    def perform_create(self, serializer):
        # save the instance first so we can create a task to archive the covered data snapshot
        obj = serializer.save()  # type: NamedStormCoveredDataSnapshot

        chain(
            # create a covered data snapshot in object storage for the nsem users to be able to download directly
            create_named_storm_covered_data_snapshot_task.si(obj.id),
            # send an email to the "nsem" user when the covered data snapshot archival is complete
            email_nsem_user_covered_data_complete_task.si(obj.id),
        )()


class NsemPsaViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, GenericViewSet):
    """
    Named Storm Event Model ViewSet
    """
    queryset = NsemPsa.objects.all()
    serializer_class = NsemPsaSerializer
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    filterset_fields = ('named_storm', 'extracted', 'validated', 'processed')

    @action(methods=['get'], detail=False, url_path='per-storm')
    def per_storm(self, request):
        # return the most recent/distinct NSEM records per storm
        qs = self.queryset.filter(extracted=True, validated=True, processed=True)
        # NOTE: order by `named_storm_id` vs `named_storm` to prevent table join which django has issues with using distinct on
        qs = qs.order_by('named_storm_id', '-date_created')
        qs = qs.distinct('named_storm_id')
        return Response(NsemPsaSerializer(qs, many=True, context=self.get_serializer_context()).data)

    def perform_create(self, serializer):
        # save the instance first so we can create a task to extract and validate the model output
        nsem_psa = serializer.save()  # type: NsemPsa

        chain(
            # extract the psa
            extract_nsem_psa_task.s(nsem_psa.id),
            # validate once extracted
            validate_nsem_psa_task.si(nsem_psa.id),
            # email validation result
            email_psa_validated_task.si(nsem_psa.id),
            # ingest the psa
            ingest_nsem_psa_task.si(nsem_psa.id),
            # email psa ingest completion
            email_psa_ingested_task.si(nsem_psa.id),
            # execute these final tasks in parallel
            group(
                # cache geo json for this psa
                cache_psa_geojson_task.si(nsem_psa.named_storm_id),
                # download and extract covered data snapshot into file storage so they're available for discovery (i.e opendap)
                extract_named_storm_covered_data_snapshot_task.si(nsem_psa.id),
            ),
        ).apply_async()


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
        self.nsem = NsemPsa.get_last_valid_psa(storm_id=storm_id)

        # validate
        if not storm.exists() or not self.nsem:
            # returning responses via dispatch isn't part of the drf workflow so manually returning JsonResponse instead
            return JsonResponse(
                status=exceptions.NotFound.status_code,
                data={'detail': exceptions.NotFound.default_detail},
            )

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
    queryset = NsemPsaContour.objects.all()  # defined in list()
    pagination_class = None
    POINT_DISTANCE = 500

    def get_serializer_class(self):
        # required placeholder because this class isn't using a serializer
        from rest_framework.serializers import BaseSerializer
        return BaseSerializer

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
            raise exceptions.ValidationError('lat & lon should be floats')

        point = geos.Point(x=lon, y=lat, srid=4326)

        fields_order = ['nsem_psa_variable__name', 'date']
        fields_values = ('nsem_psa_variable__name', 'value', 'date')

        # time-series data nearest supplied point per variable/date
        time_series_query = NsemPsaData.objects.annotate(
            distance=Distance('point', point),
        ).distinct(
            *fields_order
        ).filter(
            point__dwithin=(point, self.POINT_DISTANCE),
            nsem_psa_variable__nsem=self.nsem,
        ).order_by(
            # sort by ascending distance to get the first result in each group (i.e the nearest to supplied point)
            *fields_order + ['distance']
        ).only(
            *fields_values
        ).values(
            *fields_values
        )

        results = []

        # time-series variables
        variables = self.nsem.nsempsavariable_set.filter(
            data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
            geo_type=NsemPsaVariable.GEO_TYPE_POLYGON,
        )

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

        # csv export
        if request.query_params.get('export') == 'csv':
            return self._as_csv(results, lat, lon)

        return Response(results)


@method_decorator(gzip_page, name='dispatch')
@method_decorator(cache_control(
    public=True,
    max_age=3600,
), name='dispatch')
class NsemPsaGeoViewSet(NsemPsaBaseViewSet):
    # Named Storm Event Model PSA Geo ViewSet
    #   - expects to be nested under a NamedStormViewSet detail
    #   - returns geojson results

    filterset_class = NsemPsaContourFilter
    pagination_class = None
    CACHE_TIMEOUT = 60 * 60 * 24 * settings.CWWED_CACHE_PSA_GEOJSON_DAYS

    def get_serializer_class(self):
        # required placeholder because this class isn't using a serializer
        from rest_framework.serializers import BaseSerializer
        return BaseSerializer

    def get_queryset(self):
        """
        - group all geometries together (st_collect) by same variable & value
        - clip psa to storm's geo (st_intersection)
        """
        qs = NsemPsaContour.objects.filter(nsem_psa_variable__nsem=self.nsem)
        qs = qs.values(*[
            'value', 'meta', 'color', 'date', 'nsem_psa_variable__name',
            'nsem_psa_variable__display_name', 'nsem_psa_variable__units',
        ])
        qs = qs.annotate(geom=Intersection(Collect(Cast('geo', GeometryField())), self.storm.geo))
        qs = qs.order_by('nsem_psa_variable__name')
        return qs

    def list(self, request, *args, **kwargs):

        # return an empty list if no variable filter is supplied because
        # we can benefit from the DRF filter being presented in the API view
        if 'nsem_psa_variable' not in request.query_params:
            return Response([])

        # return cached data if it exists
        cache = caches['psa_geojson']  # type: BaseCache
        cache_key = get_cache_key(request, method='GET', cache=cache)
        if cache_key:
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.info('returning cached response for {}'.format(request.query_params))
                return HttpResponse(cached_response, content_type='application/json')
            else:
                logger.warning('No data for cache key {}'.format(cache_key))
        else:
            logger.warning('Missing cache key for {}'.format(request.query_params))

        self._validate()

        queryset = self.filter_queryset(self.get_queryset())
        geojson = get_geojson_feature_collection_from_psa_qs(queryset)
        response = HttpResponse(geojson, content_type='application/json')

        # cache result
        cache_key = learn_cache_key(
            request, response, cache_timeout=self.CACHE_TIMEOUT, cache=cache)
        cache.set(cache_key, geojson, self.CACHE_TIMEOUT)

        return response

    def _validate(self):

        # verify the requested variable exists
        nsem_psa_variable_query = self.nsem.nsempsavariable_set.filter(id=self.request.query_params['nsem_psa_variable'])
        if not nsem_psa_variable_query.exists():
            raise exceptions.ValidationError('No data exists for variable "{}"'.format(self.request.query_params['nsem_psa_variable']))

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

    def create(self, request, *args, **kwargs):
        # manually add the requesting user to the data
        request.data['user'] = request.user.id
        return super().create(request, *args, **kwargs)

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
