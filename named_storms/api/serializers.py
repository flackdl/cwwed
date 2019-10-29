import os
import logging
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.settings import api_settings
from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.models import (
    NamedStorm, NamedStormCoveredData, CoveredData, NsemPsa, CoveredDataProvider,
    NsemPsaVariable, NsemPsaUserExport, NsemPsaManifestDataset, NamedStormCoveredDataSnapshot)
from named_storms.utils import get_opendap_url_nsem, get_opendap_url_covered_data_snapshot, get_opendap_url_nsem_psa

logger = logging.getLogger('cwwed')


class NamedStormSerializer(serializers.ModelSerializer):

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

    class Meta:
        model = NamedStormCoveredDataSnapshot
        fields = '__all__'

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

    manifest = serializers.JSONField(default=dict)
    dates = serializers.ListField(child=serializers.DateTimeField())
    model_output_upload_path = serializers.SerializerMethodField()
    covered_data_storage_url = serializers.SerializerMethodField()
    opendap_url = serializers.SerializerMethodField()
    opendap_url_covered_data = serializers.SerializerMethodField()

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
        serializer = NsemPsaManifestSerializer(data=manifest)

        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)
        elif len(serializer.validated_data['datasets']) == 0:
            raise serializers.ValidationError({'datasets': ['Missing datasets']})

        dataset_errors = {}

        # verify each dataset
        for i, dataset in enumerate(serializer.validated_data['datasets']):

            # create the individual dataset serializer and validate
            dataset_serializer = NsemPsaManifestDatasetSerializer(data=dataset)

            if not dataset_serializer.is_valid():
                dataset_errors[i] = dataset_serializer.errors

        if dataset_errors:
            raise serializers.ValidationError({'datasets': dataset_errors})

        return manifest

    def validate_path(self, s3_path):
        """
        Check that the path is in the expected format (ie. "NSEM/upload/*.tgz") and exists in storage
        """
        storage = S3ObjectStoragePrivate()

        # verify the uploaded psa is in the correct path
        if not s3_path.startswith(self._model_output_upload_path()):
            raise serializers.ValidationError("should be in '{}'".format(self._model_output_upload_path()))

        # verify the path is in the expected format
        if not s3_path.endswith(settings.CWWED_ARCHIVE_EXTENSION):
            raise serializers.ValidationError("should be of the extension '.{}'".format(settings.CWWED_ARCHIVE_EXTENSION))

        # remove any prefixed "location" from the object storage instance
        location_prefix = '{}/'.format(storage.location)
        if s3_path.startswith(location_prefix):
            s3_path = s3_path.replace(location_prefix, '')

        # verify the path exists
        if not storage.exists(s3_path):
            raise serializers.ValidationError("{} does not exist in storage".format(s3_path))

        return s3_path

    def get_model_output_upload_path(self, obj):
        return self._model_output_upload_path()

    @staticmethod
    def _model_output_upload_path() -> str:
        storage = S3ObjectStoragePrivate()
        return storage.path(os.path.join(
            settings.CWWED_NSEM_DIR_NAME,
            settings.CWWED_NSEM_UPLOAD_DIR_NAME,
        ))

    def create(self, validated_data):
        nsem_psa = super().create(validated_data)  # type: NsemPsa

        # manually validate and save the individual psa manifest datasets
        for dataset in validated_data['manifest']['datasets']:
            dataset_serializer = NsemPsaManifestDatasetSerializer(data=dataset)
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
    # validation of the individual datasets is handled in the main serializer
    datasets = serializers.ListSerializer(child=serializers.JSONField())


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
