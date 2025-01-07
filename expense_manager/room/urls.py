from django.urls import path    
from .views import RoomCreateView

urlpatterns = [
    path('create/', RoomCreateView.as_view(), name='room-create'),
]