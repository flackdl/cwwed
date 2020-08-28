import logging
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.settings import api_settings
from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.models import (
    NamedStorm, NamedStormCoveredData, CoveredData, NsemPsa, CoveredDataProvider,
    NsemPsaVariable, NsemPsaUserExport, NsemPsaManifestDataset, NamedStormCoveredDataSnapshot, NsemPsaData)
from named_storms.utils import get_opendap_url_nsem, get_opendap_url_covered_data_snapshot

logger = logging.getLogger('cwwed')


class NamedStormSerializer(serializers.ModelSerializer):
    center_coords = serializers.SerializerMethodField()

    def get_center_coords(self, named_storm: NamedStorm):
        return named_storm.geo.centroid.coords

    class Meta:
        model = NamedStorm
        fields = '__all__'


class NamedStormDetailSerializer(NamedStormSerializer):
    covered_data = serializers.SerializerMethodField()

    def get_covered_data(self, storm: NamedStorm):
        return NamedStormCoveredDataSerializer(storm.namedstormcovereddata_set.all(), many=True, context=self.context).data


class CoveredDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = CoveredData
        fields = '__all__'

    providers = serializers.SerializerMethodField()

    def get_providers(self, covered_data: CoveredData):
        return CoveredDataProviderSerializer(covered_data.covereddataprovider_set.all(), many=True).data


class CoveredDataProviderSerializer(serializers.ModelSerializer):

    class Meta:
        model = CoveredDataProvider
        fields = '__all__'


class NamedStormCoveredDataSerializer(serializers.ModelSerializer):

    class Meta:
        model = NamedStormCoveredData
        exclude = ('named_storm',)
        depth = 1


class NamedStormCoveredDataSnapshotSerializer(serializers.ModelSerializer):
    covered_data_storage_url = serializers.SerializerMethodField()

    class Meta:
        model = NamedStormCoveredDataSnapshot
        fields = '__all__'

    def get_covered_data_storage_url(self, obj: NamedStormCoveredDataSnapshot):
        return obj.get_covered_data_storage_url()

    def validate(self, data):
        named_storm = data['named_storm']  # type: NamedStorm
        # verify there's covered data logs to create a snapshot from
        if not named_storm.namedstormcovereddatalog_set.filter(success=True).exists():
            raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY: ['There are no covered data for this storm']})
        return super().validate(data)


class NsemPsaSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model Serializer
    """

    class Meta:
        model = NsemPsa
        fields = '__all__'
        read_only_fields = [
            'date_created', 'extracted', 'date_validation',
            'validated', 'validation_exceptions',
            'processed', 'date_processed',
        ]

    dates = serializers.ListField(child=serializers.DateTimeField())
    covered_data_storage_url = serializers.SerializerMethodField()
    opendap_url = serializers.SerializerMethodField()
    opendap_url_covered_data = serializers.SerializerMethodField()
    covered_data_snapshot = serializers.ModelField(
        model_field=NsemPsa()._meta.get_field('covered_data_snapshot'),
        # automatically associates the most recent snapshot in validate()
        required=False,
    )

    def validate(self, attrs):
        if not self.instance:
            # populate the most recent covered data snapshot for this storm
            named_storm_id = self.context['request'].data.get('named_storm')
            qs = NamedStormCoveredDataSnapshot.objects.filter(named_storm__id=named_storm_id, date_completed__isnull=False)
            qs = qs.order_by('-date_completed')
            attrs['covered_data_snapshot'] = qs.first()
        return super().validate(attrs)

    def get_opendap_url_covered_data(self, obj: NsemPsa):
        if 'request' not in self.context:
            return None
        if not obj.covered_data_snapshot:
            return None
        return dict(
            (cdl.covered_data.id, get_opendap_url_covered_data_snapshot(self.context['request'], obj.covered_data_snapshot, cdl.covered_data))
            for cdl in obj.covered_data_snapshot.covered_data_logs.all()
        )

    def get_opendap_url(self, obj: NsemPsa):
        if 'request' not in self.context:
            return None
        if not obj.validated:
            return None
        return get_opendap_url_nsem(self.context['request'], obj)

    def get_covered_data_storage_url(self, obj: NsemPsa):
        return obj.covered_data_snapshot.get_covered_data_storage_url()

    def validate_manifest(self, manifest: dict):
        # manually validating manifest since nested writes aren't supported in drf
        serializer = NsemPsaManifestSerializer(data=manifest)
        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)
        return manifest

    def validate_path(self, s3_path):
        """
        Check that the path is in the expected format (ie. "NSEM/upload/*.tgz") and exists in storage
        """
        storage = S3ObjectStoragePrivate(force_root_location=True)

        # verify the path is in the expected format
        if not s3_path.endswith(settings.CWWED_ARCHIVE_EXTENSION):
            raise serializers.ValidationError("should be of the extension '.{}'".format(settings.CWWED_ARCHIVE_EXTENSION))

        # verify the path exists
        if not storage.exists(s3_path):
            raise serializers.ValidationError("{} does not exist in storage".format(s3_path))

        return s3_path

    def create(self, validated_data):
        nsem_psa = super().create(validated_data)  # type: NsemPsa

        # manually save the individual psa manifest datasets since nested writes aren't supported in drf
        for dataset in validated_data['manifest']['datasets']:
            dataset_serializer = NsemPsaManifestDatasetSerializer(data=dataset)
            # this will have already been validated but it's necessary to populate `validate_data`
            dataset_serializer.is_valid(raise_exception=True)
            nsem_psa.nsempsamanifestdataset_set.create(**dataset_serializer.validated_data)

        return nsem_psa


class NsemPsaManifestDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = NsemPsaManifestDataset
        exclude = ['nsem']

    def validate_variables(self, variables: list):
        # validate the "variables" are a subset of NsemPsaVariable.VARIABLE_DATASETS
        if not set(variables).issubset(NsemPsaVariable.VARIABLE_DATASETS):
            raise serializers.ValidationError('variables must be in {}'.format(NsemPsaVariable.VARIABLE_DATASETS))
        return variables


class NsemPsaManifestSerializer(serializers.Serializer):
    datasets = serializers.ListSerializer(child=NsemPsaManifestDatasetSerializer(), allow_empty=False)


class NsemPsaVariableSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model PSA Variable Serializer
    """

    class Meta:
        model = NsemPsaVariable
        fields = '__all__'


class NsemPsaUserExportSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model PSA User Export Serializer
    """

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def validate(self, data):

        data = super().validate(data)

        # require date_filter for specific formats
        date_specific_formats = [
            NsemPsaUserExport.FORMAT_CSV, NsemPsaUserExport.FORMAT_SHAPEFILE,
            NsemPsaUserExport.FORMAT_GEOJSON, NsemPsaUserExport.FORMAT_KML,
        ]
        if data['format'] in date_specific_formats and not data.get('date_filter'):
            raise serializers.ValidationError({"date_filter": ["date_filter required this export format"]})

        return data

    class Meta:
        model = NsemPsaUserExport
        fields = '__all__'


class NsemPsaDataSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model PSA Data Serializer
    """

    class Meta:
        model = NsemPsaData
        fields = '__all__'
