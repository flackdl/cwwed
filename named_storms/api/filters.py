from django_filters import rest_framework as filters
from named_storms.models import NsemPsaData, NsemPsaVariable


class NsemPsaDataFilter(filters.FilterSet):
    nsem_psa_variable = filters.ModelChoiceFilter(queryset=NsemPsaVariable.objects.all(), label='Variable')

    class Meta:
        model = NsemPsaData
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact']
        }
