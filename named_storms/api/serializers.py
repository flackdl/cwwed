import os
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.fields import CurrentUserDefault
from cwwed.storage_backends import S3ObjectStoragePrivate
from named_storms.api.fields import CurrentNsemPsaDefault
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData, NsemPsa, CoveredDataProvider, NsemPsaVariable, NsemPsaUserExport
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


class NsemPsaSerializer(serializers.ModelSerializer):
    """
    Named Storm Event Model Serializer
    """

    class Meta:
        model = NsemPsa
        fields = '__all__'

    # TODO - should dates be required up front or extracted from netcdf files after creation?
    dates = serializers.ListField(child=serializers.DateTimeField())
    model_output_upload_path = serializers.SerializerMethodField()
    covered_data_storage_url = serializers.SerializerMethodField()
    opendap_url = serializers.SerializerMethodField()
    opendap_url_psa = serializers.SerializerMethodField()
    opendap_url_covered_data = serializers.SerializerMethodField()

    def get_opendap_url_psa(self, obj: NsemPsa):
        if 'request' not in self.context:
            return None
        return get_opendap_url_nsem_psa(self.context['request'], obj)

    def get_opendap_url_covered_data(self, obj: NsemPsa):
        if 'request' not in self.context:
            return None
        if not obj.covered_data_snapshot_path:
            return None
        return dict((cdl.covered_data.id, get_opendap_url_nsem_covered_data(self.context['request'], obj, cdl.covered_data)) for cdl in obj.covered_data_logs.all())

    def get_opendap_url(self, obj: NsemPsa):
        if 'request' not in self.context:
            return None
        if not obj.snapshot_extracted:
            return None
        return get_opendap_url_nsem(self.context['request'], obj)

    def get_covered_data_storage_url(self, obj: NsemPsa):
        return obj.get_covered_data_storage_url()

    def validate_snapshot_path(self, value):
        """
        Check that it hasn't already been extracted and validated
        Check that the path is in the expected format (ie. "NSEM/upload/v68.tgz") and exists in storage
        """
        storage = S3ObjectStoragePrivate()
        obj = self.instance  # type: NsemPsa
        if obj:

            # already validated
            if obj.validated:
                raise serializers.ValidationError('Cannot be updated since the model output has already been extracted and validated')

            s3_path = self._get_model_output_upload_path(obj)

            # verify the path is in the expected format
            if s3_path != value:
                raise serializers.ValidationError("'snapshot_path' should equal '{}'".format(s3_path))

            # remove any prefixed "location" from the object storage instance
            location_prefix = '{}/'.format(storage.location)
            if s3_path.startswith(location_prefix):
                s3_path = s3_path.replace(location_prefix, '')

            # verify the path exists
            if not storage.exists(s3_path):
                raise serializers.ValidationError("{} does not exist in storage".format(s3_path))

            return s3_path
        return value

    def get_model_output_upload_path(self, obj: NsemPsa) -> str:
        return self._get_model_output_upload_path(obj)

    @staticmethod
    def _get_model_output_upload_path(obj: NsemPsa) -> str:
        storage = S3ObjectStoragePrivate()
        return storage.path(os.path.join(
            settings.CWWED_NSEM_DIR_NAME,
            settings.CWWED_NSEM_UPLOAD_DIR_NAME,
            '{}.{}'.format(obj.id, settings.CWWED_ARCHIVE_EXTENSION)),
        )


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

    # overriding these fields to use the provided serializer context
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), default=CurrentUserDefault())
    nsem = serializers.PrimaryKeyRelatedField(queryset=NsemPsa.objects.all(), default=CurrentNsemPsaDefault())

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
