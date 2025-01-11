from django.db import models
from user.models import TelegramUser
from room.models import Room

class RoomCreationSession(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    members = models.ManyToManyField(TelegramUser, related_name='rooms')
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='admin_rooms')


class ExpenseCreationSession(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.BigIntegerField()
    payer = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='paid_expenses')
    participants = models.ManyToManyField(TelegramUser, related_name='participated_expenses')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='expenses')
    

