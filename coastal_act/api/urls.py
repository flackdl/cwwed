from rest_framework import routers
from coastal_act.api import viewsets

router = routers.DefaultRouter()
router.register(r'coastal-act-projects', viewsets.CoastalActProjectViewSet)
router.register(r'user', viewsets.CurrentUserViewSet)

urlpatterns = [
]
