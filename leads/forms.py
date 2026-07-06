from django import forms
from .models import Lead


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'lead_name', 'company', 'contact_person', 'email', 'phone',
            'status', 'priority', 'source', 'expected_revenue',
            'assigned_user', 'notes',
        ]
        widgets = {
            'lead_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter lead name',
                'required': True,
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company name',
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Contact person name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control',
            }),
            'source': forms.Select(attrs={
                'class': 'form-control',
            }),
            'expected_revenue': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'assigned_user': forms.Select(attrs={
                'class': 'form-control',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add notes about this lead...',
                'rows': 4,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_user'].queryset = self.fields['assigned_user'].queryset.filter(
            is_active=True
        )
        self.fields['assigned_user'].required = False
        if 'assigned_user' in self.fields:
            self.fields['assigned_user'].label_from_instance = lambda u: u.get_full_name() or u.email

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Lead.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A lead with this email already exists.')
        return email
