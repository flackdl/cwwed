from django.contrib.gis import admin
from named_storms.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider, DataProviderProcessor


@admin.register(NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider, DataProviderProcessor)
class CoveredDataAdmin(admin.GeoModelAdmin):
    pass
