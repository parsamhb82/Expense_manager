from django.db import models
from user.models import TelegramUser

class RoomCreationSession(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    members = models.ManyToManyField(TelegramUser, related_name='rooms')
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='admin_rooms')
    

