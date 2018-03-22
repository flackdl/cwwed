import os
import re
import tarfile
from typing import List
from urllib import parse
from django.conf import settings
from rest_framework import serializers
from data_logs.models import NamedStormCoveredDataLog
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData, NSEM
from named_storms.utils import named_storm_nsem_path, create_directory


class NamedStormSerializer(serializers.ModelSerializer):

    class Meta:
        model = NamedStorm
        fields = '__all__'


class NamedStormDetailSerializer(serializers.ModelSerializer):
    covered_data = serializers.SerializerMethodField()

    def get_covered_data(self, storm: NamedStorm):
        return NamedStormCoveredDataSerializer(storm.namedstormcovereddata_set.all(), many=True, context=self.context).data

    class Meta:
        model = NamedStorm
        fields = '__all__'


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

    def archive(self, instance: NSEM, logs: List[NamedStormCoveredDataLog]):
        nsem_path = named_storm_nsem_path(instance.named_storm)
        archive_path = os.path.join(nsem_path, 'v{}'.format(instance.id), 'data.tgz')
        create_directory(os.path.dirname(archive_path))
        tar = tarfile.open(archive_path, mode='w|gz')
        for log in logs:
            tar.add(log.snapshot, arcname=os.path.basename(log.snapshot))
        tar.close()
        return archive_path

    def create(self, validated_data):
        # save the record
        instance = super().create(validated_data)  # type: NSEM

        # archive the covered data snapshots and save the path on this instance
        logs = instance.named_storm.namedstormcovereddatalog_set.filter(success=True).order_by('-date')
        if logs.exists():
            logs_to_archive = []
            for log in logs:
                if log.covered_data.name not in [l.covered_data.name for l in logs_to_archive]:
                    logs_to_archive.append(log)
            validated_data['model_input'] = self.archive(instance, logs_to_archive)
        return instance

    class Meta:
        model = NSEM
        fields = '__all__'
