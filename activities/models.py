from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    MODULE_CHOICES = [
        ('contacts', 'Contacts'),
        ('companies', 'Companies'),
        ('leads', 'Leads'),
        ('deals', 'Deals'),
        ('tasks', 'Tasks'),
        ('campaigns', 'Campaigns'),
        ('emails', 'Emails'),
        ('calendar', 'Calendar'),
        ('workflows', 'Workflows'),
        ('ai', 'AI Assistant'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_logs',
    )
    activity_type = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default='')
    module = models.CharField(max_length=50, choices=MODULE_CHOICES, default='system')
    icon = models.CharField(max_length=50, default='fa-info-circle')
    color = models.CharField(max_length=20, default='#6C63FF')
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=255, blank=True, default='')
    detail_url = models.CharField(max_length=500, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['user', 'module']),
            models.Index(fields=['user', 'activity_type']),
        ]

    def __str__(self):
        return f'{self.activity_type} by {self.user} at {self.timestamp}'
