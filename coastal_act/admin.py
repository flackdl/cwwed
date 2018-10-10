from django.contrib.gis import admin
from coastal_act.models import ComponentProject


@admin.register(ComponentProject)
class ComponentProjectAdmin(admin.GeoModelAdmin):
    pass
