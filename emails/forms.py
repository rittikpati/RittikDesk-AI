from django import forms
from .models import SMTPConfig, EmailMessage, EmailTemplate


class SMTPConfigForm(forms.ModelForm):
    encryption = forms.ChoiceField(
        choices=[('tls', 'TLS'), ('ssl', 'SSL'), ('none', 'None')],
        widget=forms.RadioSelect(attrs={'class': 'smtp-encryption-radio'}),
        initial='tls',
        label='Encryption',
    )

    class Meta:
        model = SMTPConfig
        fields = ['host', 'port', 'encryption', 'username', 'password',
                  'sender_name', 'sender_email']
        widgets = {
            'host': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'smtp.gmail.com',
                'id': 'smtp_host',
            }),
            'port': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': '587',
                'id': 'smtp_port',
            }),
            'username': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com',
                'id': 'smtp_username',
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'App password or SMTP password',
                'id': 'smtp_password',
                'autocomplete': 'off',
            }),
            'sender_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your display name',
                'id': 'smtp_sender_name',
            }),
            'sender_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com',
                'id': 'smtp_sender_email',
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        if instance:
            if instance.use_ssl:
                self.initial['encryption'] = 'ssl'
            elif instance.use_tls:
                self.initial['encryption'] = 'tls'
            else:
                self.initial['encryption'] = 'none'
            self.fields['password'].required = False
            self.fields['password'].widget.attrs['placeholder'] = 'Leave blank to keep current'

        if user and not instance:
            self.fields['sender_name'].initial = user.get_full_name() or user.username
            self.fields['sender_email'].initial = user.email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and self.instance and self.instance.pk:
            return self.instance.password
        return password

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('encryption'):
            instance.use_tls = (self.cleaned_data['encryption'] == 'tls')
            instance.use_ssl = (self.cleaned_data['encryption'] == 'ssl')
        if commit:
            instance.save()
            self._save_m2m()
        return instance

    def clean(self):
        cleaned = super().clean()
        encryption = cleaned.get('encryption')
        cleaned['use_tls'] = (encryption == 'tls')
        cleaned['use_ssl'] = (encryption == 'ssl')
        return cleaned


class ComposeEmailForm(forms.ModelForm):
    class Meta:
        model = EmailMessage
        fields = ['to_emails', 'cc_emails', 'bcc_emails', 'subject',
                  'body_html', 'body_plain', 'priority', 'scheduled_time',
                  'contact', 'lead', 'deal', 'company']
        widgets = {
            'to_emails': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'recipient@example.com',
                'required': True,
            }),
            'cc_emails': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'cc@example.com',
            }),
            'bcc_emails': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'bcc@example.com',
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Email subject',
                'required': True,
            }),
            'body_html': forms.Textarea(attrs={
                'class': 'form-control editor-html', 'rows': 15,
                'placeholder': 'Write your email...',
            }),
            'body_plain': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 10,
                'placeholder': 'Plain text version...',
            }),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_time': forms.DateTimeInput(attrs={
                'class': 'form-control', 'type': 'datetime-local',
            }),
            'contact': forms.Select(attrs={'class': 'form-control'}),
            'lead': forms.Select(attrs={'class': 'form-control'}),
            'deal': forms.Select(attrs={'class': 'form-control'}),
            'company': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['contact'].queryset = user.contacts.all()
            self.fields['lead'].queryset = user.leads.all()
            self.fields['deal'].queryset = user.deals.all()
            self.fields['company'].queryset = user.companies.all()
            self.fields['contact'].required = False
            self.fields['lead'].required = False
            self.fields['deal'].required = False
            self.fields['company'].required = False

    def clean_to_emails(self):
        value = self.cleaned_data.get('to_emails', '')
        emails = [e.strip() for e in value.split(',') if e.strip()]
        if not emails:
            raise forms.ValidationError('At least one recipient is required.')
        for email in emails:
            if '@' not in email:
                raise forms.ValidationError(f'Invalid email: {email}')
        return value


class EmailTemplateForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = ['name', 'subject', 'body_html', 'body_plain', 'is_shared']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Template name',
                'required': True,
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Email subject',
                'required': True,
            }),
            'body_html': forms.Textarea(attrs={
                'class': 'form-control editor-html', 'rows': 15,
            }),
            'body_plain': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 10,
            }),
            'is_shared': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
