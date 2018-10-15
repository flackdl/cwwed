from django.contrib.gis import admin
from coastal_act.models import CoastalActProject


@admin.register(CoastalActProject)
class ComponentProjectAdmin(admin.GeoModelAdmin):
    pass
