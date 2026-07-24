from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('activity_type', 'user', 'module', 'title', 'timestamp')
    list_filter = ('module', 'activity_type')
    search_fields = ('title', 'description', 'object_repr')
    readonly_fields = ('user', 'activity_type', 'title', 'description',
                       'module', 'icon', 'color', 'object_id', 'object_repr',
                       'detail_url', 'timestamp')
