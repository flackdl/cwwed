from rest_framework import serializers
from named_storms.models import NamedStorm, NamedStormCoveredData, CoveredData


class NamedStormSerializer(serializers.ModelSerializer):
    class Meta:
        model = NamedStorm
        fields = '__all__'


class NamedStormDetailSerializer(serializers.ModelSerializer):
    covered_data = serializers.SerializerMethodField()

    def get_covered_data(self, storm: NamedStorm):
        return NamedStormCoveredDataSerializer(storm.namedstormcovereddata_set.all(), many=True).data

    class Meta:
        model = NamedStorm
        fields = '__all__'


class CoveredDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoveredData
        fields = '__all__'


class NamedStormCoveredDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = NamedStormCoveredData
        exclude = ('named_storm',)
        depth = 1
