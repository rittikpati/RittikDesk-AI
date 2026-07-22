from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'industry', 'city', 'country', 'status', 'owner', 'created_at']
    list_filter = ['industry', 'status', 'country', 'owner']
    search_fields = ['name', 'website', 'email', 'phone', 'city', 'state', 'country', 'description']
