from django.contrib.auth.models import User
from rest_framework import viewsets

from coastal_act.api.serializers import CoastalActProjectSerializer, UserSerializer
from coastal_act.models import CoastalActProject


class CoastalActProjectViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CoastalActProject.objects.all()
    serializer_class = CoastalActProjectSerializer


class CurrentUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_queryset(self):
        """
        Limit to the authenticated user
        """
        return super().get_queryset().filter(username=self.request.user.username)
