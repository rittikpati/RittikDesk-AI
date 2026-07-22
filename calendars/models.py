from django.db import models
from django.conf import settings

class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('meeting', 'Meeting'),
        ('call', 'Call'),
        ('reminder', 'Reminder'),
        ('personal', 'Personal'),
    ]
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='events',
    )
    organization = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='events',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='events',
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='events',
    )
    task = models.ForeignKey(
        'tasks.Task',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='events',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='meeting')
    location = models.CharField(max_length=255, blank=True)
    meeting_link = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date', 'start_time']

    def __str__(self):
        return self.title
