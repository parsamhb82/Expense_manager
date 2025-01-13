from django.contrib.admin import ModelAdmin, register
from .models import TelegramUser
@register(TelegramUser)
class TelegramUserAdmin(ModelAdmin):
    pass
