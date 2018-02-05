from django.contrib.gis import admin
from covered_data.models import NamedStorm, CoveredData, CoveredDataProvider


@admin.register(NamedStorm, CoveredData, CoveredDataProvider)
class CoveredDataAdmin(admin.GeoModelAdmin):
    pass
