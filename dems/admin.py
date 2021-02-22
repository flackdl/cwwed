from django.contrib.gis import admin
from dems.models import DemSource, DemSourceLog, Dem


@admin.register(DemSource)
class DemSourceAdmin(admin.GeoModelAdmin):
    pass


@admin.register(DemSourceLog)
class DemSourceLogAdmin(admin.GeoModelAdmin):
    list_display = ('source', 'date_scanned',)


@admin.register(Dem)
class DemAdmin(admin.GeoModelAdmin):
    list_display = ('path', 'date_updated', 'crs', 'resolution')
