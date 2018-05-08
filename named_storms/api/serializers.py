import re
from urllib import parse
from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData, NSEM
from named_storms.tasks import archive_nsem_covered_data


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

    storage_url = serializers.SerializerMethodField()

    def get_storage_url(self, obj: NSEM):
        return default_storage.storage_url(obj.covered_data_snapshot)

    class Meta:
        model = NSEM
        fields = '__all__'

    def create(self, validated_data):
        # save the instance first so we can create a task to archive the covered data snapshot
        instance = super().create(validated_data)  # type: NSEM
        archive_nsem_covered_data.delay(instance.id)
        return instance
