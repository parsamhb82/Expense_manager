from rest_framework import serializers
from .models import Room
from django.contrib.auth.models import User

class RoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['name', 'description']
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user
        room = Room.objects.create(admin=user, **validated_data)
        room.members.add(user)
        room.save()
        return room