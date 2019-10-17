from django.urls import re_path
from rest_framework import routers
from named_storms.api import viewsets


router = routers.DefaultRouter()
router.register(r'named-storm', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'named-storm-covered-data-snapshot', viewsets.NamedStormCoveredDataSnapshotViewSet)
router.register(r'nsem-psa', viewsets.NsemPsaViewSet)
router.register(r'nsem-psa-user-export', viewsets.NsemPsaUserExportViewSet)


urlpatterns = [

    # nested storm -> psa routes
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/geojson/', viewsets.NsemPsaGeoViewSet.as_view({'get': 'list'}), name='psa-geojson'),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/variable/$', viewsets.NsemPsaVariableViewSet.as_view({'get': 'list'})),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/data/time-series/(?P<lat>[-+]?(\d*\.?\d+))/(?P<lon>[-+]?(\d*\.?\d+))/$', viewsets.NsemPsaTimeSeriesViewSet.as_view({'get': 'list'})),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/export/', viewsets.NsemPsaUserExportNestedViewSet.as_view({'get': 'list', 'post': 'create'})),
]
