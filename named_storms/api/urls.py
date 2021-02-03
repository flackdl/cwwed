from django.urls import re_path
from rest_framework import routers
from named_storms.api import viewsets, views


router = routers.DefaultRouter()
router.register(r'named-storm', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'named-storm-covered-data-snapshot', viewsets.NamedStormCoveredDataSnapshotViewSet)
router.register(r'nsem-psa', viewsets.NsemPsaViewSet)
router.register(r'nsem-psa-user-export', viewsets.NsemPsaUserExportViewSet)
router.register(r'nsem-psa-manifest-dataset', viewsets.NsemPsaManifestDatasetViewSet)


urlpatterns = [

    # nested storm -> psa routes
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/contour/$', viewsets.NsemPsaContourViewSet.as_view({'get': 'list'}), name='psa-contour'),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/data/$', viewsets.NsemPsaDataViewSet.as_view({'get': 'list'}), name='psa-wind-barb-geojson'),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/data/time-series/(?P<lat>[-+]?(\d*\.?\d+))/(?P<lon>[-+]?(\d*\.?\d+))/$',
            viewsets.NsemPsaTimeSeriesViewSet.as_view({'get': 'list'})),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/data/wind-barbs/(?P<date>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)/$',
            viewsets.NsemPsaWindBarbsViewSet.as_view({'get': 'list'})),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/variable/$', viewsets.NsemPsaVariableViewSet.as_view({'get': 'list'})),
    re_path(r'^named-storm/(?P<storm_id>\d+)/psa/export/$', viewsets.NsemPsaUserExportNestedViewSet.as_view({'get': 'list', 'post': 'create'})),

    # options
    re_path(r'^psa-options/', views.PsaOptions.as_view())
]
