from rest_framework import viewsets
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData
from named_storms.api.serializers import NamedStormSerializer, NamedStormCoveredDataSerializer, CoveredDataSerializer, NamedStormDetailSerializer


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStorm.objects.all()
    serializer_class = NamedStormSerializer

    def get_serializer_class(self):
        # return a more detailed representation for a specific storm
        if self.action == 'retrieve':
            return NamedStormDetailSerializer
        return super().get_serializer_class()


class CoveredDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoveredData.objects.all()
    serializer_class = CoveredDataSerializer


class NamedStormCoveredDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStormCoveredData.objects.all()
    serializer_class = NamedStormCoveredDataSerializer

    def get_queryset(self):
        """
        Expects to be nested under a named storm router
        """
        return super().get_queryset().filter(named_storm__id=self.kwargs['storm_id'])
