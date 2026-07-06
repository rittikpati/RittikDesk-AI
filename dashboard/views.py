from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from contacts.models import Contact
from django.utils import timezone
from datetime import timedelta


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        user = self.request.user

        total_contacts = Contact.objects.filter(owner=user).count()
        new_this_month = Contact.objects.filter(owner=user, created_at__gte=month_start).count()
        recent_contacts = Contact.objects.filter(owner=user)[:5]

        context['total_contacts'] = total_contacts
        context['new_contacts_month'] = new_this_month
        context['recent_contacts'] = recent_contacts
        return context
