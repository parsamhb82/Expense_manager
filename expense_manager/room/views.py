from django.shortcuts import render
from rest_framework.generics import CreateAPIView
from .serializers import RoomCreateSerializer
from .models import Room
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated

class RoomCreateView(CreateAPIView):
    serializer_class = RoomCreateSerializer
    get_queryset = Room.objects.all()
    permission_classes = [IsAuthenticated]

