from django.contrib.gis import admin
from named_storms.models import (
    NamedStorm, CoveredData, CoveredDataProvider, NamedStormCoveredData, NsemPsa,
    NamedStormCoveredDataLog, NsemPsaData,
    NsemPsaVariable, NsemPsaUserExport, NsemPsaManifestDataset)


class CoveredDataInline(admin.TabularInline):
    model = NamedStorm.covered_data.through
    show_change_link = True
    extra = 0
    exclude = ('geo',)  # editing an inline geometry isn't straight forward

    def has_add_permission(self, request):
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

    def has_add_permission(self, request):
        # disabled since we can't edit geo which is a required field
        return False


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
    list_display = ('id', 'named_storm', 'date_created', 'date_returned', 'covered_data_snapshot_path', 'path',)
    list_filter = ('named_storm__name', 'date_created', 'date_returned',)
    readonly_fields = ('date_created',)
    inlines = (NsemPsaVariableInline,)


@admin.register(NsemPsaVariable)
class NsemPsaVariableAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'named_storm', 'nsem', 'name', 'data_type', 'auto_displayed')
    list_filter = ('nsem__named_storm__name',)

    def named_storm(self, nsem_psa_variable: NsemPsaVariable):
        return nsem_psa_variable.nsem.named_storm


@admin.register(NsemPsaData)
class NsemPsaDataAdmin(admin.GeoModelAdmin):
    list_display = ('nsem_psa_variable', 'value', 'date')
    list_filter = ('nsem_psa_variable',)


@admin.register(NsemPsaUserExport)
class NsemPsaUserExportAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'nsem', 'user', 'date_created', 'date_expires')
    list_filter = ('nsem__named_storm__name',)

    def named_storm(self, obj):
        return obj.nsem.named_storm


@admin.register(NsemPsaManifestDataset)
class NsemPsaManifestDatasetAdmin(admin.GeoModelAdmin):
    list_display = ('id', 'nsem', 'path')
    list_filter = ('nsem__named_storm__name',)

    def named_storm(self, obj):
        return obj.nsem.named_storm


@admin.register(NamedStormCoveredDataLog)
class DataLogAdmin(admin.ModelAdmin):
    list_display = ('named_storm', 'covered_data', 'date', 'success', 'snapshot',)
    list_filter = ('named_storm__name', 'covered_data', 'date', 'success',)
    readonly_fields = ('date',)  # hidden by default since it uses auto_now_add
