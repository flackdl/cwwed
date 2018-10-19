from django.contrib.gis import admin
from audit.models import ThreddsRequestLog


@admin.register(ThreddsRequestLog)
class AuditAdmin(admin.GeoModelAdmin):
    list_display = ('user', 'date_requested', 'path')
    list_filter = ('user', 'date_requested')
