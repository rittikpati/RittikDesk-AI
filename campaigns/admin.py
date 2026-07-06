from django.contrib import admin
from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'status', 'scheduled_at', 'owner', 'created_at']
    list_filter = ['status', 'owner']
    search_fields = ['name', 'subject']
