from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from contacts.models import Contact
from leads.models import Lead
from campaigns.models import Campaign
from tasks.models import Task
from calendars.models import Event
from django.utils import timezone
from datetime import timedelta
from .services import DashboardIntelligenceService


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

        # ── AI Dashboard Intelligence ──────────────────────────────
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
