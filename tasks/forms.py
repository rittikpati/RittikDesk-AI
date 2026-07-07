from django import forms
from django.db.models import Q
from .models import Task


class TaskForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['contact'].queryset = user.contacts.all()
            self.fields['lead'].queryset = user.leads.all()

    class Meta:
        model = Task
        fields = ['title', 'description', 'due_date', 'due_time', 'priority', 'status', 'contact', 'lead']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter task title',
                'required': True,
                'maxlength': 255,
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Add description...',
                'rows': 4,
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'due_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time',
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control',
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
            }),
            'contact': forms.Select(attrs={
                'class': 'form-control',
            }),
            'lead': forms.Select(attrs={
                'class': 'form-control',
            }),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError('Title is required.')
        if len(title) > 255:
            raise forms.ValidationError('Title must be 255 characters or fewer.')
        return title
