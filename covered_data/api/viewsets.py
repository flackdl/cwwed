from rest_framework import viewsets
from covered_data.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider
from covered_data.api.serializers import NamedStormSerializer, NamedStormCoveredDataSerializer, NamedStormCoveredDataProviderSerializer


class NamedStormViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStorm.objects.all()
    serializer_class = NamedStormSerializer


class NamedStormCoveredDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStormCoveredData.objects.all()
    serializer_class = NamedStormCoveredDataSerializer


class NamedStormCoveredDataProviderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NamedStormCoveredDataProvider.objects.all()
    serializer_class = NamedStormCoveredDataProviderSerializer
