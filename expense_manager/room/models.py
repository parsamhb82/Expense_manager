from django.db import models
from  user.models import TelegramUser

class Room(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    members = models.ManyToManyField(TelegramUser, related_name='rooms')
    admin = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='admin_rooms')
    code = models.CharField(max_length=16, unique=True)
    

    def __str__(self):
        return self.name

class Expense(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='expenses')
    payer = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='paid_expenses')
    participants = models.ManyToManyField(TelegramUser, related_name='participated_expenses')

class Payment(models.Model):
    amount = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='payments')
    payer = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='paid_payments')
    participant = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='participated_payments')
    is_paid = models.BooleanField(default=False)