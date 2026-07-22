from django.contrib import admin
from .models import Deal


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ['deal_name', 'company', 'stage', 'value', 'currency', 'priority', 'status', 'owner', 'created_at']
    list_filter = ['stage', 'priority', 'status', 'source', 'owner']
    search_fields = ['deal_name', 'company', 'description', 'notes']
