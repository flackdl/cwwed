from rest_framework import routers
from dems.api import viewsets

router = routers.DefaultRouter()
router.register(r'dem-source', viewsets.DemSourceViewSet)
router.register(r'dem-source-log', viewsets.DemSourceLogViewSet)
router.register(r'dem', viewsets.DemViewSet)
