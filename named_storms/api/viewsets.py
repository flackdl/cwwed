from rest_framework import viewsets
from named_storms.tasks import archive_nsem_covered_data, extract_nsem_model_output, email_nsem_covered_data_complete_task
from named_storms.models import NamedStorm, CoveredData, NSEM
from named_storms.api.serializers import NamedStormSerializer, CoveredDataSerializer, NamedStormDetailSerializer, NSEMSerializer


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStorm.objects.all()
    serializer_class = NamedStormSerializer
    filter_fields = ('name',)
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

    def perform_create(self, serializer):
        # save the instance first so we can create a task to archive the covered data snapshot
        obj = serializer.save()

        base_url = '{}://{}'.format(
            self.request.scheme,
            self.request.get_host(),
        )

        archive_nsem_covered_data.apply_async(
            (obj.id,),
            # also send an email to the "nsem" user when the archival is complete
            link=email_nsem_covered_data_complete_task.s(base_url),
        )

    def perform_update(self, serializer):
        # save the instance first so we can create a task to extract the model output snapshot
        obj = serializer.save()
        extract_nsem_model_output.delay(obj.id)
