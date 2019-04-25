from django.urls import path, re_path
from rest_framework import routers
from named_storms.api import views
from named_storms.api import viewsets

router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'nsem', viewsets.NSEMViewset)


urlpatterns = [
    path('psa-filter/', views.PSAFilterView.as_view()),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/geojson/(?P<date>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})/', viewsets.NsemPsaGeoViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/variable/$', viewsets.NsemPsaVariableViewset.as_view({'get': 'list'})),
    re_path(r'^named-storms/(?P<storm_id>\d+)/psa/data/$', viewsets.NsemPsaDataViewset.as_view({'get': 'list'})),
]
