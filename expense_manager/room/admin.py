from django.contrib.admin import ModelAdmin, register
from .models import Room

@register(Room)
class RoomAdmin(ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description')
