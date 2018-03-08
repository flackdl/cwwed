from django.contrib.gis import admin
from named_storms.models import NamedStorm, CoveredData, CoveredDataProvider, DataProviderProcessor, NamedStormCoveredData


class CoveredDataInline(admin.TabularInline):
    model = NamedStorm.covered_data.through
    show_change_link = True
    extra = 0
    exclude = ('geo',)  # editing an inline geometry isn't possible (no way to inherit from GeoAdmin)

    def has_add_permission(self, request):  # disable since we can't edit geo which is required
        return False


class NamedStormCoveredDataProviderInline(admin.TabularInline):
    model = CoveredDataProvider
    show_change_link = True
    extra = 0


@admin.register(NamedStorm)
class NamedStormInlineAdmin(admin.GeoModelAdmin):
    inlines = (
        CoveredDataInline,
    )


@admin.register(CoveredData)
class NamedStormCoveredDataInlineAdmin(admin.GeoModelAdmin):
    inlines = (
        NamedStormCoveredDataProviderInline,
    )


@admin.register(CoveredDataProvider, DataProviderProcessor, NamedStormCoveredData)
class NamedStormAdmin(admin.GeoModelAdmin):
    pass
