from django import forms
from .models import Contact


class ContactForm(forms.ModelForm):
    TAG_OPTIONS = ['Lead', 'Client', 'VIP', 'Partner']

    tag_choices = forms.MultipleChoiceField(
        choices=[(t, t) for t in TAG_OPTIONS],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Quick Tags',
    )

    class Meta:
        model = Contact
        fields = ['full_name', 'email', 'phone', 'company', 'job_title', 'tags', 'notes', 'profile_image']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter full name',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+1 (555) 000-0000',
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company name',
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Job title',
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Custom tags (comma-separated)',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add notes about this contact...',
                'rows': 4,
            }),
            'profile_image': forms.FileInput(attrs={
                'class': 'form-control',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.tags:
            existing = [t.strip() for t in self.instance.tags.split(',') if t.strip()]
            self.fields['tag_choices'].initial = [t for t in existing if t in self.TAG_OPTIONS]
            custom = [t for t in existing if t not in self.TAG_OPTIONS]
            self.initial['tags'] = ', '.join(custom)

    def clean(self):
        cleaned = super().clean()
        tag_choices = cleaned.get('tag_choices', [])
        custom_tags = cleaned.get('tags', '')
        custom_list = [t.strip() for t in custom_tags.split(',') if t.strip()]
        all_tags = list(tag_choices) + custom_list
        cleaned['tags'] = ', '.join(all_tags)
        return cleaned

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Contact.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A contact with this email already exists.')
        return email
