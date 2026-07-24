import logging
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

CRM_KEYWORDS = frozenset({
    'task', 'meeting', 'contact', 'lead', 'campaign',
    'event', 'calendar', 'crm', 'pipeline', 'deal',
    'customer', 'client', 'prospect', 'follow.up',
    'overdue', 'pending', 'today', 'tomorrow', 'week',
    'revenue', 'value', 'email', 'call', 'schedule',
    'appointment', 'meet', 'deadline', 'due',
    'active', 'open', 'new', 'recent', 'upcoming',
    'highest', 'most', 'count', 'show', 'list',
    'activity', 'activities', 'timeline', 'history', 'log',
    'completed', 'done', 'finished',
})


class CRMContextService:
    """Collects CRM data scoped to a single user for AI context."""

    def __init__(self, user):
        self.user = user

    def is_crm_query(self, text):
        """Return True if the text likely relates to CRM data."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in CRM_KEYWORDS)

    def get_context(self):
        """Build a CRM data summary string for the current user."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        week_end = today + timedelta(days=7)
        thirty_days_ago = timezone.now() - timedelta(days=30)

        parts = ['Current CRM Data', '-' * 40]

        # ── Tasks ──
        t = self.user.tasks
        task_stats = t.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            in_progress=Count('id', filter=Q(status='in_progress')),
            completed=Count('id', filter=Q(status='completed')),
            overdue=Count('id', filter=Q(status='pending', due_date__lt=today)),
            today_count=Count('id', filter=Q(due_date=today)),
        )
        parts.append(
            'Tasks\n'
            f'  Pending: {task_stats["pending"]} | '
            f'In Progress: {task_stats["in_progress"]} | '
            f'Completed: {task_stats["completed"]} | '
            f'Overdue: {task_stats["overdue"]} | '
            f'Due Today: {task_stats["today_count"]}'
        )

        top_tasks = t.filter(
            status__in=['pending', 'in_progress'],
        ).order_by('due_date')[:5]
        if top_tasks:
            parts.append('  Upcoming tasks:')
            for task in top_tasks:
                due = f' (due: {task.due_date})' if task.due_date else ''
                parts.append(f'    - {task.title} [{task.priority}]{due}')

        # ── Contacts ──
        c = self.user.contacts
        contact_stats = c.aggregate(
            total=Count('id'),
            new_month=Count('id', filter=Q(created_at__gte=thirty_days_ago)),
        )
        parts.append(
            'Contacts\n'
            f'  Total: {contact_stats["total"]} | '
            f'Added this month: {contact_stats["new_month"]}'
        )

        newest_contact = c.order_by('-created_at').first()
        if newest_contact:
            company = f' ({newest_contact.company})' if newest_contact.company else ''
            parts.append(f'  Recent: {newest_contact.full_name}{company}')

        # ── Leads ──
        l_qs = self.user.leads
        lead_stats = l_qs.aggregate(
            total=Count('id'),
            open=Count('id', filter=~Q(status__in=['Won', 'Lost'])),
            new_month=Count('id', filter=Q(created_at__gte=thirty_days_ago)),
        )
        parts.append(
            'Leads\n'
            f'  Total: {lead_stats["total"]} | '
            f'Open: {lead_stats["open"]} | '
            f'New this month: {lead_stats["new_month"]}'
        )

        highest_lead = (
            l_qs.exclude(expected_revenue__isnull=True)
            .order_by('-expected_revenue')
            .first()
        )
        if highest_lead:
            parts.append(
                f'  Highest value: {highest_lead.lead_name} - '
                f'Rs.{highest_lead.expected_revenue}'
            )

        newest_lead = l_qs.order_by('-created_at').first()
        if newest_lead:
            parts.append(f'  Newest: {newest_lead.lead_name}')

        # ── Campaigns ──
        cmp = self.user.campaigns
        camp_stats = cmp.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status__in=['Draft', 'Scheduled'])),
            sent=Count('id', filter=Q(status='Sent')),
        )
        parts.append(
            'Campaigns\n'
            f'  Total: {camp_stats["total"]} | '
            f'Active/Draft: {camp_stats["active"]} | '
            f'Sent: {camp_stats["sent"]}'
        )

        active_camps = cmp.filter(status__in=['Draft', 'Scheduled'])[:3]
        if active_camps:
            parts.append('  Active campaigns:')
            for camp in active_camps:
                sched = (
                    f' (scheduled: {camp.scheduled_at})'
                    if camp.scheduled_at else ''
                )
                parts.append(f'    - {camp.name}{sched}')

        # ── Calendar Events ──
        ev = self.user.events
        event_stats = ev.aggregate(
            today_count=Count('id', filter=Q(start_date=today)),
            tomorrow_count=Count('id', filter=Q(start_date=tomorrow)),
            week_count=Count(
                'id',
                filter=Q(start_date__gte=today, start_date__lte=week_end),
            ),
        )
        parts.append(
            'Calendar\n'
            f'  Today: {event_stats["today_count"]} | '
            f'Tomorrow: {event_stats["tomorrow_count"]} | '
            f'This week: {event_stats["week_count"]}'
        )

        today_events = ev.filter(start_date=today)[:5]
        if today_events:
            parts.append('  Today\'s schedule:')
            for ev_item in today_events:
                t_str = f' {ev_item.start_time}' if ev_item.start_time else ''
                parts.append(
                    f'    - {ev_item.title}{t_str} [{ev_item.event_type}]'
                )

        return '\n'.join(parts)
