from django.contrib.gis import admin
from audit.models import OpenDapRequestLog


@admin.register(OpenDapRequestLog)
class AuditAdmin(admin.GeoModelAdmin):
    list_display = ('user', 'date_requested', 'path')
    list_filter = ('user', 'date_requested')
