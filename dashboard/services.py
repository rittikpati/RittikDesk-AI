from django.utils import timezone


class DashboardIntelligenceService:
    """Collect all AI Dashboard Intelligence data for a given user.

    Every method filters strictly by ``owner=user`` — no cross-user data
    leakage.  Queries use ``.filter(…).count()`` for stats, and
    ``.order_by('-created_at')`` with a small limit for activity feeds;
    no N+1 queries are introduced.
    """

    def __init__(self, user):
        self.user = user
        self.now = timezone.now()
        self.today = self.now.date()

    # ------------------------------------------------------------------
    # Card stats
    # ------------------------------------------------------------------
    def get_card_stats(self):
        from contacts.models import Contact
        from leads.models import Lead
        from tasks.models import Task
        from calendars.models import Event
        from campaigns.models import Campaign
        from workflows.models import Workflow, Notification

        user = self.user
        return {
            'ai_total_contacts': Contact.objects.filter(owner=user).count(),
            'ai_total_leads': Lead.objects.filter(owner=user).count(),
            'ai_high_priority_leads': Lead.objects.filter(
                owner=user, priority__in=['High', 'Urgent']
            ).count(),
            'ai_converted_leads': Lead.objects.filter(
                owner=user, status='Won'
            ).count(),
            'ai_total_tasks': Task.objects.filter(owner=user).count(),
            'ai_completed_tasks': Task.objects.filter(
                owner=user, status='completed'
            ).count(),
            'ai_pending_tasks': Task.objects.filter(
                owner=user, status='pending'
            ).count(),
            'ai_today_meetings': Event.objects.filter(
                owner=user, start_date=self.today, event_type='meeting'
            ).count(),
            'ai_upcoming_meetings': Event.objects.filter(
                owner=user, start_date__gte=self.today, status='scheduled'
            ).count(),
            'ai_active_campaigns': Campaign.objects.filter(
                owner=user, status='Scheduled'
            ).count(),
            'ai_active_workflows': Workflow.objects.filter(
                owner=user, is_active=True
            ).count(),
            'ai_unread_notifications': Notification.objects.filter(
                owner=user, is_read=False
            ).count(),
            'ai_total_emails_sent': 0,
        }

    # ------------------------------------------------------------------
    # Recent activity (unified across 7 entity types)
    # ------------------------------------------------------------------
    def get_recent_activity(self, limit=10):
        from contacts.models import Contact
        from leads.models import Lead
        from campaigns.models import Campaign
        from tasks.models import Task
        from calendars.models import Event
        from workflows.models import WorkflowExecutionLog, Notification

        user = self.user
        activities = []

        for c in Contact.objects.filter(owner=user).order_by('-created_at')[:limit]:
            activities.append({
                'type': 'contact',
                'text': f'New contact <strong>{c.full_name}</strong> added',
                'time': c.created_at,
                'color': '#6C63FF',
                'icon': 'fa-user-plus',
                'url_name': 'contacts:detail',
                'url_pk': c.pk,
            })

        for l in Lead.objects.filter(owner=user).order_by('-created_at')[:limit]:
            activities.append({
                'type': 'lead',
                'text': f'Lead <strong>{l.lead_name}</strong> created — {l.status}',
                'time': l.created_at,
                'color': '#FFB800',
                'icon': 'fa-tag',
                'url_name': 'leads:detail',
                'url_pk': l.pk,
            })

        for c in Campaign.objects.filter(owner=user).order_by('-created_at')[:limit]:
            activities.append({
                'type': 'campaign',
                'text': f'Campaign <strong>{c.name}</strong> {c.status.lower()}',
                'time': c.created_at,
                'color': '#00D9A6',
                'icon': 'fa-bullhorn',
                'url_name': 'campaigns:detail',
                'url_pk': c.pk,
            })

        for t in Task.objects.filter(
            owner=user, status='completed'
        ).order_by('-updated_at')[:limit]:
            activities.append({
                'type': 'task',
                'text': f'Task <strong>{t.title}</strong> completed',
                'time': t.updated_at,
                'color': '#00D9A6',
                'icon': 'fa-check-circle',
                'url_name': 'tasks:detail',
                'url_pk': t.pk,
            })

        for e in Event.objects.filter(owner=user).order_by('-created_at')[:limit]:
            activities.append({
                'type': 'event',
                'text': f'Meeting <strong>{e.title}</strong> scheduled',
                'time': e.created_at,
                'color': '#00B4D8',
                'icon': 'fa-calendar-alt',
                'url_name': 'calendars:detail',
                'url_pk': e.pk,
            })

        for wl in WorkflowExecutionLog.objects.filter(
            workflow__owner=user
        ).select_related('workflow').order_by('-started_at')[:limit]:
            activities.append({
                'type': 'workflow',
                'text': f'Workflow <strong>{wl.workflow.name}</strong> executed — {wl.status}',
                'time': wl.started_at,
                'color': '#3699FF',
                'icon': 'fa-gears',
                'url_name': 'workflows:log_detail',
                'url_pk': wl.pk,
            })

        for n in Notification.objects.filter(owner=user).order_by('-created_at')[:limit]:
            activities.append({
                'type': 'notification',
                'text': f'<strong>{n.title}</strong>',
                'time': n.created_at,
                'color': '#FF6B6B',
                'icon': 'fa-bell',
                'url_name': 'workflows:notifications',
                'url_pk': None,
            })

        activities.sort(key=lambda x: x['time'], reverse=True)
        return activities[:limit]

    # ------------------------------------------------------------------
    # Upcoming events (with full metadata)
    # ------------------------------------------------------------------
    def get_upcoming_events(self, limit=5):
        from calendars.models import Event
        return list(Event.objects.filter(
            owner=self.user,
            start_date__gte=self.today,
            status='scheduled',
        ).order_by('start_date', 'start_time')[:limit])

    # ------------------------------------------------------------------
    # AI insights — generated from real CRM data, never fake
    # ------------------------------------------------------------------
    def get_ai_insights(self):
        from leads.models import Lead
        from tasks.models import Task
        from calendars.models import Event
        from workflows.models import Notification, Workflow

        user = self.user
        insights = []

        high_priority = Lead.objects.filter(
            owner=user, priority__in=['High', 'Urgent']
        ).count()
        if high_priority:
            insights.append(
                f"You have {high_priority} high-priority lead"
                f"{'s' if high_priority != 1 else ''} awaiting follow-up."
            )

        overdue = Task.objects.filter(
            owner=user, due_date__lt=self.today, status='pending'
        ).count()
        if overdue:
            insights.append(
                f"You have {overdue} overdue task{'s' if overdue != 1 else ''}"
                f" that need{'s' if overdue == 1 else ''} your attention."
            )

        today_meetings = Event.objects.filter(
            owner=user, start_date=self.today
        ).count()
        if today_meetings:
            insights.append(
                f"You have {today_meetings} meeting{'s' if today_meetings != 1 else ''}"
                f" scheduled today."
            )
        else:
            insights.append("No meeting scheduled today.")

        won = Lead.objects.filter(owner=user, status='Won').count()
        if won:
            insights.append(f"You've converted {won} lead{'s' if won != 1 else ''} — keep up the momentum!")

        unread = Notification.objects.filter(owner=user, is_read=False).count()
        if unread:
            insights.append(
                f"You have {unread} unread notification{'s' if unread != 1 else ''}."
            )

        pending = Task.objects.filter(owner=user, status='pending').count()
        if pending:
            insights.append(
                f"You have {pending} pending task{'s' if pending != 1 else ''}"
                f" to complete."
            )

        active_workflows = Workflow.objects.filter(owner=user, is_active=True).count()
        if active_workflows:
            insights.append(
                f"{active_workflows} workflow{'s' if active_workflows != 1 else ''}"
                f" {'are' if active_workflows != 1 else 'is'} actively running."
            )

        if not insights:
            insights.append("No data yet — start by adding contacts or leads.")

        return insights

    # ------------------------------------------------------------------
    # Lead funnel
    # ------------------------------------------------------------------
    def get_lead_funnel(self):
        from leads.models import Lead
        qs = Lead.objects.filter(owner=self.user)
        return {
            'new': qs.filter(status='New').count(),
            'contacted': qs.filter(status='Contacted').count(),
            'qualified': qs.filter(status='Qualified').count(),
            'proposal': qs.filter(status__in=['Proposal Sent', 'Negotiation']).count(),
            'won': qs.filter(status='Won').count(),
            'lost': qs.filter(status='Lost').count(),
        }

    # ------------------------------------------------------------------
    # Task summary
    # ------------------------------------------------------------------
    def get_task_summary(self):
        from tasks.models import Task
        qs = Task.objects.filter(owner=self.user)
        return {
            'completed': qs.filter(status='completed').count(),
            'pending': qs.filter(status='pending').count(),
            'overdue': qs.filter(
                due_date__lt=self.today, status='pending'
            ).count(),
            'today': qs.filter(due_date=self.today).count(),
        }

    # ------------------------------------------------------------------
    # Campaign summary
    # ------------------------------------------------------------------
    def get_campaign_summary(self):
        from campaigns.models import Campaign
        qs = Campaign.objects.filter(owner=self.user)
        return {
            'scheduled': qs.filter(status='Scheduled').count(),
            'sent': qs.filter(status='Sent').count(),
            'draft': qs.filter(status='Draft').count(),
        }

    # ------------------------------------------------------------------
    # Workflow summary
    # ------------------------------------------------------------------
    def get_workflow_summary(self):
        from workflows.models import Workflow, WorkflowExecutionLog
        user = self.user
        total = Workflow.objects.filter(owner=user).count()
        active = Workflow.objects.filter(owner=user, is_active=True).count()
        disabled = total - active
        failed = WorkflowExecutionLog.objects.filter(
            workflow__owner=user, status='failed'
        ).values('workflow').distinct().count()
        return {
            'active': active,
            'disabled': disabled,
            'failed': failed,
        }

    # ------------------------------------------------------------------
    # Notification summary
    # ------------------------------------------------------------------
    def get_notification_summary(self):
        from workflows.models import Notification
        qs = Notification.objects.filter(owner=self.user)
        return {
            'unread': qs.filter(is_read=False).count(),
            'read': qs.filter(is_read=True).count(),
        }
