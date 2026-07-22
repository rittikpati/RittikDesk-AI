from django.db import models
from django.conf import settings


class Lead(models.Model):
    STATUS_CHOICES = [
        ('New', 'New'),
        ('Contacted', 'Contacted'),
        ('Qualified', 'Qualified'),
        ('Proposal Sent', 'Proposal Sent'),
        ('Negotiation', 'Negotiation'),
        ('Won', 'Won'),
        ('Lost', 'Lost'),
    ]
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    SOURCE_CHOICES = [
        ('Website', 'Website'),
        ('Referral', 'Referral'),
        ('LinkedIn', 'LinkedIn'),
        ('Facebook', 'Facebook'),
        ('Instagram', 'Instagram'),
        ('Cold Email', 'Cold Email'),
        ('Event', 'Event'),
        ('Other', 'Other'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leads',
    )
    lead_name = models.CharField(max_length=255)
    organization = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='leads',
    )
    company = models.CharField(max_length=255, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='Website')
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='assigned_leads',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.lead_name
