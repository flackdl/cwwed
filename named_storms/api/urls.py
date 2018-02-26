from django.urls import path, include
from rest_framework import routers
from named_storms.api import viewsets

router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)

named_storm_router = routers.DefaultRouter()
named_storm_router.register(r'covered-data', viewsets.NamedStormCoveredDataViewSet)

covered_data_router = routers.DefaultRouter()
covered_data_router.register(r'providers', viewsets.NamedStormCoveredDataProviderViewSet)


urlpatterns = [
    path('', include(router.urls)),
    path('named-storms/<int:storm_id>/', include(named_storm_router.urls)),
    path('named-storms/<int:storm_id>/covered-data/<int:covered_data_id>/', include(covered_data_router.urls)),
]
