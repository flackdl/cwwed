from django.urls import path, include
from rest_framework import routers
from named_storms.api import viewsets
from rest_framework.authtoken import views

router = routers.DefaultRouter()
router.register(r'named-storms', viewsets.NamedStormViewSet)
router.register(r'covered-data', viewsets.CoveredDataViewSet)
router.register(r'nsem', viewsets.NSEMViewset)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', views.obtain_auth_token),  # authenticates user and returns token
]
