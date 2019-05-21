import json
from django.db.models.functions import Cast
from django.http import JsonResponse
from django.utils.decorators import method_decorator
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
from named_storms.tasks import (
    archive_nsem_covered_data_task, extract_nsem_model_output_task, email_nsem_covered_data_complete_task,
    extract_nsem_covered_data_task,
)
from named_storms.models import NamedStorm, CoveredData, NSEM, NsemPsaVariable, NsemPsaData
from named_storms.api.serializers import NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NSEMSerializer, NsemPsaVariableSerializer, NsemPsaDataSerializer


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
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


class NSEMViewset(viewsets.ModelViewSet):
    """
    Named Storm Event Model Viewset
    """
    queryset = NSEM.objects.all()
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
    #     - expects to be nested under a NamedStormViewset detail
    storm: NamedStorm = None
    nsem: NSEM = None

    def dispatch(self, request, *args, **kwargs):
        # define the storm
        self.storm = NamedStorm.objects.get(id=kwargs.pop('storm_id'))

        # get most recent, valid, nsem
        nsem = self.storm.nsem_set.filter(model_output_snapshot_extracted=True).order_by('-date_returned')
        if nsem.exists():
            self.nsem = nsem[0]

        return super().dispatch(request, *args, **kwargs)


class NsemPsaVariableViewset(NsemPsaBaseViewset):
    # Named Storm Event Model PSA Variable Viewset
    #     - expects to be nested under a NamedStormViewset detail
    serializer_class = NsemPsaVariableSerializer
    filterset_fields = ('name',)

    def get_queryset(self):
        return self.nsem.nsempsavariable_set.all() if self.nsem else NsemPsaVariable.objects.none()


class NsemPsaDataViewset(NsemPsaBaseViewset):
    # Named Storm Event Model PSA Data Viewset
    #     - expects to be nested under a NamedStormViewset detail
    serializer_class = NsemPsaDataSerializer
    filterset_class = NsemPsaDataFilter

    def get_queryset(self):
        if not self.nsem:
            return NsemPsaData.objects.none()
        return NsemPsaData.objects.filter(nsem_psa_variable__nsem=self.nsem)

    def list(self, request, *args, **kwargs):
        if 'date' not in self.request.query_params:
            raise exceptions.ValidationError({'date': ['missing value']})
        return super().list(request, *args, **kwargs)

    def dates(self, request, *args, **kwargs):
        return Response(self.nsem.dates)

    def time_series(self, request, *args, **kwargs):
        # validate supplied coordinate
        coordinate = request.query_params.getlist('coordinate')
        if not coordinate or not len(coordinate) == 2:
            raise exceptions.NotFound('Coordinate (2) not supplied')
        try:
            coordinate = tuple(map(float, coordinate))
        except ValueError:
            raise exceptions.NotFound('Coordinate should be floats')

        point = geos.Point(x=coordinate[0], y=coordinate[1])

        # find data covering bounding boxes
        bbox_query = NsemPsaData.objects.annotate().filter(
            nsem_psa_variable__nsem=self.nsem,
            bbox__covers=point,
            nsem_psa_variable__data_type=NsemPsaVariable.DATA_TYPE_TIME_SERIES,
        )

        bbox_data = bbox_query.only('id').values('id')

        # find data covering point from the bbox results
        time_series_query = NsemPsaData.objects.filter(
            id__in=[bbox['id'] for bbox in bbox_data],
            geo__covers=point,
        )

        time_series_query = time_series_query.order_by('nsem_psa_variable__name', 'date')
        time_series_query = time_series_query.only('nsem_psa_variable__name', 'value', 'date')
        time_series = time_series_query.values('nsem_psa_variable__name', 'value', 'date')

        result = {
            'dates': self.nsem.dates,
        }

        # list of all variables
        variables = set(map(lambda x: x['nsem_psa_variable__name'], time_series))

        # include data grouped by variable
        for variable in variables:
            result[variable] = []
            for date in self.nsem.dates:
                # find matching record if it exists
                value = next((v['value'] for v in time_series if v['nsem_psa_variable__name'] == variable and v['date'] == date), 0)
                result[variable].append(value)

        return Response(result)


class NsemPsaGeoViewset(NsemPsaBaseViewset):
    # Named Storm Event Model PSA Geo Viewset
    #     - expects to be nested under a NamedStormViewset detail
    #     - returns geojson results

    filterset_class = NsemPsaDataFilter

    nsem_psa_variable: NsemPsaVariable = None

    @method_decorator(gzip_page)
    @method_decorator(cache_control(max_age=3600))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.nsem_psa_variable.nsempsadata_set.all() if self.nsem_psa_variable else NsemPsaData.objects.none()

    def list(self, request, *args, **kwargs):
        """
        return geojson results by grouping all geometries together by same value which reduces total features
        """

        self._validate()

        features = []

        fields = ['value', 'color', 'date', 'nsem_psa_variable__name', 'nsem_psa_variable__units']
        for data in self.filter_queryset(self.get_queryset().values(*fields).annotate(geom=Collect(Cast('geo', GeometryField())))):
            features.append({
                "type": "Feature",
                "properties": {
                    "name": data['nsem_psa_variable__name'],
                    "unit": data['nsem_psa_variable__units'],
                    "value": data['value'],
                    "date": data['date'].isoformat() if data['date'] else None,
                    "color": data['color'],
                },
                "geometry": json.loads(data['geom'].json),
            })

        return JsonResponse({"type": "FeatureCollection", "features": features})

    def _validate(self):

        if not self.nsem:
            raise exceptions.ValidationError('No post storm assessments exist for this storm')

        if 'variable' not in self.request.query_params:
            raise exceptions.ValidationError({'variable': ['missing value']})

        nsem_psa_variable = self.nsem.nsempsavariable_set.filter(name=self.request.query_params['variable'])
        if not nsem_psa_variable.exists():
            raise exceptions.ValidationError('No data exists for variable "{}"'.format(self.request.query_params['variable']))
        self.nsem_psa_variable = nsem_psa_variable[0]

        if self.nsem_psa_variable.data_type == NsemPsaVariable.DATA_TYPE_TIME_SERIES and 'date' not in self.request.query_params:
            raise exceptions.ValidationError({'date': ['missing value']})
