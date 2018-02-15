from rest_framework import serializers
from covered_data.models import NamedStorm, NamedStormCoveredData, NamedStormCoveredDataProvider


class NamedStormSerializer(serializers.ModelSerializer):
    class Meta:
        model = NamedStorm
        fields = '__all__'


class NamedStormCoveredDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = NamedStormCoveredData
        fields = '__all__'


class NamedStormCoveredDataProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = NamedStormCoveredDataProvider
        fields = '__all__'
