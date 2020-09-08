from django.contrib.gis import admin
from named_storms.models import (
    NamedStorm, CoveredData, CoveredDataProvider, NamedStormCoveredData, NsemPsa,
    NamedStormCoveredDataLog, NsemPsaContour,
    NsemPsaVariable, NsemPsaUserExport, NsemPsaManifestDataset, NamedStormCoveredDataSnapshot)


class CoveredDataInline(admin.TabularInline):
    model = NamedStorm.covered_data.through
    show_change_link = True
    extra = 0
    exclude = ('geo',)  # editing an inline geometry isn't straight forward

    def has_add_permission(self, request, obj):
        # disabled since we can't edit geo which is a required field
        return False


class NamedStormCoveredDataProviderInline(admin.TabularInline):
    model = CoveredDataProvider
    show_change_link = True
    extra = 0


class NsemPsaVariableInline(admin.TabularInline):
    model = NsemPsaVariable
    show_change_link = True
    extra = 0
    fields = ('nsem', 'name', 'data_type')

    def has_add_permission(self, request, obj):
        # disabled since we can't edit geo which is a required field
        return False


class NsemPsaManifestDatasetInline(admin.TabularInline):
    model = NsemPsaManifestDataset
    show_change_link = True
    extra = 0
    fields = ('nsem', 'path', 'variables')


@admin.register(NamedStorm)
class NamedStormInlineAdmin(admin.GeoModelAdmin):
    inlines = (
        CoveredDataInline,
    )
    list_display = ('name', 'date_start', 'date_end', 'active',)
    list_filter = ('name', 'date_start', 'date_end', 'active',)


@admin.register(CoveredData)
class CoveredDataAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'name', 'active', 'url',)
    inlines = (
        NamedStormCoveredDataProviderInline,
    )


@admin.register(CoveredDataProvider)
class CoveredDataProviderAdmin(admin.GeoModelAdmin):
    list_display = ('name', 'covered_data', 'active', 'url', 'processor_factory', 'processor_source', 'epoch_datetime',)
    list_filter = ('active',)


@admin.register(NamedStormCoveredData)
class NamedStormCoveredDataAdmin(admin.GeoModelAdmin):
    list_display = ('named_storm', 'covered_data', 'date_start', 'date_end')
    list_filter = ('named_storm', 'covered_data', 'date_start', 'date_end')


@admin.register(NsemPsa)
class NSEMAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'named_storm', 'date_created', 'path', 'extracted', 'validated', 'processed')
    list_filter = ('named_storm__name', 'date_created', 'extracted', 'validated', 'processed',)
    readonly_fields = ('date_created',)
    inlines = (NsemPsaVariableInline, NsemPsaManifestDatasetInline,)


@admin.register(NsemPsaVariable)
class NsemPsaVariableAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'nsem', 'name', 'display_name', 'data_type', 'auto_displayed')
    list_filter = ('nsem__named_storm',)
    readonly_fields = ('display_name',)

    def get_list_filter(self, request):
        filters = list(super().get_list_filter(request))
        # conditionally include nsem filter if a specific storm filter exists
        if 'nsem__named_storm__id__exact' in request.GET:
            filters = filters + ['nsem']
        return tuple(filters)


@admin.register(NsemPsaContour)
class NsemPsaContourAdmin(admin.GeoModelAdmin):
    list_display = ('nsem_psa_variable', 'value', 'date')
    list_filter = ('nsem_psa_variable__nsem__named_storm',)


@admin.register(NsemPsaUserExport)
class NsemPsaUserExportAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'nsem', 'user', 'date_created', 'date_expires')
    list_filter = ('nsem__named_storm__name',)


@admin.register(NsemPsaManifestDataset)
class NsemPsaManifestDatasetAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'nsem', 'path')
    list_filter = ('nsem__named_storm',)


@admin.register(NamedStormCoveredDataSnapshot)
class NsemPsaManifestDatasetAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'named_storm', 'date_requested', 'date_completed', 'path')
    list_filter = ('named_storm__name',)

    def named_storm(self, obj):
        # for list_display
        return obj.named_storm


@admin.register(NamedStormCoveredDataLog)
class DataLogAdmin(admin.ModelAdmin):
    list_display = ('named_storm', 'covered_data', 'date_created', 'success', 'snapshot',)
    list_filter = ('named_storm__name', 'covered_data', 'date_created', 'success',)
    readonly_fields = ('date_created',)  # hidden by default since it uses auto_now_add
