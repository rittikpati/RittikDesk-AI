from django.contrib import admin
from .models import SMTPConfig, EmailMessage, EmailAttachment, EmailTemplate


@admin.register(SMTPConfig)
class SMTPConfigAdmin(admin.ModelAdmin):
    list_display = ['username', 'host', 'port', 'is_verified', 'owner', 'created_at']
    search_fields = ['username', 'host']


@admin.register(EmailMessage)
class EmailMessageAdmin(admin.ModelAdmin):
    list_display = ['subject', 'to_emails', 'status', 'priority', 'owner', 'created_at']
    list_filter = ['status', 'priority', 'is_draft']
    search_fields = ['subject', 'to_emails']


@admin.register(EmailAttachment)
class EmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'email', 'file_size', 'created_at']


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'subject', 'owner', 'is_shared', 'created_at']
    search_fields = ['name', 'subject']
