from django.shortcuts import render
from .serializers import UserRegisterSerializer
from rest_framework.generics import CreateAPIView
from django.contrib.auth.models import User
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


class UserRegisterView(CreateAPIView):
    serializer_class = UserRegisterSerializer
    queryset = User.objects.all()

class Login(TokenObtainPairView):
    pass

class RefreshToken(TokenRefreshView):
    pass
