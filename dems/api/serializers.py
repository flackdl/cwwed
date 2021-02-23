from rest_framework import serializers

from dems.models import DemSource, DemSourceLog, Dem


class DemSourceSerializer(serializers.ModelSerializer):

    class Meta:
        model = DemSource
        fields = '__all__'


class DemSourceLogSerializer(serializers.ModelSerializer):

    class Meta:
        model = DemSourceLog
        fields = '__all__'


class DemSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    def get_url(self, dem: Dem):
        return dem.get_url()

    class Meta:
        model = Dem
        fields = '__all__'
