from django.urls import path
from .views import UserRegisterView, Login, RefreshToken

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='user-register'),
    path('login/', Login.as_view(), name='login'),
    path('refresh/', RefreshToken.as_view(), name='refresh'),
]