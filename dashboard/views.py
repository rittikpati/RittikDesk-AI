from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta

from contacts.models import Contact
from companies.models import Company
from leads.models import Lead
from deals.models import Deal
from tasks.models import Task
from campaigns.models import Campaign
from emails.models import EmailMessage
from calendars.models import Event
from .services import DashboardIntelligenceService


LIMIT_PER_MODULE = 5


class GlobalSearchView(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get('q', '').strip()
        if len(q) < 2:
            return JsonResponse({'results': {}, 'query': q})

        user = request.user
        results = {}

        contacts = Contact.objects.filter(
            Q(owner=user) & (Q(full_name__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q) | Q(phone__icontains=q))
        ).order_by('full_name')[:LIMIT_PER_MODULE]
        results['contacts'] = [
            {
                'id': c.pk,
                'name': c.full_name,
                'subtitle': c.email or c.company or '',
                'icon': 'fas fa-user',
                'detail_url': f'/contacts/{c.pk}/',
            }
            for c in contacts
        ]

        companies = Company.objects.filter(
            Q(owner=user) & (Q(name__icontains=q) | Q(email__icontains=q) | Q(industry__icontains=q) | Q(city__icontains=q))
        ).order_by('name')[:LIMIT_PER_MODULE]
        results['companies'] = [
            {
                'id': c.pk,
                'name': c.name,
                'subtitle': c.industry or c.email or '',
                'icon': 'fas fa-building',
                'detail_url': f'/companies/{c.pk}/',
            }
            for c in companies
        ]

        leads = Lead.objects.filter(
            Q(owner=user) & (Q(lead_name__icontains=q) | Q(email__icontains=q) | Q(company__icontains=q))
        ).order_by('lead_name')[:LIMIT_PER_MODULE]
        results['leads'] = [
            {
                'id': l.pk,
                'name': l.lead_name,
                'subtitle': l.email or l.company or '',
                'icon': 'fas fa-tag',
                'detail_url': f'/leads/{l.pk}/',
            }
            for l in leads
        ]

        deals = Deal.objects.filter(
            Q(owner=user) & (Q(deal_name__icontains=q) | Q(company__icontains=q))
        ).order_by('deal_name')[:LIMIT_PER_MODULE]
        results['deals'] = [
            {
                'id': d.pk,
                'name': d.deal_name,
                'subtitle': d.company or '',
                'icon': 'fas fa-handshake',
                'detail_url': f'/deals/{d.pk}/',
            }
            for d in deals
        ]

        tasks = Task.objects.filter(
            Q(owner=user) & (Q(title__icontains=q) | Q(description__icontains=q))
        ).order_by('title')[:LIMIT_PER_MODULE]
        results['tasks'] = [
            {
                'id': t.pk,
                'name': t.title,
                'subtitle': t.due_date.strftime('%b %d, %Y') if t.due_date else '',
                'icon': 'fas fa-check-circle',
                'detail_url': f'/tasks/{t.pk}/',
            }
            for t in tasks
        ]

        campaigns = Campaign.objects.filter(
            Q(owner=user) & (Q(name__icontains=q) | Q(subject__icontains=q))
        ).order_by('name')[:LIMIT_PER_MODULE]
        results['campaigns'] = [
            {
                'id': c.pk,
                'name': c.name,
                'subtitle': c.subject or '',
                'icon': 'fas fa-bullhorn',
                'detail_url': f'/campaigns/{c.pk}/',
            }
            for c in campaigns
        ]

        emails = EmailMessage.objects.filter(
            Q(owner=user) & (Q(subject__icontains=q) | Q(to_emails__icontains=q) | Q(body_plain__icontains=q))
        ).order_by('-sent_at')[:LIMIT_PER_MODULE]
        results['emails'] = [
            {
                'id': e.pk,
                'name': e.subject,
                'subtitle': e.to_emails or '',
                'icon': 'fas fa-envelope',
                'detail_url': f'/emails/{e.pk}/',
            }
            for e in emails
        ]

        return JsonResponse({'results': results, 'query': q})


class DashboardHomeView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        today = now.date()
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

        total_campaigns = Campaign.objects.filter(owner=user).count()
        draft_campaigns = Campaign.objects.filter(owner=user, status='Draft').count()
        scheduled_campaigns = Campaign.objects.filter(owner=user, status='Scheduled').count()
        sent_campaigns = Campaign.objects.filter(owner=user, status='Sent').count()
        recent_campaigns = Campaign.objects.filter(owner=user)[:5]

        tasks_qs = Task.objects.filter(owner=user)
        total_tasks = tasks_qs.count()
        pending_tasks = tasks_qs.filter(status='pending').count()
        in_progress_tasks = tasks_qs.filter(status='in_progress').count()
        completed_tasks = tasks_qs.filter(status='completed').count()
        overdue_tasks = tasks_qs.filter(due_date__lt=today, status='pending').count()
        recent_tasks = tasks_qs.order_by('-created_at')[:5]

        total_events = Event.objects.filter(owner=user).count()
        today_events = Event.objects.filter(owner=user, start_date=today).count()
        upcoming_events = Event.objects.filter(owner=user, start_date__gte=today, status='scheduled').order_by('start_date', 'start_time')[:5]

        context['total_contacts'] = total_contacts
        context['new_contacts_month'] = new_contacts_month
        context['recent_contacts'] = recent_contacts
        context['total_leads'] = total_leads
        context['new_leads_month'] = new_leads_month
        context['won_leads'] = won_leads
        context['lost_leads'] = lost_leads
        context['recent_leads'] = recent_leads
        context['total_campaigns'] = total_campaigns
        context['draft_campaigns'] = draft_campaigns
        context['scheduled_campaigns'] = scheduled_campaigns
        context['sent_campaigns'] = sent_campaigns
        context['recent_campaigns'] = recent_campaigns
        context['total_tasks'] = total_tasks
        context['pending_tasks'] = pending_tasks
        context['in_progress_tasks'] = in_progress_tasks
        context['completed_tasks'] = completed_tasks
        context['overdue_tasks'] = overdue_tasks
        context['recent_tasks'] = recent_tasks
        context['total_events'] = total_events
        context['today_events'] = today_events
        context['upcoming_events'] = upcoming_events
        context['today'] = today

        deal_qs = Deal.objects.filter(owner=user)
        context['total_deals'] = deal_qs.count()
        context['won_deals'] = deal_qs.filter(stage='Won').count()
        context['lost_deals'] = deal_qs.filter(stage='Lost').count()
        context['open_deals'] = deal_qs.exclude(stage__in=['Won', 'Lost']).count()
        context['deal_revenue'] = deal_qs.filter(stage='Won').aggregate(Sum('value'))['value__sum'] or 0
        context['deal_potential'] = deal_qs.exclude(stage__in=['Won', 'Lost']).aggregate(Sum('value'))['value__sum'] or 0

        company_qs = Company.objects.filter(owner=user)
        context['total_companies'] = company_qs.count()
        context['active_companies'] = company_qs.filter(status='Active').count()
        context['inactive_companies'] = company_qs.filter(status='Inactive').count()
        context['top_industries'] = company_qs.exclude(industry='').values('industry').annotate(count=Count('id')).order_by('-count')[:5]

        email_qs = EmailMessage.objects.filter(owner=user)
        context['total_emails'] = email_qs.count()
        context['sent_emails'] = email_qs.filter(status='sent').count()
        context['draft_emails'] = email_qs.filter(status='draft', is_draft=True).count()
        context['failed_emails'] = email_qs.filter(status='failed').count()

        svc = DashboardIntelligenceService(user)

        context.update(svc.get_card_stats())
        context['ai_recent_activity'] = svc.get_recent_activity()
        context['ai_upcoming_events'] = svc.get_upcoming_events()
        context['ai_insights'] = svc.get_ai_insights()
        context['ai_lead_funnel'] = svc.get_lead_funnel()
        context['ai_task_summary'] = svc.get_task_summary()
        context['ai_campaign_summary'] = svc.get_campaign_summary()
        context['ai_workflow_summary'] = svc.get_workflow_summary()
        context['ai_notification_summary'] = svc.get_notification_summary()

        return context
