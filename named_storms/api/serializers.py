import os
from django.conf import settings
from rest_framework import serializers

from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData, NSEM, CoveredDataProvider, NsemPsaVariable, NsemPsaData
from named_storms.utils import get_opendap_url_nsem, get_opendap_url_nsem_covered_data, get_opendap_url_nsem_psa


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


class NSEMSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model Serializer
    """

    class Meta:
        model = NSEM
        fields = '__all__'

    model_output_upload_path = serializers.SerializerMethodField()
    covered_data_storage_url = serializers.SerializerMethodField()
    opendap_url = serializers.SerializerMethodField()
    opendap_url_psa = serializers.SerializerMethodField()
    opendap_url_covered_data = serializers.SerializerMethodField()

    def get_opendap_url_psa(self, obj: NSEM):
        if 'request' not in self.context:
            return None
        return get_opendap_url_nsem_psa(self.context['request'], obj)

    def get_opendap_url_covered_data(self, obj: NSEM):
        if 'request' not in self.context:
            return None
        if not obj.covered_data_snapshot:
            return None
        return dict((cdl.covered_data.id, get_opendap_url_nsem_covered_data(self.context['request'], obj, cdl.covered_data)) for cdl in obj.covered_data_logs.all())

    def get_opendap_url(self, obj: NSEM):
        if 'request' not in self.context:
            return None
        if not obj.model_output_snapshot_extracted:
            return None
        return get_opendap_url_nsem(self.context['request'], obj)

    def get_covered_data_storage_url(self, obj: NSEM):
        storage = S3ObjectStoragePrivate()
        if obj.covered_data_snapshot:
            return storage.storage_url(obj.covered_data_snapshot)
        return None

    def validate_model_output_snapshot(self, value):
        """
        Check that it hasn't already been processed
        Check that the path is in the expected format (ie. "NSEM/upload/v68.tgz") and exists in storage
        """
        storage = S3ObjectStoragePrivate()
        obj = self.instance  # type: NSEM
        if obj:

            # already extracted
            if obj.model_output_snapshot_extracted:
                raise serializers.ValidationError('Cannot be updated since the model output has already been processed')

            s3_path = self._get_model_output_upload_path(obj)

            # verify the path is in the expected format
            if s3_path != value:
                raise serializers.ValidationError("'model_output_snapshot' should equal '{}'".format(s3_path))

            # remove any prefixed "location" from the object storage instance
            location_prefix = '{}/'.format(storage.location)
            if s3_path.startswith(location_prefix):
                s3_path = s3_path.replace(location_prefix, '')

            # verify the path exists
            if not storage.exists(s3_path):
                raise serializers.ValidationError("{} does not exist in storage".format(s3_path))

            return s3_path
        return value

    def get_model_output_upload_path(self, obj: NSEM) -> str:
        return self._get_model_output_upload_path(obj)

    @staticmethod
    def _get_model_output_upload_path(obj: NSEM) -> str:
        storage = S3ObjectStoragePrivate()
        return storage.path(os.path.join(
            settings.CWWED_NSEM_DIR_NAME,
            settings.CWWED_NSEM_UPLOAD_DIR_NAME,
            'v{}.{}'.format(obj.id, settings.CWWED_ARCHIVE_EXTENSION)),
        )


class NsemPsaVariableSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model PSA Variable Serializer
    """

    class Meta:
        model = NsemPsaVariable
        fields = '__all__'
