from django import forms

from .models import Workflow, WorkflowAction
from .models import TRIGGER_CHOICES


class WorkflowForm(forms.ModelForm):
    class Meta:
        model = Workflow
        fields = ['name', 'description', 'trigger_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Welcome Email Flow',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what this workflow does...',
            }),
            'trigger_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class WorkflowActionForm(forms.ModelForm):
    class Meta:
        model = WorkflowAction
        fields = ['action_type', 'order', 'config']
        widgets = {
            'action_type': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
            }),
            'config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': '{"title": "Follow up with {{ object.full_name }}"}',
            }),
        }


class WorkflowActionFormSet(forms.BaseInlineFormSet):
    def clean(self):
        if any(self.errors):
            return
        orders = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                orders.append(form.cleaned_data['order'])
        if len(orders) != len(set(orders)):
            raise forms.ValidationError('Each action must have a unique order number.')
