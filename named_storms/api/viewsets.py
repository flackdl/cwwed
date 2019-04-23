from datetime import datetime
from django.core.serializers import serialize
from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework import exceptions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.response import Response

from named_storms.api.filters import NsemPsaFilter
from named_storms.tasks import (
    archive_nsem_covered_data_task, extract_nsem_model_output_task, email_nsem_covered_data_complete_task,
    extract_nsem_covered_data_task,
)
from named_storms.models import NamedStorm, CoveredData, NSEM, NsemPsaVariable, NsemPsaData
from named_storms.api.serializers import NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NSEMSerializer


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


class NsemPsaViewset(viewsets.ReadOnlyModelViewSet):
    # Named Storm Event Model Viewset
    #     - expects to be nested under a NamedStormViewset detail
    #     - returns geojson results

    filterset_class = NsemPsaFilter

    storm: NamedStorm = None
    nsem: NSEM = None
    nsem_psa_variable: NsemPsaVariable = None
    date: datetime = None

    def dispatch(self, request, *args, **kwargs):
        self.storm = NamedStorm.objects.get(id=kwargs.pop('storm_id'))
        self.date = parse_datetime(kwargs.pop('date'))

        nsem = self.storm.nsem_set.filter(model_output_snapshot_extracted=True).order_by('-date_returned')
        if nsem.exists():
            self.nsem = nsem[0]

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.nsem_psa_variable.nsempsadata_set.all() if self.nsem_psa_variable else NsemPsaData.objects.none()

    def list(self, request, *args, **kwargs):

        self._validate()

        return HttpResponse(
            content=serialize(
                'geojson',
                self.filter_queryset(self.get_queryset()),
                geometry_field='geo',
                fields=('value', 'color', 'date'),),
            content_type='application/json',
        )

    def _validate(self):
        nsem_psa_variable = self.nsem.nsempsavariable_set.filter(name=self.request.query_params['variable'])
        if nsem_psa_variable.exists():
            self.nsem_psa_variable = nsem_psa_variable[0]

        if not self.nsem:
            raise exceptions.ValidationError('No post storm assessments exist for this storm')
        if not self.nsem_psa_variable:
            raise ValidationError('No data exists for variable "{}" and date "{}"'.format(self.request.query_params['variable'], self.date.isoformat()))
        if not self.date:
            raise ValidationError({'date': ['date parameter must be valid']})
        if 'variable' not in self.request.query_params:
            raise ValidationError({'variable': ['variable parameter must be supplied']})
