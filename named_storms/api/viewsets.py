import csv
import logging

import geojson
from celery import chain, group, chord
from django.contrib.gis.db.models.functions import Distance
from django.db.models.functions import Cast
from django.http import JsonResponse, HttpResponse
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.gis import geos
from django.views.decorators.gzip import gzip_page
from django.views.decorators.cache import cache_control, cache_page
from django.contrib.gis.db.models import Collect, GeometryField
from rest_framework import viewsets, mixins
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from named_storms.api.filters import NsemPsaContourFilter, NsemPsaDataFilter
from named_storms.api.mixins import UserReferenceViewSetMixin
from named_storms.sql import wind_barbs_query
from named_storms.tasks import (
    create_named_storm_covered_data_snapshot_task, extract_nsem_psa_task, email_nsem_user_covered_data_complete_task,
    extract_named_storm_covered_data_snapshot_task, create_psa_user_export_task,
    email_psa_user_export_task, validate_nsem_psa_task,
    postprocess_psa_ingest_task, cache_psa_contour_task,
    ingest_nsem_psa_dataset_variable_task, postprocess_psa_validated_task,
)
from named_storms.models import (
    NamedStorm, CoveredData, NsemPsa, NsemPsaVariable, NsemPsaContour, NsemPsaUserExport, NamedStormCoveredDataSnapshot,
    NsemPsaData, NsemPsaManifestDataset,
)
from named_storms.api.serializers import (
    NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NsemPsaSerializer, NsemPsaVariableSerializer, NsemPsaUserExportSerializer,
    NamedStormCoveredDataSnapshotSerializer, NsemPsaDataSerializer, NsemPsaTimeSeriesSerializer, NsemPsaManifestDatasetSerializer, NsemPsaWindBarbsSerializer,
    NsemPsaContourSerializer)
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
        qs = self.filter_queryset(self.queryset).filter(extracted=True, validated=True, processed=True)
        # order by named_storm_id vs named_storm to prevent table join which django has issues with using distinct on
        qs = qs.order_by('named_storm_id', '-date_created')
        qs = qs.distinct('named_storm_id')
        return Response(NsemPsaSerializer(qs, many=True, context=self.get_serializer_context()).data)

    @classmethod
    def get_ingest_psa_dataset_tasks(cls, nsem_psa_id):
        """
        Creates tasks to ingest an NSEM PSA into CWWED
        """

        nsem_psa = NsemPsa.objects.get(id=nsem_psa_id)
        tasks = []
        # create tasks to process each variable for each date in each dataset
        for dataset in nsem_psa.nsempsamanifestdataset_set.all():  # type: NsemPsaManifestDataset
            for variable in dataset.variables:
                # max-values data type so there's no date
                if NsemPsaVariable.get_variable_attribute(variable, 'data_type') == NsemPsaVariable.DATA_TYPE_MAX_VALUES:
                    tasks.append(ingest_nsem_psa_dataset_variable_task.si(dataset.id, variable))
                else:
                    for date in sorted(nsem_psa.dates):
                        tasks.append(ingest_nsem_psa_dataset_variable_task.si(dataset.id, variable, date))
        return tasks

    def perform_create(self, serializer):
        # save the instance first so we can create a task to extract and validate the model output
        nsem_psa = serializer.save()  # type: NsemPsa

        chain(
            # extract the psa
            extract_nsem_psa_task.s(nsem_psa.id),
            # validate once extracted
            validate_nsem_psa_task.si(nsem_psa.id),
            # post-process the validation and email validation result
            postprocess_psa_validated_task.si(nsem_psa.id),
            # ingest the psa in parallel by creating tasks for each dataset/variable/date
            chord(
                header=self.get_ingest_psa_dataset_tasks(nsem_psa.id),
                # then run the following sequentially
                body=chain(
                    # save psa as processed and send confirmation email
                    postprocess_psa_ingest_task.si(nsem_psa.id, True),  # success
                    # execute these final tasks in parallel
                    group(
                        # cache geo json for this psa
                        cache_psa_contour_task.si(nsem_psa.named_storm_id),
                        # download and extract covered data snapshot into file storage so they're available for discovery (i.e opendap)
                        extract_named_storm_covered_data_snapshot_task.si(nsem_psa.id),
                    ),
                )
            ).on_error(postprocess_psa_ingest_task.si(nsem_psa.id, False))  # header failure (ingestion failed)
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
    """
    #### PSA Time Series
    """
    queryset = NsemPsaData.objects.all()  # defined in list()
    pagination_class = None
    serializer_class = NsemPsaTimeSeriesSerializer

    POINT_DISTANCE = 500  # meters

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
                    result['variable'].name,
                    result['variable'].units,
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
                'variable': variable,
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

        return Response(self.serializer_class(results, many=True).data)


class NsemPsaWindBarbsViewSet(NsemPsaBaseViewSet):
    """
    #### Named Storm PSA Wind Barbs
    """
    # Named Storm Event Model PSA Wind Barbs ViewSet
    # - expects to be nested under a NamedStormViewSet detail
    # - returns geojson results
    queryset = NsemPsaData.objects.all()  # defined in list()

    def get_serializer_class(self):
        # dummy serializer class
        return NsemPsaWindBarbsSerializer

    def list(self, request, *args, date=None, **kwargs):

        date = parse_datetime(date or '')
        if not date:
            raise exceptions.ValidationError({'date': ['date is required (format: 2018-09-14T01:00:00Z)']})

        try:
            step = int(request.query_params.get('step') or 1)
        except ValueError:
            raise exceptions.ValidationError({'step': ['step must be an integer']})

        try:
            center = geos.fromstr(request.query_params.get('center'))
        except Exception:
            logger.warning('Invalid center {}'.format(request.query_params.get('center')))
            raise exceptions.ValidationError({'center': ['center point must be WKT']})

        results = wind_barbs_query(self.nsem.id, date=date, center=center, step=step)

        # build geojson features
        features = []
        for result in results:
            point = geos.fromstr(result[0])  # type: geos.Point
            features.append(
                geojson.Feature(
                    geometry=geojson.Point((point.x, point.y)),
                    properties={
                        'name': 'wind_direction',
                        'wind_direction_value': result[1],
                        'wind_direction_units': NsemPsaVariable.get_variable_attribute(NsemPsaVariable.VARIABLE_DATASET_WIND_DIRECTION, 'units'),
                        'wind_speed_value': result[2],
                        'wind_speed_units': NsemPsaVariable.get_variable_attribute(NsemPsaVariable.VARIABLE_DATASET_WIND_SPEED, 'units'),
                    },
                )
            )

        return Response(geojson.FeatureCollection(features=features))


@method_decorator(gzip_page, name='dispatch')
@method_decorator(cache_control(public=True, max_age=3600), name='dispatch')
@method_decorator(cache_page(settings.CWWED_CACHE_PSA_CONTOURS_SECONDS, cache="psa_contours"), name='dispatch')
class NsemPsaContourViewSet(NsemPsaBaseViewSet):
    """
    #### Named Storm PSA Contour

    **required params:**

    - `nsem_psa_variable`
    - `date`
    """
    # Named Storm Event Model PSA Geo ViewSet
    #   - expects to be nested under a NamedStormViewSet detail
    #   - returns geojson results

    queryset = NsemPsaContour.objects.all()
    filterset_class = NsemPsaContourFilter
    pagination_class = None

    def get_serializer_class(self):
        # dummy serializer class
        return NsemPsaContourSerializer

    def get_queryset(self):
        """
        - group all geometries together (st_collect) by same variable & value
        """
        qs = NsemPsaContour.objects.filter(nsem_psa_variable__nsem=self.nsem)
        qs = qs.values(*[
            'value', 'color', 'date', 'nsem_psa_variable__name', 'nsem_psa_variable__data_type',
            'nsem_psa_variable__display_name', 'nsem_psa_variable__units',
        ])
        qs = qs.annotate(geom=Collect(Cast('geo', GeometryField())))
        qs = qs.order_by('nsem_psa_variable__name')
        return qs

    def list(self, request, *args, **kwargs):

        # return an empty list if no variable filter is supplied because the query is
        # too expensive and we can benefit from the DRF filter being presented in the API view
        if 'nsem_psa_variable' not in request.query_params:
            return Response([])

        self._validate()

        queryset = self.filter_queryset(self.get_queryset())

        # get geo json from queryset
        geo_json = get_geojson_feature_collection_from_psa_qs(queryset)

        return HttpResponse(geo_json, content_type='application/json')

    def _validate(self):

        # verify the requested variable exists
        nsem_psa_variable_query = self.nsem.nsempsavariable_set.filter(name=self.request.query_params['nsem_psa_variable'])
        if not nsem_psa_variable_query.exists():
            raise exceptions.ValidationError('No data exists for variable "{}"'.format(self.request.query_params['nsem_psa_variable']))

        # verify if the variable requires a date filter
        if nsem_psa_variable_query[0].data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES and not self.request.query_params.get('date'):
            raise exceptions.ValidationError({'date': ['required for this type of variable']})


@method_decorator(gzip_page, name='dispatch')
class NsemPsaDataViewSet(NsemPsaBaseViewSet):
    """
    #### Named Storm PSA Data

    **required params:**

    - `nsem_psa_variable`
    """
    # Named Storm Event Model PSA Data ViewSet
    #   - expects to be nested under a NamedStormViewSet detail

    filterset_class = NsemPsaDataFilter
    serializer_class = NsemPsaDataSerializer

    def get_queryset(self):
        # filter by nested nsem
        return NsemPsaData.objects.filter(nsem_psa_variable__nsem=self.nsem)

    def list(self, request, *args, **kwargs):
        # return an empty list if no variable filter is supplied because
        # the query is too expensive and we can benefit from the DRF filter being presented in the API view
        if 'nsem_psa_variable' not in request.query_params:
            return Response([])
        return super().list(request, *args, **kwargs)


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


class NsemPsaManifestDatasetViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NsemPsaManifestDatasetSerializer
    queryset = NsemPsaManifestDataset.objects.all()
    filterset_fields = ('nsem', 'nsem__named_storm')
