from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Enter your email'
    }))
    username = forms.CharField(required=True, widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Choose a username'
    }))
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Create a password'
    }))
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Confirm your password'
    }))

    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'password1', 'password2')


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'phone', 'company', 'avatar')


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'phone', 'company', 'avatar')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1234567890'}),
            'company': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your company'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }
