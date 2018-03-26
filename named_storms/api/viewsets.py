from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets, exceptions
from rest_framework.decorators import detail_route
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

    @detail_route(url_path='covered-data', methods=['get'])
    def covered_data(self, *args, **kwargs):
        """
        Returns the actual covered data archive as a streamed response
        """
        instance = self.get_object()  # type: NSEM

        # handle absent archive
        if not instance.model_input:
            raise exceptions.NotFound

        # create the response
        response = FileResponse(
            open(instance.model_input, 'rb'),
            content_type=settings.CWWED_NSEM_ARCHIVE_CONTENT_TYPE)

        # include a helpful filename header
        response['Content-Disposition'] = 'attachment; filename="covered-data.{}"'.format(
            settings.CWWED_NSEM_ARCHIVE_EXTENSION)

        return response
