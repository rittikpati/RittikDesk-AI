from django.contrib import admin
from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'company', 'owner', 'created_at']
    list_filter = ['owner']
    search_fields = ['full_name', 'email', 'company']
