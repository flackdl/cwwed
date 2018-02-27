from django.contrib.gis import admin
from named_storms.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider, DataProviderProcessor


class NamedStormCoveredDataInline(admin.TabularInline):
    model = NamedStormCoveredData
    show_change_link = True
    extra = 0
    readonly_fields = ('geo',)


class NamedStormCoveredDataProviderInline(admin.TabularInline):
    model = NamedStormCoveredDataProvider
    show_change_link = True
    extra = 0


@admin.register(NamedStorm)
class NamedStormInlineAdmin(admin.OSMGeoAdmin):
    inlines = (
        NamedStormCoveredDataInline,
    )


@admin.register(NamedStormCoveredData)
class NamedStormCoveredDataInlineAdmin(admin.OSMGeoAdmin):
    inlines = (
        NamedStormCoveredDataProviderInline,
    )


@admin.register(NamedStormCoveredDataProvider, DataProviderProcessor)
class NamedStormAdmin(admin.GeoModelAdmin):
    pass
