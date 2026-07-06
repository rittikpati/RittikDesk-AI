from django import forms
from .models import Campaign


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'subject', 'body', 'status', 'scheduled_at']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter campaign name',
                'required': True,
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email subject line',
                'required': True,
            }),
            'body': forms.Textarea(attrs={
                'class': 'form-control campaign-body-editor',
                'placeholder': 'Write your email content here...',
                'rows': 12,
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'scheduled_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
        }

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        scheduled_at = cleaned.get('scheduled_at')

        if status == 'Scheduled' and not scheduled_at:
            raise forms.ValidationError('Scheduled date and time is required when status is "Scheduled".')

        if scheduled_at and status == 'Draft':
            cleaned['status'] = 'Scheduled'

        return cleaned
