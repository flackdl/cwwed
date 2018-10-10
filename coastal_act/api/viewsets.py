from rest_framework import viewsets
from coastal_act.api.serializers import CoastalActProjectSerializer
from coastal_act.models import CoastalActProject


class CoastalActProjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoastalActProject.objects.all()
    serializer_class = CoastalActProjectSerializer
