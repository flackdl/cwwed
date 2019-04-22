from django.urls import path
from rest_framework import routers
from named_storms.api import views
from named_storms.api import viewsets

router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'nsem', viewsets.NSEMViewset)


urlpatterns = [
    path('psa-filter/', views.PSAFilterView.as_view()),
    path('named-storms/<int:storm_id>/psa/', viewsets.NsemPsaViewset.as_view({'get': 'list'})),
]
