import csv
import io
from django import forms
from .models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name', 'industry', 'website', 'email', 'phone',
            'address', 'city', 'state', 'country', 'postal_code',
            'employees', 'annual_revenue', 'company_size',
            'linkedin_url', 'description', 'status',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter company name',
                'required': True,
            }),
            'industry': forms.Select(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'company@example.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Street address',
                'rows': 2,
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City',
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'State / Province',
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country',
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal / Zip code',
            }),
            'employees': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of employees',
                'min': '0',
            }),
            'annual_revenue': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Annual revenue',
                'step': '0.01',
                'min': '0',
            }),
            'company_size': forms.Select(attrs={'class': 'form-control'}),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://linkedin.com/company/...',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Company description...',
                'rows': 3,
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['industry'].required = False
        self.fields['website'].required = False
        self.fields['email'].required = False
        self.fields['phone'].required = False
        self.fields['address'].required = False
        self.fields['city'].required = False
        self.fields['state'].required = False
        self.fields['country'].required = False
        self.fields['postal_code'].required = False
        self.fields['employees'].required = False
        self.fields['annual_revenue'].required = False
        self.fields['company_size'].required = False
        self.fields['linkedin_url'].required = False
        self.fields['description'].required = False
        self.fields['status'].required = False

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            qs = Company.objects.filter(name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('A company with this name already exists.')
        return name


class CompanyImportForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with columns: name, industry, website, email, phone, city, state, country, employees, annual_revenue, description, status',
    )

    def clean_csv_file(self):
        file = self.cleaned_data.get('csv_file')
        if not file.name.endswith('.csv'):
            raise forms.ValidationError('Please upload a CSV file.')
        return file
