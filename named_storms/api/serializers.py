from urllib import parse
from rest_framework import serializers
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData


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
        return '{}://{}/thredds/catalog/covered-data/cache/{}/{}/catalog.html'.format(
            self.context['request'].scheme,
            self.context['request'].get_host(),
            parse.quote(obj.named_storm.name),
            parse.quote(obj.covered_data.name),
        )

    class Meta:
        model = NamedStormCoveredData
        exclude = ('named_storm',)
        depth = 1
