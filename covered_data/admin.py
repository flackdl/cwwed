from django.contrib.gis import admin
from covered_data.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider, DataProviderProcessor


@admin.register(NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider, DataProviderProcessor)
class CoveredDataAdmin(admin.GeoModelAdmin):
    pass
