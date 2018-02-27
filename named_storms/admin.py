from django.contrib.gis import admin
from named_storms.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider, DataProviderProcessor


class NamedStormCoveredDataInline(admin.TabularInline):
    model = NamedStormCoveredData
    show_change_link = True
    extra = 0
    exclude = ('geo',)  # editing an inline geometry isn't possible (no way to inherit from GeoAdmin)


class NamedStormCoveredDataProviderInline(admin.TabularInline):
    model = NamedStormCoveredDataProvider
    show_change_link = True
    extra = 0


@admin.register(NamedStorm)
class NamedStormInlineAdmin(admin.GeoModelAdmin):
    inlines = (
        NamedStormCoveredDataInline,
    )


@admin.register(NamedStormCoveredData)
class NamedStormCoveredDataInlineAdmin(admin.GeoModelAdmin):
    inlines = (
        NamedStormCoveredDataProviderInline,
    )


@admin.register(NamedStormCoveredDataProvider, DataProviderProcessor)
class NamedStormAdmin(admin.GeoModelAdmin):
    pass
