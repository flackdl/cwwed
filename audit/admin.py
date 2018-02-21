from django.contrib.gis import admin
from audit.models import ThreddsRequestLog


@admin.register(ThreddsRequestLog)
class CoveredDataAdmin(admin.GeoModelAdmin):
    pass
