import django_filters

from named_storms.models import NsemPsa


class NsemPsaFilter(django_filters.FilterSet):

    class Meta:
        model = NsemPsa
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact'],
            'variable': ['exact'],
        }
