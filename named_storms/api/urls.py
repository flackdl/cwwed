from django.urls import path, include
from rest_framework import routers
from named_storms.api import viewsets

router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
