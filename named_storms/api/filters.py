from django.contrib.gis.db.models import GeometryField
from django.db.models.functions import Cast
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


class NsemPsaContourFilter(NsemPsaDataFilterBase):
    class Meta:
        model = NsemPsaContour
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact']  # only a single date is accepted
        }


class NsemPsaDataFilter(NsemPsaDataFilterBase):
    point = filters.CharFilter(method='filter_point')

    def filter_point(self, queryset, name, value):
        # cast point to geometry then test equality
        return queryset.annotate(
            point_geom=Cast('point', GeometryField()),
        ).filter(
            point_geom__equals=value,
        )

    class Meta:
        model = NsemPsaData
        fields = {
            'value': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'date': ['exact', 'gt', 'gte', 'lt', 'lte'],
        }
