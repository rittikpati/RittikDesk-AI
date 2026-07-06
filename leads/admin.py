from django.contrib import admin
from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['lead_name', 'company', 'status', 'priority', 'source', 'expected_revenue', 'owner', 'created_at']
    list_filter = ['status', 'priority', 'source', 'owner']
    search_fields = ['lead_name', 'company', 'email', 'contact_person']
