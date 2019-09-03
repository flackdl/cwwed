import csv
import json
import pytz
from celery import chain
from django.db.models.functions import Cast
from django.http import JsonResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.contrib.gis import geos
from django.views.decorators.gzip import gzip_page
from django.views.decorators.cache import cache_control, cache_page
from django.contrib.gis.db.models import Collect, GeometryField
from rest_framework import viewsets
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response

from named_storms.api.filters import NsemPsaDataFilter
from named_storms.api.mixins import UserReferenceViewSetMixin
from named_storms.tasks import (
    archive_nsem_covered_data_task, extract_nsem_model_output_task, email_nsem_covered_data_complete_task,
    extract_nsem_covered_data_task, create_psa_user_export_task,
    email_psa_user_export_task)
from named_storms.models import NamedStorm, CoveredData, NsemPsa, NsemPsaVariable, NsemPsaData, NsemPsaUserExport
from named_storms.api.serializers import (
    NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NSEMSerializer, NsemPsaVariableSerializer, NsemPsaUserExportSerializer,
)


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


class NSEMViewset(viewsets.ModelViewSet):
    """
    Named Storm Event Model Viewset
    """
    queryset = NsemPsa.objects.all()
    serializer_class = NSEMSerializer
    permission_classes = (DjangoModelPermissionsOrAnonReadOnly,)
    filterset_fields = ('named_storm__id', 'model_output_snapshot_extracted')

    @action(methods=['get'], detail=False, url_path='per-storm')
    def per_storm(self, request):
        # return the most recent/distinct NSEM records per storm
        return Response(NSEMSerializer(
            self.queryset.filter(model_output_snapshot_extracted=True).order_by('named_storm', '-date_returned').distinct('named_storm'),
            many=True, context=self.get_serializer_context()).data)

    def perform_create(self, serializer):
        # save the instance first so we can create a task to archive the covered data snapshot
        obj = serializer.save()

        # base url for email
        base_url = '{}://{}'.format(
            self.request.scheme,
            self.request.get_host(),
        )

        # create an archive in object storage for the nsem users to download directly
        archive_nsem_covered_data_task.apply_async(
            (obj.id,),
            link=[
                # send an email to the "nsem" user when the archival is complete
                email_nsem_covered_data_complete_task.s(base_url),
                # download and extract archives into file storage so they're available for discovery (i.e opendap)
                extract_nsem_covered_data_task.s()
            ],
        )

    def perform_update(self, serializer):
        # save the instance first so we can create a task to extract the model output snapshot
        obj = serializer.save()
        extract_nsem_model_output_task.delay(obj.id)


class NsemPsaBaseViewset(viewsets.ReadOnlyModelViewSet):
    # Named Storm Event Model PSA BASE Viewset
    #   - expects to be nested under a NamedStormViewset detail
    storm: NamedStorm = None
    nsem: NsemPsa = None

    def dispatch(self, request, *args, **kwargs):
        storm_id = kwargs.pop('storm_id')

        # get the storm instance
        storm = NamedStorm.objects.filter(id=storm_id)

        # get the storm's most recent & valid nsem
        nsem = NsemPsa.objects.filter(named_storm__id=storm_id, model_output_snapshot_extracted=True).order_by('-date_returned')

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


class NsemPsaVariableViewset(NsemPsaBaseViewset):
    # Named Storm Event Model PSA Variable Viewset
    #   - expects to be nested under a NamedStormViewset detail
    serializer_class = NsemPsaVariableSerializer
    filterset_fields = ('name', 'geo_type', 'data_type',)

    def get_queryset(self):
        return self.nsem.nsempsavariable_set.all() if self.nsem else NsemPsaVariable.objects.none()


class NsemPsaDatesViewset(NsemPsaBaseViewset):
    queryset = NsemPsa.objects.none()  # required but unnecessary since we're returning a specific nsem's dates
    pagination_class = None

    def list(self, request, *args, **kwargs):
        return Response(self.nsem.dates)


class NsemPsaTimeSeriesViewset(NsemPsaBaseViewset):
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
                    # TODO - remove timezone localization once data is correctly consumed in UTC
                    pytz.timezone('US/Eastern').localize(self.nsem.dates[i].replace(tzinfo=None)),
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


class NsemPsaGeoViewset(NsemPsaBaseViewset):
    # Named Storm Event Model PSA Geo Viewset
    #   - expects to be nested under a NamedStormViewset detail
    #   - returns geojson results

    filterset_class = NsemPsaDataFilter
    pagination_class = None

    @method_decorator(gzip_page)
    @method_decorator(cache_control(max_age=3600))  # expire client-side
    @method_decorator(cache_page(timeout=60*60*24*7))  # expire server-side
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

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

        # invalid - no nsem exists
        if not self.nsem:
            raise exceptions.ValidationError('No post storm assessments exist for this storm')

        # return an empty list if no variable filter is supplied because we can benefit from the DRF filter being presented in the API view
        if 'nsem_psa_variable' not in request.query_params:
            return Response([])

        self._validate()

        queryset = self.filter_queryset(self.get_queryset())

        features = []

        for data in queryset:
            features.append({
                "type": "Feature",
                "properties": {
                    "name": data['nsem_psa_variable__name'],
                    "units": data['nsem_psa_variable__units'],
                    "value": data['value'],
                    "meta": data['meta'],
                    "date": data['date'].isoformat() if data['date'] else None,
                    "fill": data['color'],
                    "stroke": data['color'],
                },
                "geometry": json.loads(data['geom'].json),
            })

        return Response({"type": "FeatureCollection", "features": features})

    def _validate(self):

        # verify the requested variable exists
        nsem_psa_variable_query = self.nsem.nsempsavariable_set.filter(id=self.request.query_params['nsem_psa_variable'])
        if not nsem_psa_variable_query.exists():
            raise exceptions.ValidationError('No data exists for variable "{}"'.format(self.request.query_params['variable']))

        # verify if the variable requires a date filter
        if nsem_psa_variable_query[0].data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES and not self.request.query_params.get('date'):
            raise exceptions.ValidationError({'date': ['required for this type of variable']})


class NsemPsaUserExportViewset(UserReferenceViewSetMixin, viewsets.ModelViewSet):
    serializer_class = NsemPsaUserExportSerializer
    queryset = NsemPsaUserExport.objects.all()

    def get_queryset(self):
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


class NsemPsaUserExportNestedViewset(NsemPsaBaseViewset, NsemPsaUserExportViewset):
    # Named Storm Event Model PSA User Export
    #   - expects to be nested under a NamedStormViewset detail

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['nsem'] = self.nsem
        return context
