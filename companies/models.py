from django.db import models
from django.conf import settings


class Company(models.Model):
    INDUSTRY_CHOICES = [
        ('Technology', 'Technology'),
        ('Healthcare', 'Healthcare'),
        ('Finance', 'Finance'),
        ('Education', 'Education'),
        ('Manufacturing', 'Manufacturing'),
        ('Retail', 'Retail'),
        ('Real Estate', 'Real Estate'),
        ('Consulting', 'Consulting'),
        ('Media', 'Media'),
        ('Telecommunications', 'Telecommunications'),
        ('Transportation', 'Transportation'),
        ('Energy', 'Energy'),
        ('Hospitality', 'Hospitality'),
        ('Agriculture', 'Agriculture'),
        ('Other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Lead', 'Lead'),
        ('Prospect', 'Prospect'),
        ('Customer', 'Customer'),
        ('Partner', 'Partner'),
        ('Former', 'Former'),
    ]
    SIZE_CHOICES = [
        ('1-10', '1-10'),
        ('11-50', '11-50'),
        ('51-200', '51-200'),
        ('201-500', '201-500'),
        ('501-1000', '501-1000'),
        ('1001-5000', '1001-5000'),
        ('5001-10000', '5001-10000'),
        ('10000+', '10000+'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='companies',
    )
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='companies/logos/', blank=True, null=True)
    industry = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, blank=True, default='Other')
    website = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    employees = models.IntegerField(blank=True, null=True, help_text='Number of employees')
    annual_revenue = models.DecimalField(max_digits=16, decimal_places=2, blank=True, null=True)
    company_size = models.CharField(max_length=20, choices=SIZE_CHOICES, blank=True, default='1-10')
    linkedin_url = models.URLField(blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'companies'

    def __str__(self):
        return self.name
