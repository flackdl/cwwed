from django.urls import re_path
from rest_framework import routers
from named_storms.api import viewsets


router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'nsem-psa', viewsets.NSEMViewset)
router.register(r'nsem-psa-user-export', viewsets.NsemPsaUserExportViewset)


urlpatterns = [

    # nested storm -> psa routes
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/geojson/', viewsets.NsemPsaGeoViewset.as_view({'get': 'list'}), name='psa-geojson'),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/variable/$', viewsets.NsemPsaVariableViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/data/dates/$', viewsets.NsemPsaDatesViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/data/time-series/(?P<lat>[-+]?(\d*\.?\d+))/(?P<lon>[-+]?(\d*\.?\d+))/$', viewsets.NsemPsaTimeSeriesViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/export/', viewsets.NsemPsaUserExportNestedViewset.as_view({'get': 'list', 'post': 'create'})),
]
