from django_filters import rest_framework as filters
from named_storms.models import NsemPsaContour, NsemPsaVariable, NsemPsaData


class NsemPsaDataFilterBase(filters.FilterSet):
    """
    base filter for psa data and contours
    """
    nsem_psa_variable = filters.ChoiceFilter(
        choices=zip(NsemPsaVariable.VARIABLE_DATASETS, NsemPsaVariable.VARIABLE_DATASETS),
        method='filter_psa_variable',
    )

    def filter_psa_variable(self, queryset, name, value):
        return queryset.filter(nsem_psa_variable__name=value)

    class Meta:
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact', 'gt', 'gte', 'lt', 'lte']
        }


class NsemPsaContourFilter(NsemPsaDataFilterBase):
    class Meta:
        model = NsemPsaContour
        fields = NsemPsaDataFilterBase.Meta.fields


class NsemPsaDataFilter(NsemPsaDataFilterBase):

    class Meta:
        model = NsemPsaData
        fields = NsemPsaDataFilterBase.Meta.fields
