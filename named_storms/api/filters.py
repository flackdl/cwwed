from django_filters import rest_framework as filters
from named_storms.models import NsemPsaContour, NsemPsaVariable


class NsemPsaContourFilter(filters.FilterSet):
    nsem_psa_variable = filters.ModelChoiceFilter(queryset=NsemPsaVariable.objects.all(), label='Variable')

    class Meta:
        model = NsemPsaContour
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact']
        }
