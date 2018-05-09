import os
import re
from urllib import parse
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData, NSEM


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


class NamedStormCoveredDataSerializer(serializers.ModelSerializer):
    thredds_url = serializers.SerializerMethodField()

    def get_thredds_url(self, obj: NamedStormCoveredData):
        """
        find the most recent, successful covered data snapshot and return it's thredds url
        """
        logs = obj.named_storm.namedstormcovereddatalog_set.filter(success=True, covered_data=obj.covered_data).order_by('-date')
        if logs.exists():
            # TODO - this year-based naming convention is deprecated and needs updating
            # get date-stamped year for directory name
            match = re.match(r'.*(?P<year>\d{4}-\d{2}-\d{2}).*', logs[0].snapshot)
            if match:
                year = match.group('year')
                return '{}://{}/thredds/catalog/cwwed/{}/{}/{}/{}/catalog.html'.format(
                    self.context['request'].scheme,
                    self.context['request'].get_host(),
                    parse.quote(obj.named_storm.name),
                    parse.quote(settings.CWWED_COVERED_DATA_DIR_NAME),
                    year,
                    parse.quote(obj.covered_data.name),
                )
        return None

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

    storage_url = serializers.SerializerMethodField()

    def get_storage_url(self, obj: NSEM):
        if obj.covered_data_snapshot:
            return default_storage.storage_url(obj.covered_data_snapshot)
        return None

    def validate_model_output_snapshot(self, value):
        """
        Check that the path is in the expected format (ie. "NSEM/upload/v68.tgz") and exists in storage
        """
        if self.instance:
            s3_path = os.path.join(
                settings.CWWED_NSEM_DIR_NAME,
                settings.CWWED_NSEM_UPLOAD_DIR_NAME,
                'v{}.{}'.format(self.instance.id, settings.CWWED_ARCHIVE_EXTENSION)
            )
            # verify the path is in the expected format
            if s3_path != value:
                raise serializers.ValidationError("'model_output_snapshot' should equal '{}'".format(s3_path))
            # verify the path exists
            if not default_storage.exists(s3_path):
                raise serializers.ValidationError("{} does not exist in storage".format(s3_path))
        return value
