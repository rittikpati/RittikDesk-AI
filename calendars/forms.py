from django import forms
from calendars.models import Event

class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['contact'].queryset = user.contacts.all()
            self.fields['lead'].queryset = user.leads.all()
            self.fields['task'].queryset = user.tasks.all()

    class Meta:
        model = Event
        fields = [
            'title', 'description', 'start_date', 'start_time', 'end_time',
            'event_type', 'status', 'location', 'meeting_link',
            'contact', 'lead', 'task',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter event title',
                'required': True,
                'maxlength': 255,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add description...',
                'rows': 4,
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'event_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter location',
                'maxlength': 255,
            }),
            'meeting_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://meet.google.com/...',
            }),
            'contact': forms.Select(attrs={'class': 'form-control'}),
            'lead': forms.Select(attrs={'class': 'form-control'}),
            'task': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError('Title is required.')
        if len(title) > 255:
            raise forms.ValidationError('Title must be 255 characters or fewer.')
        return title
