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

    class Meta:
        model = Dem
        fields = '__all__'
