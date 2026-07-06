from django.db import models
from django.conf import settings


class Contact(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contacts',
    )
    full_name = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    job_title = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text='Comma-separated tags')
    notes = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to='contacts/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.full_name

    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]
