from django.db import models
from django.conf import settings


class Deal(models.Model):
    STAGE_CHOICES = [
        ('New', 'New'),
        ('Qualified', 'Qualified'),
        ('Proposal Sent', 'Proposal Sent'),
        ('Negotiation', 'Negotiation'),
        ('Contract Review', 'Contract Review'),
        ('Won', 'Won'),
        ('Lost', 'Lost'),
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
    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Urgent', 'Urgent'),
    ]
    CURRENCY_CHOICES = [
        ('USD', 'USD'),
        ('EUR', 'EUR'),
        ('GBP', 'GBP'),
        ('INR', 'INR'),
        ('CAD', 'CAD'),
        ('AUD', 'AUD'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='deals',
    )
    deal_name = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    organization = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='deals',
    )
    contact = models.ForeignKey(
        'contacts.Contact',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='deals',
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='deals',
    )
    value = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD')
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='New')
    probability = models.IntegerField(default=0, help_text='Probability percentage (0–100)')
    expected_close_date = models.DateField(blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='Website')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='Open', choices=[
        ('Open', 'Open'),
        ('Won', 'Won'),
        ('Lost', 'Lost'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.deal_name

    def update_status_from_stage(self):
        if self.stage == 'Won':
            self.status = 'Won'
        elif self.stage == 'Lost':
            self.status = 'Lost'
        else:
            self.status = 'Open'

    def save(self, *args, **kwargs):
        self.update_status_from_stage()
        super().save(*args, **kwargs)
