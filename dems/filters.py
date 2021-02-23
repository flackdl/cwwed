from django_filters import rest_framework as filters

from dems.models import Dem, DemSourceLog


class DemSourceLogFilter(filters.FilterSet):
    class Meta:
        model = DemSourceLog
        fields = {
            'source': ['exact'],
            'date_scanned': ['exact', 'gte', 'lte'],
        }


class DemFilter(filters.FilterSet):
    class Meta:
        model = Dem
        fields = {
            'source': ['exact'],
            'path': ['exact', 'icontains'],
            'date_updated': ['exact', 'gte', 'lte'],
        }
