from django.contrib import admin
from data_logs.models import NamedStormCoveredDataLog


@admin.register(NamedStormCoveredDataLog)
class DataLogAdmin(admin.ModelAdmin):
    list_display = ('named_storm', 'covered_data', 'date', 'success', 'snapshot',)
    list_filter = ('named_storm', 'covered_data', 'date', 'success',)
    readonly_fields = ('date',)  # hidden by default since it uses auto_now_add
