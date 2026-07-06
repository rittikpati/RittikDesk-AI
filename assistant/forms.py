from django import forms


class MessageForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'chat-input',
            'placeholder': 'Ask me anything...',
            'rows': 1,
            'autocomplete': 'off',
        }),
        required=True,
    )

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if not message:
            raise forms.ValidationError('Message cannot be empty.')
        return message
