from django.urls import re_path
from rest_framework import routers
from named_storms.api import viewsets

router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'nsem', viewsets.NSEMViewset)


urlpatterns = [

    # nested storm -> psa routes
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/geojson/', viewsets.NsemPsaGeoViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/variable/$', viewsets.NsemPsaVariableViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/data/$', viewsets.NsemPsaDataViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/data/dates/$', viewsets.NsemPsaDataViewset.as_view({'get': 'dates'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/data/time-series/$', viewsets.NsemPsaDataViewset.as_view({'get': 'time_series'})),
]
