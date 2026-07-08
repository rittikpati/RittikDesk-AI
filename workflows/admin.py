from django.contrib import admin

from .models import Workflow, WorkflowAction, WorkflowSchedule, WorkflowExecutionLog, Notification


class WorkflowActionInline(admin.TabularInline):
    model = WorkflowAction
    extra = 1


class WorkflowScheduleInline(admin.TabularInline):
    model = WorkflowSchedule
    extra = 0


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'trigger_type', 'is_active', 'created_at']
    list_filter = ['is_active', 'trigger_type']
    search_fields = ['name', 'owner__email']
    inlines = [WorkflowActionInline, WorkflowScheduleInline]


@admin.register(WorkflowExecutionLog)
class WorkflowExecutionLogAdmin(admin.ModelAdmin):
    list_display = ['workflow', 'trigger_type', 'status', 'started_at']
    list_filter = ['status']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'is_read', 'created_at']
    list_filter = ['is_read']
