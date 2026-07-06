from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from contacts.models import Contact
from leads.models import Lead
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
        new_contacts_month = Contact.objects.filter(owner=user, created_at__gte=month_start).count()
        recent_contacts = Contact.objects.filter(owner=user)[:5]

        total_leads = Lead.objects.filter(owner=user).count()
        new_leads_month = Lead.objects.filter(owner=user, created_at__gte=month_start).count()
        won_leads = Lead.objects.filter(owner=user, status='Won').count()
        lost_leads = Lead.objects.filter(owner=user, status='Lost').count()
        recent_leads = Lead.objects.filter(owner=user)[:5]

        context['total_contacts'] = total_contacts
        context['new_contacts_month'] = new_contacts_month
        context['recent_contacts'] = recent_contacts
        context['total_leads'] = total_leads
        context['new_leads_month'] = new_leads_month
        context['won_leads'] = won_leads
        context['lost_leads'] = lost_leads
        context['recent_leads'] = recent_leads
        return context
