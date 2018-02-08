from django.contrib.gis import admin
from covered_data.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider


@admin.register(NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider)
class CoveredDataAdmin(admin.GeoModelAdmin):
    pass
