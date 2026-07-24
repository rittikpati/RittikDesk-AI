"""Read-only CRM data query service.

Detects natural-language requests to view CRM data and returns
formatted results by querying the database directly — no LLM call.
"""

import logging
import re
from datetime import date, timedelta

from django.utils import timezone
from assistant.action_layer import _parse_date_from_text

logger = logging.getLogger(__name__)


class CRMQueryService:
    """Parses user messages for read-only CRM data requests and returns
    formatted results, or None if the message is not a known query."""

    def __init__(self, user):
        self.user = user
        self._handlers = [
            (self._match_show_leads, self._handle_show_leads),
            (self._match_show_contacts, self._handle_show_contacts),
            (self._match_search_contact, self._handle_search_contact),
            (self._match_overdue_tasks, self._handle_overdue_tasks),
            (self._match_events_by_date, self._handle_events_by_date),
            (self._match_today_events, self._handle_today_events),
            (self._match_active_campaigns, self._handle_active_campaigns),
            (self._match_notifications, self._handle_notifications),
            (self._match_recent_activity, self._handle_recent_activity),
            (self._match_today_activity, self._handle_today_activity),
            (self._match_today_emails, self._handle_today_emails),
            (self._match_today_tasks, self._handle_today_tasks),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, text):
        """Try to handle *text* as a CRM query. Returns a formatted
        string on match, or ``None`` to let the normal AI flow proceed."""
        text_lower = text.lower().strip()
        for matcher, handler in self._handlers:
            params = matcher(text_lower)
            if params is not None:
                try:
                    return handler(**params)
                except Exception:
                    logger.exception('CRM query handler failed')
                    return None
        return None

    # ------------------------------------------------------------------
    # Matchers — return a dict of handler kwargs or None
    # ------------------------------------------------------------------

    @staticmethod
    def _match_show_leads(text):
        if re.search(r'(show|list|get|display|view)\s+(my\s+)?leads', text):
            return {}
        return None

    @staticmethod
    def _match_show_contacts(text):
        if re.search(r'(show|list|get|display|view)\s+(my\s+)?contacts', text):
            return {}
        return None

    @staticmethod
    def _match_search_contact(text):
        m = re.search(
            r'(?:search|find|look\s*up|get)\s+contact\s+["\']?(.+?)["\']?$',
            text,
        )
        if m:
            return {'name': m.group(1).strip()}
        return None

    @staticmethod
    def _match_overdue_tasks(text):
        if re.search(r'(show|list|get|display|view)\s+(overdue|past\s+due)\s+tasks?', text):
            return {}
        if re.search(r'(overdue|past\s+due)\s+tasks?', text):
            return {}
        return None

    @staticmethod
    def _match_today_events(text):
        if re.search(
            r'(show|list|get|display|view)\s+(today\'?s?\s+)?(meetings?|events?|calendar)',
            text,
        ):
            return {}
        if re.search(r'today\'?s?\s+(meetings?|events?|schedule)', text):
            return {}
        return None

    @staticmethod
    def _match_active_campaigns(text):
        if re.search(r'(show|list|get|display|view)\s+(active\s+)?campaigns', text):
            return {}
        if re.search(r'active\s+campaigns', text):
            return {}
        return None

    @staticmethod
    def _match_notifications(text):
        if re.search(r'(show|list|get|display|view)\s+(recent\s+)?notifications', text):
            return {}
        if re.search(r'(my\s+)?notifications', text):
            return {}
        return None

    @staticmethod
    def _match_events_by_date(text):
        if not re.search(
            r'\b(meeting|meetings|event|events|calendar|schedule|appointment)\b',
            text,
        ):
            return None
        m = re.search(
            r'\b(today|tomorrow|yesterday|next\s+week|this\s+week|'
            r'monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
            r'\d{1,2}(?:st|nd|rd|th)?\s+'
            r'(?:january|february|march|april|may|june|'
            r'july|august|september|october|november|december|'
            r'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|'
            r'(?:january|february|march|april|may|june|'
            r'july|august|september|october|november|december|'
            r'jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?)\b',
            text, re.IGNORECASE,
        )
        if not m:
            return None
        return {'text': text}

    # ------------------------------------------------------------------
    # Handlers — query DB and return a formatted string
    # ------------------------------------------------------------------

    def _handle_show_leads(self):
        qs = self.user.leads.all().order_by('-created_at')[:20]
        if not qs:
            return 'You have no leads yet.'
        lines = [f'**Leads** ({len(qs)}):']
        for i, lead in enumerate(qs, 1):
            revenue = (
                f' — ${lead.expected_revenue:.2f}'
                if lead.expected_revenue else ''
            )
            assigned = (
                f' → {lead.assigned_user.get_full_name() or lead.assigned_user.email}'
                if lead.assigned_user else ''
            )
            lines.append(
                f'{i}. **{lead.lead_name}** ({lead.status}, {lead.priority}){revenue}{assigned}'
            )
        return '\n'.join(lines)

    def _handle_show_contacts(self):
        qs = self.user.contacts.all().order_by('-created_at')[:20]
        if not qs:
            return 'You have no contacts yet.'
        lines = [f'**Contacts** ({len(qs)}):']
        for i, contact in enumerate(qs, 1):
            company = f' @ {contact.company}' if contact.company else ''
            lines.append(
                f'{i}. **{contact.full_name}**{company}'
                f'{" · " + contact.email if contact.email else ""}'
                f'{" · " + contact.phone if contact.phone else ""}'
            )
        return '\n'.join(lines)

    def _handle_search_contact(self, name):
        qs = self.user.contacts.filter(
            full_name__icontains=name,
        ).order_by('full_name')[:10]
        if not qs:
            return f'No contacts found matching "{name}".'
        lines = [f'**Contacts matching "{name}"** ({len(qs)}):']
        for i, contact in enumerate(qs, 1):
            company = f' @ {contact.company}' if contact.company else ''
            lines.append(
                f'{i}. **{contact.full_name}**{company}'
                f'{" · " + contact.email if contact.email else ""}'
                f'{" · " + contact.phone if contact.phone else ""}'
            )
        return '\n'.join(lines)

    def _handle_overdue_tasks(self):
        today = date.today()
        qs = self.user.tasks.filter(
            due_date__lt=today,
        ).exclude(status='completed').order_by('due_date')[:20]
        if not qs:
            return 'No overdue tasks. Great job!'
        lines = [f'**Overdue Tasks** ({len(qs)}):']
        for i, task in enumerate(qs, 1):
            lines.append(
                f'{i}. **{task.title}** — due {task.due_date} ({task.priority})'
            )
        return '\n'.join(lines)

    def _handle_today_events(self):
        today = date.today()
        qs = self.user.events.filter(
            start_date=today,
        ).order_by('start_time', 'title')[:20]
        if not qs:
            return 'No events scheduled for today.'
        lines = [f'**Today\'s Events** ({len(qs)}):']
        for i, event in enumerate(qs, 1):
            time_str = (
                event.start_time.strftime('%I:%M %p').lstrip('0')
                if event.start_time else ''
            )
            time_str = f' @ {time_str}' if time_str else ''
            event_type = event.get_event_type_display()
            lines.append(
                f'{i}. **{event.title}** ({event_type}){time_str}'
            )
        return '\n'.join(lines)

    def _handle_events_by_date(self, text):
        d, _ = _parse_date_from_text(text)
        if not d:
            return None
        qs = self.user.events.filter(
            start_date=d,
        ).order_by('start_time', 'title')[:20]
        if not qs:
            date_str = d.strftime('%B %d, %Y')
            return f'No events or meetings scheduled for {date_str}.'
        date_str = d.strftime('%b %d, %Y')
        lines = [f'**Events for {date_str}** ({len(qs)}):']
        for i, event in enumerate(qs, 1):
            time_str = (
                event.start_time.strftime('%I:%M %p').lstrip('0')
                if event.start_time else ''
            )
            time_str = f' @ {time_str}' if time_str else ''
            event_type = event.get_event_type_display()
            location = f' · {event.location}' if event.location else ''
            lines.append(
                f'{i}. **{event.title}** ({event_type}){time_str}{location}'
            )
        return '\n'.join(lines)

    def _handle_active_campaigns(self):
        qs = self.user.campaigns.filter(
            status__in=('Scheduled', 'Sent'),
        ).order_by('-created_at')[:20]
        if not qs:
            return 'No active campaigns right now.'
        lines = [f'**Active Campaigns** ({len(qs)}):']
        for i, camp in enumerate(qs, 1):
            lines.append(
                f'{i}. **{camp.name}** ({camp.status})'
                f'{" · Scheduled: " + camp.scheduled_at.strftime("%b %d") if camp.scheduled_at else ""}'
            )
        return '\n'.join(lines)

    def _handle_notifications(self):
        qs = self.user.notifications.all().order_by('-created_at')[:10]
        if not qs:
            return 'No notifications yet.'
        lines = [f'**Recent Notifications** ({len(qs)}):']
        for i, notif in enumerate(qs, 1):
            read = '' if notif.is_read else ' · *Unread*'
            lines.append(
                f'{i}. **{notif.title}**{read}'
                f'\n   _{notif.created_at.strftime("%b %d, %I:%M %p")}_'
            )
        return '\n'.join(lines)

    # ── Activity Timeline queries ──

    @staticmethod
    def _match_recent_activity(text):
        patterns = [
            r'(?:show|list|get|display|view)\s+(?:my\s+)?(?:recent\s+)?activit',
            r'(?:what\s+did\s+i\s+do|my\s+activit|recent\s+activit)',
            r'(?:show|list|get)\s+(?:my\s+)?(?:recent\s+)?(?:crm\s+)?(?:activity|log|history)',
        ]
        for pat in patterns:
            if re.search(pat, text):
                return {}
        return None

    @staticmethod
    def _match_today_activity(text):
        patterns = [
            r'(?:what\s+did\s+i\s+do|my\s+activity|activity)\s+(?:today|this\s+day)',
            r"(?:show|list|get)\s+(?:today'?s?\s+)?(?:crm\s+)?(?:activity|activities)",
            r'(?:today\'?s?\s+(?:crm\s+)?activity|activity\s+(?:for|on)\s+today)',
        ]
        for pat in patterns:
            if re.search(pat, text):
                return {}
        return None

    @staticmethod
    def _match_today_emails(text):
        patterns = [
            r'(?:what|which)\s+emails?\s+(?:were\s+)?(?:sent|delivered)',
            r'(?:show|list|get)\s+(?:today\'?s?\s+)?(?:sent\s+)?emails?',
            r'(?:emails?\s+(?:sent|delivered)\s+(?:today|this\s+day))',
        ]
        for pat in patterns:
            if re.search(pat, text):
                return {}
        return None

    @staticmethod
    def _match_today_tasks(text):
        patterns = [
            r'(?:what|which)\s+tasks?\s+(?:were\s+)?(?:completed|done|finished)',
            r'(?:show|list|get)\s+(?:today\'?s?\s+)?(?:completed\s+)?tasks?',
            r'(?:tasks?\s+(?:completed|done)\s+(?:today|this\s+day))',
        ]
        for pat in patterns:
            if re.search(pat, text):
                return {}
        return None

    def _handle_recent_activity(self):
        from activities.models import ActivityLog
        qs = ActivityLog.objects.filter(user=self.user).order_by('-timestamp')[:20]
        if not qs:
            return 'No recent activities found. Start using your CRM and activities will appear here.'
        lines = [f'**Recent Activities** ({qs.count()}):']
        for i, act in enumerate(qs, 1):
            time_str = act.timestamp.strftime('%b %d, %I:%M %p')
            lines.append(f'{i}. **{act.title}** ({act.module}) — {time_str}')
        return '\n'.join(lines)

    def _handle_today_activity(self):
        from activities.models import ActivityLog
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = ActivityLog.objects.filter(user=self.user, timestamp__gte=today).order_by('-timestamp')
        count = qs.count()
        if not qs:
            return 'No activities recorded today yet.'
        lines = [f"**Today's Activities** ({count}):"]
        for i, act in enumerate(qs[:20], 1):
            time_str = act.timestamp.strftime('%I:%M %p')
            lines.append(f'{i}. **{act.title}** — {time_str}')
        return '\n'.join(lines)

    def _handle_today_emails(self):
        from activities.models import ActivityLog
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = ActivityLog.objects.filter(
            user=self.user, module='emails', timestamp__gte=today,
        ).order_by('-timestamp')
        count = qs.count()
        if not qs:
            return 'No emails sent today.'
        lines = [f"**Today's Emails** ({count}):"]
        for i, act in enumerate(qs[:20], 1):
            time_str = act.timestamp.strftime('%I:%M %p')
            lines.append(f'{i}. **{act.title}** — {time_str}')
        return '\n'.join(lines)

    def _handle_today_tasks(self):
        from activities.models import ActivityLog
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = ActivityLog.objects.filter(
            user=self.user, module='tasks', activity_type='task_completed',
            timestamp__gte=today,
        ).order_by('-timestamp')
        count = qs.count()
        if not qs:
            return 'No tasks completed today.'
        lines = [f"**Today's Completed Tasks** ({count}):"]
        for i, act in enumerate(qs[:20], 1):
            time_str = act.timestamp.strftime('%I:%M %p')
            lines.append(f'{i}. **{act.title}** — {time_str}')
        return '\n'.join(lines)
