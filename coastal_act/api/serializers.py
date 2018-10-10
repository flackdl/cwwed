from rest_framework import serializers

from coastal_act.models import CoastalActProject


class CoastalActProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = CoastalActProject
        fields = '__all__'
