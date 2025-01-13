from django.db import models
from user.models import TelegramUser
from room.models import Room

class RoomCreationSession(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    members = models.ManyToManyField(TelegramUser, related_name='room_creation_sessions')
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='admin_room_creation_sessions')


class ExpenseCreationSession(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    amount = models.BigIntegerField(blank=True, null=True)
    payer = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='expense_creation_paid_sessions')
    participants = models.ManyToManyField(TelegramUser, related_name='expense_creation_participated_sessions')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='expense_creation_sessions')

class AddRoomMemberSession(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='add_member_sessions')
    member = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='added_as_member_sessions', blank=True, null=True)
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name='add_room_member_sessions')
    

