from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView
from django.contrib.auth.views import PasswordResetDoneView, PasswordResetConfirmView
from django.contrib.auth.views import PasswordResetCompleteView
from .forms import CustomUserCreationForm, ProfileUpdateForm
from .models import CustomUser


class RegisterView(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Account'
        return context


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Sign In'
        return context


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('core:landing')


class ProfileView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = 'registration/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'My Profile'
        return context


class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.html'
    success_url = reverse_lazy('accounts:password_reset_done')


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'registration/password_reset_complete.html'
