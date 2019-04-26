from django_filters import rest_framework as filters
from named_storms.models import NsemPsaData


class NsemPsaDataFilter(filters.FilterSet):
    variable = filters.CharFilter(field_name='nsem_psa_variable', lookup_expr='name')

    class Meta:
        model = NsemPsaData
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact']
        }
