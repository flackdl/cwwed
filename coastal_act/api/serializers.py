from django.contrib.auth.models import User
from rest_framework import serializers

from coastal_act.models import CoastalActProject


class CoastalActProjectSerializer(serializers.ModelSerializer):

    class Meta:
        model = CoastalActProject
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'is_superuser', 'username', 'first_name', 'last_name', 'email')
