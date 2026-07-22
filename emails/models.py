import uuid
from django.db import models
from django.conf import settings


class SMTPConfig(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='smtp_config',
    )
    host = models.CharField(max_length=255, default='smtp.gmail.com')
    port = models.PositiveIntegerField(default=587)
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    username = models.EmailField(max_length=255)
    password = models.CharField(max_length=255)
    sender_name = models.CharField(max_length=255, blank=True,
                                   help_text='Display name for outgoing emails')
    sender_email = models.EmailField(max_length=255, blank=True,
                                     help_text='If blank, username is used')
    is_verified = models.BooleanField(default=False)
    last_tested = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'SMTP Config'
        verbose_name_plural = 'SMTP Configs'

    def __str__(self):
        return f'{self.username} ({self.host})'

    @property
    def effective_sender_email(self):
        return self.sender_email or self.username


class EmailMessage(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('scheduled', 'Scheduled'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='emails',
    )
    smtp_config = models.ForeignKey(
        SMTPConfig,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emails',
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    to_emails = models.TextField(help_text='Comma-separated recipient emails')
    cc_emails = models.TextField(blank=True, help_text='Comma-separated CC emails')
    bcc_emails = models.TextField(blank=True, help_text='Comma-separated BCC emails')
    subject = models.CharField(max_length=998)
    body_html = models.TextField(blank=True)
    body_plain = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_time = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    is_draft = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    template = models.ForeignKey(
        'EmailTemplate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emails',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emails',
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emails',
    )
    deal = models.ForeignKey(
        'deals.Deal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emails',
    )
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='emails',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.subject} ({self.get_status_display()})'

    def recipient_list(self):
        return [e.strip() for e in self.to_emails.split(',') if e.strip()]

    def cc_list(self):
        return [e.strip() for e in self.cc_emails.split(',') if e.strip()]

    def bcc_list(self):
        return [e.strip() for e in self.bcc_emails.split(',') if e.strip()]


class EmailAttachment(models.Model):
    email = models.ForeignKey(
        EmailMessage,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='email_attachments/%Y/%m/%d/')
    original_filename = models.CharField(max_length=512)
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.original_filename


class EmailTemplate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_templates',
    )
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=998)
    body_html = models.TextField(blank=True)
    body_plain = models.TextField(blank=True)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name
