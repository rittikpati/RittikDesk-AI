import json
import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

TRIGGER_CHOICES = [
    ('contact_created', 'Contact Created'),
    ('contact_updated', 'Contact Updated'),
    ('lead_created', 'Lead Created'),
    ('lead_updated', 'Lead Updated'),
    ('lead_qualified', 'Lead Status → Qualified'),
    ('lead_won', 'Lead Status → Won'),
    ('lead_lost', 'Lead Status → Lost'),
    ('task_created', 'Task Created'),
    ('task_completed', 'Task Completed'),
    ('task_overdue', 'Task Overdue'),
    ('meeting_created', 'Meeting Created'),
    ('meeting_finished', 'Meeting Finished'),
    ('meeting_reminder', 'Meeting Reminder'),
    ('campaign_created', 'Campaign Created'),
    ('campaign_started', 'Campaign Started'),
    ('campaign_completed', 'Campaign Completed'),
    ('scheduled_daily', 'Scheduled — Daily'),
    ('scheduled_weekly', 'Scheduled — Weekly'),
    ('scheduled_monthly', 'Scheduled — Monthly'),
]

ACTION_CHOICES = [
    ('create_task', 'Create Task'),
    ('update_task', 'Update Task'),
    ('send_email', 'Send Email'),
    ('create_event', 'Create Calendar Event'),
    ('assign_lead', 'Assign Lead'),
    ('change_lead_status', 'Change Lead Status'),
    ('add_tag', 'Add Tag'),
    ('remove_tag', 'Remove Tag'),
    ('ai_summary', 'Generate AI Summary'),
    ('ai_email', 'Generate AI Email'),
    ('ai_followup', 'Generate AI Follow-up'),
    ('create_notification', 'Create Notification'),
    ('send_notification', 'Send Notification'),
    ('create_contact', 'Create Contact'),
    ('create_lead', 'Create Lead'),
    ('create_calendar_event', 'Create Calendar Event'),
    ('webhook', 'Webhook (Custom)'),
]


class Workflow(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='workflows',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    trigger_type = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class WorkflowAction(models.Model):
    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name='actions',
    )
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)
    order = models.IntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f'{self.get_action_type_display()} (#{self.order})'


class WorkflowSchedule(models.Model):
    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name='schedules',
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
    )
    time = models.TimeField()
    day_of_week = models.IntegerField(
        null=True, blank=True,
        choices=[
            (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
            (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'),
            (6, 'Sunday'),
        ],
        help_text='Required for weekly schedules.',
    )
    day_of_month = models.IntegerField(
        null=True, blank=True,
        help_text='Required for monthly schedules (1-31).',
    )
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['schedule_type', 'time']


class WorkflowExecutionLog(models.Model):
    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name='execution_logs',
    )
    trigger_type = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20,
        choices=[('running', 'Running'), ('success', 'Success'),
                 ('failed', 'Failed'), ('partial', 'Partial')],
        default='running',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.workflow.name} — {self.get_status_display()}'


PRIORITY_CHOICES = [
    ('low', 'Low'),
    ('medium', 'Medium'),
    ('high', 'High'),
]


class Notification(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
