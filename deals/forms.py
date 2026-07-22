from django import forms
from .models import Deal


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            'deal_name', 'company', 'contact', 'lead',
            'value', 'currency', 'stage', 'probability', 'expected_close_date',
            'source', 'priority', 'description', 'notes',
        ]
        widgets = {
            'deal_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter deal name',
                'required': True,
            }),
            'company': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Company name',
            }),
            'contact': forms.Select(attrs={'class': 'form-control'}),
            'lead': forms.Select(attrs={'class': 'form-control'}),
            'value': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
            }),
            'currency': forms.Select(attrs={'class': 'form-control'}),
            'stage': forms.Select(attrs={'class': 'form-control'}),
            'probability': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0',
                'min': '0',
                'max': '100',
            }),
            'expected_close_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
            }),
            'source': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Deal description...',
                'rows': 3,
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Internal notes...',
                'rows': 3,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['contact'].required = False
        self.fields['lead'].required = False
        self.fields['value'].required = False
        self.fields['expected_close_date'].required = False
        self.fields['currency'].required = False
        self.fields['source'].required = False
        self.fields['priority'].required = False

    def clean_deal_name(self):
        name = self.cleaned_data.get('deal_name')
        if name and Deal.objects.filter(deal_name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A deal with this name already exists.')
        return name

    def clean_probability(self):
        prob = self.cleaned_data.get('probability')
        if prob is not None and (prob < 0 or prob > 100):
            raise forms.ValidationError('Probability must be between 0 and 100.')
        return prob
