from rest_framework import viewsets

from dems.models import DemSource, DemSourceLog, Dem
from dems.api.serializers import DemSerializer, DemSourceSerializer, DemSourceLogSerializer


class DemSourceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemSource.objects.all()
    serializer_class = DemSourceSerializer


class DemSourceLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DemSourceLog.objects.all()
    serializer_class = DemSourceLogSerializer


class DemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Dem.objects.all()
    serializer_class = DemSerializer
