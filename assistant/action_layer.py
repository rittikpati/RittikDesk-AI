"""Modular Action Layer between the chat endpoint and OpenRouter.

Each action is a plugin that registers itself with the ActionRegistry.
When a user message arrives, ActionLayer checks every registered action.
If one matches, it executes the action and returns the result.
If none match, the message passes through to the existing AI flow.
"""

import logging
import re
from datetime import date, timedelta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plugin base
# ---------------------------------------------------------------------------

class BaseAction:
    """Subclass to create a new action plugin.

    Must set:
        action_type (str) — unique id, e.g. ``"create_task"``
        keywords (frozenset) — trigger words for pre-filtering
        patterns (list of compiled regex) — matched against message text

    May override:
        execute(text, user) -> str
            Execute the action and return a human-readable result string.
            Default returns a placeholder.
    """

    action_type = ''
    keywords = frozenset()
    patterns = []

    def detect(self, text):
        """Return ``True`` if *text* looks like this action."""
        text_lower = text.lower()
        if not any(kw in text_lower for kw in self.keywords):
            return False
        return any(p.search(text_lower) for p in self.patterns)

    def execute(self, text, user):
        """Execute this action against the database.

        *text* — original user message
        *user* — authenticated Django user
        Returns a human-readable result string, or raises on failure.
        """
        return self._placeholder(text)

    def _placeholder(self, text):
        return f"CRM action detected: {self.action_type}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ActionRegistry:
    """Holds all registered action plugins."""

    def __init__(self):
        self._actions = {}

    def register(self, action_cls):
        action = action_cls() if isinstance(action_cls, type) else action_cls
        self._actions[action.action_type] = action
        logger.debug('Action registered: %s', action.action_type)
        return action

    def get(self, action_type):
        return self._actions.get(action_type)

    @property
    def all(self):
        return list(self._actions.values())


# ---------------------------------------------------------------------------
# Global registry
# ---------------------------------------------------------------------------

registry = ActionRegistry()


def register(action_cls):
    """Decorator to register an action plugin."""
    registry.register(action_cls)
    return action_cls


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ActionLayer:
    """Entry point. Call ``handle(text, user)`` from the chat view.

    Returns a result string if a CRM action is detected and executed, or
    ``None`` to let the message pass through to OpenRouter.
    """

    # Tiebreaker: when multiple actions match, prefer the one whose entity
    # keyword appears as a whole word in the text.
    _ENTITY_KEYWORDS = {
        'create_lead': r'\blead\b|\bprospect\b|\bdeal\b',
        'create_contact': r'\bcontact\b',
        'create_task': r'\btask\b|\bto-?do\b',
        'create_event': r'\bevent\b|\bmeeting\b|\bappointment\b',
        'create_campaign': r'\bcampaign\b',
        'create_notification': r'\bnotification\b|\balert\b',
        'create_workflow': r'\bworkflow\b|\bautomation\b|\brule\b',
        'delete_contact': r'\bcontact\b|\bperson\b',
        'delete_lead': r'\blead\b|\bprospect\b|\bdeal\b',
        'delete_task': r'\btask\b',
        'delete_event': r'\bevent\b|\bmeeting\b|\bappointment\b',
        'delete_campaign': r'\bcampaign\b',
        'update_contact': r'\bcontact\b|\bperson\b',
        'update_lead': r'\blead\b|\bprospect\b|\bdeal\b',
        'update_event': r'\bevent\b|\bmeeting\b|\bappointment\b|' + 
                        r'\blocation\b|\btime\b|\bdate\b|\bstatus\b|\btype\b',
        'compose_email': r'\bemail\b|\bmail\b|\bcompose\b|\bdraft\b',
        'view_contact': r'\bcontact\b|\bperson\b',
        'view_lead': r'\blead\b|\bprospect\b|\bdeal\b',
        'view_task': r'\btask\b|\bto-?do\b',
        'view_event': r'\bevent\b|\bmeeting\b|\bappointment\b',
    }

    @staticmethod
    def handle(text, user=None):
        if not text or not text.strip():
            return None
        text_lower = text.lower().strip()
        matched = []
        for action in registry.all:
            if action.detect(text_lower):
                matched.append(action)

        if not matched:
            return ActionLayer._fallback_search(text, user)

        if len(matched) > 1:
            best = None
            best_pos = len(text_lower) + 1
            for action in matched:
                kw = ActionLayer._ENTITY_KEYWORDS.get(action.action_type)
                if kw:
                    m = re.search(kw, text_lower)
                    if m and m.start() < best_pos:
                        best = action
                        best_pos = m.start()
            if best:
                logger.info(
                    'Action detected: %s | user=%s msg=%s',
                    best.action_type, user, text[:80],
                )
                return best.execute(text, user)

        action = matched[0]
        logger.info(
            'Action detected: %s | user=%s msg=%s',
            action.action_type, user, text[:80],
        )
        return action.execute(text, user)

    @staticmethod
    def _fallback_search(text, user):
        """When no action matches, try searching all entities for *text*.

        If exactly one object matches → show its details.
        If multiple objects match → show grouped results.
        If none → return ``None`` so the message passes to the AI.
        """
        if not user or not user.is_authenticated:
            return None

        query = text.strip()
        if not query or len(query) < 2:
            return None

        from django.db.models import Q

        results = []  # (type_label, obj_list)

        # Contacts
        contacts = list(user.contacts.filter(
            Q(full_name__icontains=query)
        )[:5])
        if contacts:
            results.append(('Contact', contacts))

        # Leads
        leads = list(user.leads.filter(
            Q(lead_name__icontains=query) | Q(contact_person__icontains=query)
        )[:5])
        if leads:
            results.append(('Lead', leads))

        # Tasks
        tasks = list(user.tasks.filter(
            Q(title__icontains=query)
        )[:5])
        if tasks:
            results.append(('Task', tasks))

        # Events
        events = list(user.events.filter(
            Q(title__icontains=query)
        )[:5])
        if events:
            results.append(('Event', events))

        if not results:
            return None

        total = sum(len(items) for _, items in results)

        if total == 1:
            # Single match — open it directly
            type_label, items = results[0]
            obj = items[0]
            return SearchAction._format_single_result(type_label, obj)

        # Multiple matches — grouped results
        lines = [f'I found **{total}** matches for "{query}":']
        for type_label, items in results:
            lines.append(f'\n**{type_label}**')
            for obj in items:
                name = SearchAction._obj_name(type_label, obj)
                lines.append(f'- {name}')
        lines.append(
            '\nWhich one would you like to open? '
            'You can say the number or the name.'
        )
        return '\n'.join(lines)


# ===========================================================================
# Built-in action plugins
# ===========================================================================

# ── Helpers shared across actions ──

_WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday',
             'saturday', 'sunday']

_MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9,
    'oct': 10, 'nov': 11, 'dec': 12,
}


def _parse_date_from_text(text):
    """Extract a ``date`` from *text* and return ``(date_obj, cleaned_text)``.

    Handles:
      - today, tomorrow
      - next week, next <weekday>, this <weekday>
      - in N days / in N weeks
      - Month Day, Day Month, YYYY-MM-DD, DD/MM/YYYY
      - due <date>, by <date>, on <date>
    Returns ``(None, text)`` if nothing found.
    """
    today = date.today()
    original = text
    text_lower = text.lower()

    LD = r'(?:due|by|on|before)\s+'  # optional leader word prefix

    # ── Relative dates ──

    for pattern, compute in [
        (rf'{LD}tomorrow', lambda m: today + timedelta(days=1)),
        (r'\btomorrow\b', lambda m: today + timedelta(days=1)),
        (rf'{LD}today', lambda m: today),
        (r'\btoday\b', lambda m: today),
        (rf'{LD}next\s+week', lambda m: today + timedelta(days=7)),
        (r'\bnext\s+week\b', lambda m: today + timedelta(days=7)),
    ]:
        m = re.search(pattern, text_lower)
        if m:
            return (compute(m), _remove_match(text, m))

    # next Monday/Tuesday/... (always the following week)
    for leader in [rf'{LD}next', r'\bnext']:
        m = re.search(
            leader + r'\s+(' + '|'.join(_WEEKDAYS) + r')\b', text_lower,
        )
        if m:
            target = _WEEKDAYS.index(m.group(1))
            delta = (target - today.weekday() + 7) % 7
            delta += 7  # always next week, not the upcoming occurrence
            return (today + timedelta(days=delta),
                    _remove_match(text, m))

    # this Monday/Tuesday/...
    for leader in [rf'{LD}this', r'\bthis']:
        m = re.search(
            leader + r'\s+(' + '|'.join(_WEEKDAYS) + r')\b', text_lower,
        )
        if m:
            target = _WEEKDAYS.index(m.group(1))
            delta = target - today.weekday()
            if delta <= 0:
                delta += 7
            return (today + timedelta(days=delta),
                    _remove_match(text, m))

    # Standalone weekday (e.g. "Monday" or "on Monday") — upcoming occurrence
    for leader in [rf'{LD}', r'\b']:
        m = re.search(
            leader + r'(' + '|'.join(_WEEKDAYS) + r')\b', text_lower,
        )
        if m:
            target = _WEEKDAYS.index(m.group(1))
            delta = target - today.weekday()
            if delta <= 0:
                delta += 7
            return (today + timedelta(days=delta),
                    _remove_match(text, m))

    # in N days / in N weeks
    m = re.search(r'\bin\s+(\d+)\s+(day|days|week|weeks)\b', text_lower)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        delta = num * 7 if unit in ('week', 'weeks') else num
        return (today + timedelta(days=delta),
                _remove_match(text, m))

    # ── Absolute dates ──

    # Month Day (e.g. "march 5", "mar 5th")
    for name, num in _MONTH_MAP.items():
        for prefix in [rf'{LD}', r'\b']:
            m = re.search(
                prefix + name + r'\s+(\d{1,2})(?:st|nd|rd|th)?\b', text_lower,
            )
            if m:
                try:
                    d = date(today.year, num, int(m.group(1)))
                    if d < today:
                        d = date(today.year + 1, num, int(m.group(1)))
                    return (d, _remove_match(text, m))
                except ValueError:
                    continue

    # Day Month (e.g. "5 march", "5th mar")
    for name, num in _MONTH_MAP.items():
        for prefix in [rf'{LD}', r'\b']:
            m = re.search(
                prefix + r'(\d{1,2})(?:st|nd|rd|th)?\s+' + name + r'\b', text_lower,
            )
            if m:
                try:
                    d = date(today.year, num, int(m.group(1)))
                    if d < today:
                        d = date(today.year + 1, num, int(m.group(1)))
                    return (d, _remove_match(text, m))
                except ValueError:
                    continue

    # YYYY-MM-DD
    m = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', text)
    if m:
        try:
            return (date(int(m.group(1)), int(m.group(2)), int(m.group(3))),
                    _remove_match(text, m))
        except ValueError:
            pass

    # DD/MM/YYYY
    m = re.search(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', text)
    if m:
        try:
            return (date(int(m.group(3)), int(m.group(2)), int(m.group(1))),
                    _remove_match(text, m))
        except ValueError:
            try:
                return (date(int(m.group(3)), int(m.group(1)), int(m.group(2))),
                        _remove_match(text, m))
            except ValueError:
                pass

    return (None, text)


def _parse_time_from_text(text):
    """Extract a ``time`` from *text*. Returns ``(time_obj, cleaned_text)``
    or ``(None, text)``.

    Handles:
      - at 3pm, at 3:30 PM
      - at 15:00 (24-hour)
    """
    from datetime import time as time_class

    # 12-hour with am/pm
    m = re.search(
        r'\b(?:at\s+|by\s+)?'
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b',
        text, re.IGNORECASE,
    )
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3).lower()
        if ampm == 'pm' and hour < 12:
            hour += 12
        elif ampm == 'am' and hour == 12:
            hour = 0
        try:
            return (time_class(hour, minute), _remove_match(text, m))
        except ValueError:
            pass

    # 24-hour HH:MM
    m = re.search(r'\b(\d{2}):(\d{2})\b', text)
    if m:
        try:
            t = time_class(int(m.group(1)), int(m.group(2)))
            return (t, _remove_match(text, m))
        except ValueError:
            pass

    return (None, text)


def _parse_datetime_from_text(text):
    """Extract a ``datetime`` from *text*.  Returns ``(datetime_obj, cleaned_text)``
    or ``(None, text)``.

    Combines date + time parsing in a single pass so that both date and
    time words are removed from the returned text.  The returned datetime
    is timezone-aware (uses Django's current timezone).
    """
    from datetime import datetime as dt_class
    from django.utils import timezone

    d, body = _parse_date_from_text(text)
    if not d:
        return (None, text)
    t, body = _parse_time_from_text(body)
    if t:
        dt = dt_class.combine(d, t)
    else:
        dt = dt_class.combine(d, dt_class.min.time())
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return (dt, body)


def _remove_match(text, match):
    """Remove a regex match region from *text*, preserving original case."""
    return (text[:match.start()] + text[match.end():]).strip()


def _extract_priority(text):
    """Extract priority from *text*.  Returns ``(priority, cleaned_text)``.

    Priority is one of ``'high'``, ``'medium'``, ``'low'``, or ``None``.
    """
    text_lower = text.lower()
    rules = [
        (r'\bhigh\s+priority\b', 'high'),
        (r'\bpriority\s+high\b', 'high'),
        (r'\burgent\b', 'high'),
        (r'\bcritical\b', 'high'),
        (r'\bmedium\s+priority\b', 'medium'),
        (r'\bpriority\s+medium\b', 'medium'),
        (r'\bnormal\s+priority\b', 'medium'),
        (r'\blow\s+priority\b', 'low'),
        (r'\bpriority\s+low\b', 'low'),
        (r'\bminor\b', 'low'),
    ]
    for pattern, value in rules:
        m = re.search(pattern, text_lower)
        if m:
            return (value, _remove_match(text, m))
    return (None, text)


def _extract_title(text):
    """Extract a meaningful title from the remaining message text."""
    text = re.sub(r'\s+', ' ', text).strip()
    # Strip leading/trailing punctuation
    text = re.sub(r'^[:\-;.,\s]+', '', text).strip()
    text = re.sub(r'[:\-;.,\s]+$', '', text).strip()
    # Remove trailing prepositions / noise
    text = re.sub(r'\b(due|by|on|at|for|to|with|about)\s*$', '', text, flags=re.IGNORECASE).strip()
    return text


# ---------------------------------------------------------------------------
# Update-action helpers
# ---------------------------------------------------------------------------

# Maps natural-language field phrases → model field names for each entity

_CONTACT_UPDATE_FIELDS = {
    'phone': 'phone', 'phone number': 'phone', 'mobile': 'phone',
    'telephone': 'phone', 'tel': 'phone',
    'email': 'email', 'e-mail': 'email', 'mail': 'email',
    'company': 'company', 'organization': 'company', 'org': 'company',
    'job title': 'job_title', 'designation': 'job_title',
    'notes': 'notes', 'note': 'notes',
    'tags': 'tags', 'tag': 'tags',
    'name': 'full_name', 'full name': 'full_name',
}

_LEAD_UPDATE_FIELDS = {
    'status': 'status',
    'priority': 'priority',
    'source': 'source',
    'lead name': 'lead_name', 'name': 'lead_name',
    'company': 'company',
    'contact person': 'contact_person',
    'expected revenue': 'expected_revenue', 'revenue': 'expected_revenue',
    'email': 'email', 'phone': 'phone',
    'notes': 'notes', 'note': 'notes',
}

_TASK_UPDATE_FIELDS = {
    'status': 'status',
    'priority': 'priority',
    'due date': 'due_date', 'deadline': 'due_date',
    'due time': 'due_time',
    'title': 'title', 'name': 'title',
    'description': 'description', 'desc': 'description',
    'notes': 'description',
}

_EVENT_UPDATE_FIELDS = {
    'title': 'title', 'name': 'title',
    'date': 'start_date', 'start date': 'start_date',
    'time': 'start_time', 'start time': 'start_time',
    'end time': 'end_time',
    'location': 'location', 'place': 'location',
    'status': 'status',
    'type': 'event_type', 'event type': 'event_type',
    'description': 'description',
    'meeting link': 'meeting_link', 'link': 'meeting_link', 'url': 'meeting_link',
}


def _parse_update_field_value(text, field_map):
    """Extract (model_field, raw_value, remaining) from an update message.

    Tries:
      1.  ``<field> to <value>`` / ``<field> as <value>`` / ``<field>: <value>``
      2.  ``as <value>`` at end (status-only updates)
      3.  ``'s <field> to <value>`` (possessive)
    Returns ``(None, None, text)`` when nothing is found.
    """
    text_stripped = text.strip()
    text_lower = text_stripped.lower()

    # Build alternation sorted longest-first so longer phrases match before
    # substrings (e.g. "phone number" before "phone").
    keys = sorted(field_map.keys(), key=len, reverse=True)
    field_alt = '|'.join(re.escape(k) for k in keys)

    # 0.  "<field> of <name> to/as <value>"  → "company of Rahul Sharma to Google"
    m = re.search(
        r'\b(' + field_alt + r')\s+of\s+(.+?)\s+(?:to|as)\s+(.+?)$',
        text_stripped, flags=re.IGNORECASE,
    )
    if m:
        raw_field = m.group(1).lower()
        value = m.group(3).strip()
        remaining = m.group(2).strip()
        return (field_map[raw_field], value, remaining)

    # 1.  "<field> to/as/is/= <value>"  or  "<field>: <value>" at end
    m = re.search(
        r'\b(' + field_alt + r')(?:\s+(?:to|as|is|=)|:\s*)\s*(.+?)$',
        text_stripped, flags=re.IGNORECASE,
    )
    if m:
        raw_field = m.group(1).lower()
        value = m.group(2).strip()
        remaining = text_stripped[:m.start()].strip()
        remaining = re.sub(r"'s\s*$", '', remaining, flags=re.IGNORECASE).strip()
        remaining = re.sub(
            r'\s+(?:to|for|with|about|regarding)\s*$', '', remaining,
            flags=re.IGNORECASE,
        ).strip()
        return (field_map[raw_field], value, remaining)

    # 2.  possessive:  "<name>'s <field> to/as/is/= <value>"  or  "<name>'s <field>: <value>"
    m = re.search(
        r"'s\s+(" + field_alt + r")(?:\s+(?:to|as|is|=)|:\s*)\s*(.+?)$",
        text_stripped, flags=re.IGNORECASE,
    )
    if m:
        raw_field = m.group(1).lower()
        value = m.group(2).strip()
        remaining = text_stripped[:m.start()].strip()
        remaining = re.sub(r"\s*'?\s*$", '', remaining)
        return (field_map[raw_field], value, remaining)

    # 3.  "as <value>" at end  (status-only)
    m = re.search(r'\bas\s+(.+?)$', text_stripped, flags=re.IGNORECASE)
    if m:
        value = m.group(1).strip()
        remaining = text_stripped[:m.start()].strip()
        remaining = re.sub(r'\s+(?:for|with|about)\s*$', '', remaining, flags=re.IGNORECASE).strip()
        return ('status', value, remaining)

    return (None, None, text)


def _normalise_contact_field_value(field, raw, user):
    """Validate + normalise a contact field value.  Returns (field, value)
    or raises ``ValueError`` explaining the problem."""
    if field == 'full_name':
        val = re.sub(r'\s+', ' ', raw).strip()
        if not val:
            raise ValueError('Name cannot be empty.')
        return (field, val)

    if field == 'email':
        val = raw.lower().strip()
        if not re.match(r'[^@\s]+@[^@\s]+\.[^@\s]+$', val):
            raise ValueError(f'"{raw}" is not a valid email address.')
        return (field, val)

    if field in ('phone', 'company', 'job_title', 'notes', 'tags'):
        return (field, raw.strip())

    raise ValueError(f'Unknown contact field: "{field}".')


def _normalise_lead_field_value(field, raw, user):
    """Validate + normalise a lead field value.  Returns (field, value)
    or raises ``ValueError``."""
    from leads.models import Lead

    if field == 'lead_name':
        val = re.sub(r'\s+', ' ', raw).strip()
        if not val:
            raise ValueError('Lead name cannot be empty.')
        return (field, val)

    if field == 'status':
        val = raw.strip().lower()
        status_map = {
            'new': 'New', 'contacted': 'Contacted', 'qualified': 'Qualified',
            'proposal sent': 'Proposal Sent', 'proposal': 'Proposal Sent',
            'negotiation': 'Negotiation',
            'won': 'Won', 'closed won': 'Won',
            'lost': 'Lost', 'closed lost': 'Lost',
        }
        if val in status_map:
            return (field, status_map[val])
        # Try partial match
        for k, mapped in status_map.items():
            if k.startswith(val) or val.startswith(k):
                return (field, mapped)
        raise ValueError(f'Unknown lead status: "{raw}". '
                         f'Valid: {", ".join(dict(Lead.STATUS_CHOICES).values())}.')

    if field == 'priority':
        val = raw.strip().lower()
        priority_map = {'low': 'Low', 'medium': 'Medium', 'high': 'High', 'urgent': 'Urgent'}
        if val in priority_map:
            return (field, priority_map[val])
        for k, mapped in priority_map.items():
            if k.startswith(val) or val.startswith(k):
                return (field, mapped)
        raise ValueError(f'Unknown priority: "{raw}". Use Low, Medium, High, or Urgent.')

    if field == 'source':
        from leads.models import Lead
        val = raw.strip().lower()
        source_map = {s.lower(): s for s in dict(Lead.SOURCE_CHOICES)}
        if val in source_map:
            return (field, source_map[val])
        for k, mapped in source_map.items():
            if k.startswith(val) or val.startswith(k):
                return (field, mapped)
        return (field, raw.strip().title())

    if field == 'expected_revenue':
        cleaned = re.sub(r'[$,]', '', raw).strip()
        try:
            return (field, float(cleaned))
        except ValueError:
            raise ValueError(f'Could not parse revenue from "{raw}".')

    if field in ('company', 'contact_person', 'email', 'phone', 'notes'):
        return (field, raw.strip())

    raise ValueError(f'Unknown lead field: "{field}".')


def _normalise_task_field_value(field, raw, user):
    """Validate + normalise a task field value.  Returns (field, value)
    or raises ``ValueError``."""
    from tasks.models import Task

    if field in ('title', 'description', 'notes'):
        return (field, raw.strip())

    if field == 'priority':
        val = raw.strip().lower()
        for choice_val, _ in Task.PRIORITY_CHOICES:
            if val == choice_val or val.startswith(choice_val) or choice_val.startswith(val):
                return (field, choice_val)
        raise ValueError(f'Unknown priority: "{raw}". '
                         f'Valid: {", ".join(dict(Task.PRIORITY_CHOICES).values())}.')

    if field == 'status':
        val = raw.strip().lower()
        status_map = {
            'pending': 'pending', 'todo': 'pending', 'not started': 'pending',
            'in progress': 'in_progress', 'in-progress': 'in_progress',
            'inprogress': 'in_progress', 'doing': 'in_progress',
            'completed': 'completed', 'done': 'completed', 'finished': 'completed',
        }
        if val in status_map:
            return (field, status_map[val])
        for k, mapped in status_map.items():
            if k.startswith(val) or val.startswith(k):
                return (field, mapped)
        raise ValueError(f'Unknown task status: "{raw}". '
                         f'Valid: {", ".join(dict(Task.STATUS_CHOICES).values())}.')

    if field == 'due_date':
        d, _ = _parse_date_from_text(raw)
        if d:
            return (field, d)
        raise ValueError(f'Could not parse a date from "{raw}".')

    if field == 'due_time':
        t, _ = _parse_time_from_text(raw)
        if t:
            return (field, t)
        raise ValueError(f'Could not parse a time from "{raw}".')

    raise ValueError(f'Unknown task field: "{field}".')


def _normalise_event_field_value(field, raw, user):
    """Validate + normalise an event field value.  Returns (field, value)
    or raises ``ValueError``."""
    from calendars.models import Event

    if field in ('title', 'description', 'location', 'meeting_link'):
        return (field, raw.strip())

    if field == 'start_date':
        d, _ = _parse_date_from_text(raw)
        if d:
            return (field, d)
        # Could also be a relative reference like "tomorrow" → _parse_date_from_text handles that
        raise ValueError(f'Could not parse a date from "{raw}".')

    if field == 'start_time':
        t, _ = _parse_time_from_text(raw)
        if t:
            return (field, t)
        raise ValueError(f'Could not parse a time from "{raw}".')

    if field == 'end_time':
        t, _ = _parse_time_from_text(raw)
        if t:
            return (field, t)
        raise ValueError(f'Could not parse a time from "{raw}".')

    if field == 'status':
        val = raw.strip().lower()
        status_map = {
            'scheduled': 'scheduled', 'planned': 'scheduled',
            'completed': 'completed', 'done': 'completed', 'finished': 'completed',
            'cancelled': 'cancelled', 'canceled': 'cancelled', 'cancel': 'cancelled',
        }
        if val in status_map:
            return (field, status_map[val])
        for k, mapped in status_map.items():
            if k.startswith(val) or val.startswith(k):
                return (field, mapped)
        raise ValueError(f'Unknown event status: "{raw}". '
                         f'Valid: {", ".join(dict(Event.STATUS_CHOICES).values())}.')

    if field == 'event_type':
        val = raw.strip().lower()
        type_map = {
            'meeting': 'meeting', 'call': 'call', 'phone': 'call',
            'reminder': 'reminder', 'personal': 'personal',
        }
        if val in type_map:
            return (field, type_map[val])
        for k, mapped in type_map.items():
            if k.startswith(val) or val.startswith(k):
                return (field, mapped)
        raise ValueError(f'Unknown event type: "{raw}". '
                         f'Valid: {", ".join(dict(Event.EVENT_TYPE_CHOICES).values())}.')

    raise ValueError(f'Unknown event field: "{field}".')


# ═══════════════════════════════════════════════════════════════════════════
#  search
# ═══════════════════════════════════════════════════════════════════════════

@register
class SearchAction(BaseAction):
    """Search all CRM entities and return grouped results or open directly."""
    action_type = 'search'
    keywords = frozenset({'search', 'find', 'lookup', 'look', 'results'})
    patterns = [
        re.compile(r'(search|find|look\s?up)\s+(?:for\s+)?'),
    ]

    @staticmethod
    def _obj_name(type_label, obj):
        if type_label == 'Contact':
            return f'{obj.full_name}  ({obj.email or obj.phone or "—"})'
        if type_label == 'Lead':
            return f'{obj.lead_name}  ({obj.get_status_display()})'
        if type_label == 'Task':
            return f'{obj.title}  ({obj.get_status_display()})'
        if type_label == 'Event':
            return f'{obj.title}  ({obj.start_date})'
        return str(obj)

    @staticmethod
    def _format_single_result(type_label, obj):
        if type_label == 'Contact':
            created = obj.created_at.strftime('%b %d, %Y') if obj.created_at else '—'
            updated = obj.updated_at.strftime('%b %d, %Y') if obj.updated_at else '—'
            rows = [
                f'| **Name**     | {obj.full_name}',
                f'| **Email**    | {obj.email or "—"}',
                f'| **Phone**    | {obj.phone or "—"}',
                f'| **Company**  | {obj.company or "—"}',
                f'| **Position** | {obj.job_title or "—"}',
                f'| **Notes**    | {obj.notes or "—"}',
                f'| **Created**  | {created}',
                f'| **Updated**  | {updated}',
            ]
            return '### Contact Details\n' + '\n'.join(rows)
        if type_label == 'Lead':
            revenue = f'${obj.expected_revenue:,.2f}' if obj.expected_revenue else '—'
            assigned = obj.assigned_user.get_full_name() or str(obj.assigned_user) if obj.assigned_user else '—'
            rows = [
                f'| **Name**            | {obj.lead_name}',
                f'| **Email**           | {obj.email or "—"}',
                f'| **Phone**           | {obj.phone or "—"}',
                f'| **Status**          | {obj.get_status_display()}',
                f'| **Priority**        | {obj.get_priority_display()}',
                f'| **Expected Revenue**| {revenue}',
                f'| **Source**          | {obj.get_source_display()}',
                f'| **Notes**           | {obj.notes or "—"}',
                f'| **Owner**           | {assigned}',
            ]
            return '### Lead Details\n' + '\n'.join(rows)
        if type_label == 'Task':
            due_date = obj.due_date.strftime('%b %d, %Y') if obj.due_date else '—'
            due_time = obj.due_time.strftime('%I:%M %p').lstrip('0') if obj.due_time else ''
            due_str = f'{due_date} {due_time}'.strip() if due_time else due_date
            contact_name = obj.contact.full_name if obj.contact else '—'
            rows = [
                f'| **Title**       | {obj.title}',
                f'| **Description** | {obj.description or "—"}',
                f'| **Due**         | {due_str}',
                f'| **Priority**    | {obj.get_priority_display()}',
                f'| **Status**      | {obj.get_status_display()}',
                f'| **Contact**     | {contact_name}',
            ]
            return '### Task Details\n' + '\n'.join(rows)
        if type_label == 'Event':
            start_date = obj.start_date.strftime('%b %d, %Y') if obj.start_date else '—'
            start_time = obj.start_time.strftime('%I:%M %p').lstrip('0') if obj.start_time else '—'
            end_time = obj.end_time.strftime('%I:%M %p').lstrip('0') if obj.end_time else '—'
            time_str = f'{start_time} – {end_time}' if obj.start_time else '—'
            rows = [
                f'| **Title**  | {obj.title}',
                f'| **Date**   | {start_date}',
                f'| **Time**   | {time_str}',
                f'| **Location**| {obj.location or "—"}',
                f'| **Type**   | {obj.get_event_type_display()}',
                f'| **Status** | {obj.get_status_display()}',
            ]
            return '### Event Details\n' + '\n'.join(rows)
        return str(obj)

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:search|find|look\s?up)\s+(?:for\s+)?',
            '', body, flags=re.IGNORECASE,
        ).strip()
        return _extract_title(body)

    def execute(self, text, user):
        query = self._parse(text)
        if not query:
            return 'What would you like to search for? I can search contacts, leads, tasks, and events.'

        from django.db.models import Q

        results = []

        contacts = list(user.contacts.filter(
            Q(full_name__icontains=query)
        )[:5])
        if contacts:
            results.append(('Contact', contacts))

        leads = list(user.leads.filter(
            Q(lead_name__icontains=query) | Q(contact_person__icontains=query)
        )[:5])
        if leads:
            results.append(('Lead', leads))

        tasks = list(user.tasks.filter(
            Q(title__icontains=query)
        )[:5])
        if tasks:
            results.append(('Task', tasks))

        events = list(user.events.filter(
            Q(title__icontains=query)
        )[:5])
        if events:
            results.append(('Event', events))

        if not results:
            return f'I could not find any contacts, leads, tasks, or events matching "{query}".'

        total = sum(len(items) for _, items in results)

        if total == 1:
            type_label, items = results[0]
            return self._format_single_result(type_label, items[0])

        lines = [f'I found **{total}** matches for "{query}":']
        for type_label, items in results:
            lines.append(f'\n**{type_label}**')
            for obj in items:
                lines.append(f'- {self._obj_name(type_label, obj)}')
        lines.append(
            '\nWhich one would you like to open? '
            'You can type its name or number.'
        )
        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════════════
#  create_task
# ═══════════════════════════════════════════════════════════════════════════

@register
class CreateTaskAction(BaseAction):
    action_type = 'create_task'
    keywords = frozenset({'create', 'add', 'new', 'make', 'task', 'to-do', 'todo'})
    patterns = [re.compile(r'(create|add|new|make).*(task|to-?do)')]

    def execute(self, text, user):
        params = self._parse(text)
        title = params.get('title', '').strip()
        if not title:
            return (
                'I need a title to create a task. '
                'What should the task be called?'
            )

        priority = params.get('priority', 'medium')
        if priority not in ('low', 'medium', 'high'):
            priority = 'medium'

        contact = None
        if '_contact_raw' in params:
            contact = self._resolve_contact(params['_contact_raw'], user)
        if not contact:
            contact = self._find_contact_in_text(text, user)

        # Clean contact name from title if present
        if contact and contact.full_name:
            for name_part in [contact.full_name, contact.full_name.split()[0]]:
                if name_part.lower() in title.lower():
                    title = re.sub(
                        re.escape(name_part), '', title, flags=re.IGNORECASE,
                    ).strip()
                    title = re.sub(r'^(?:to|for)\s+', '', title, flags=re.IGNORECASE).strip()
                    title = re.sub(r'\s+', ' ', title).strip()
                    break

        if not title:
            return (
                'I need a title to create a task. '
                'What should the task be called?'
            )

        from tasks.models import Task
        from django.db import transaction

        try:
            with transaction.atomic():
                task = Task(
                    owner=user,
                    title=title,
                    description=params.get('description', ''),
                    priority=priority,
                    due_date=params.get('due_date'),
                )
                if contact:
                    task.contact = contact
                task.save()
                task.refresh_from_db()
        except Exception as e:
            logger.exception('Failed to create task for user=%s', user)
            return f'Failed to create task: {e}'

        lines = [f'Task created successfully: **{task.title}**']
        if task.due_date:
            lines.append(f'Due: {task.due_date.strftime("%b %d, %Y")}')
        lines.append(f'Priority: {task.priority.title()}')
        if task.contact:
            lines.append(f'Contact: {task.contact.full_name}')
        if task.description:
            lines.append(f'Description: {task.description[:200]}')
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Extract priority FIRST (before prefix is stripped)
        priority, body = _extract_priority(body)
        if priority:
            params['priority'] = priority

        # 2. Strip action prefix — find "task" or "to-do" and take everything after it
        m = re.search(
            r'\b(?:create|add|new|make)\s'
            r'(?:.*?\s+)?'
            r'(?:task|to-?do)\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        body = re.sub(r'^to\s+', '', body, flags=re.IGNORECASE).strip()

        # 3. Extract raw contact name from @mention only
        m = re.search(r'@(\w[\w\s]{0,30}?)', body)
        if m:
            params['_contact_raw'] = m.group(1).strip()
            body = _remove_match(body, m)

        # 4. Extract due date
        due_date, body = _parse_date_from_text(body)
        if due_date:
            params['due_date'] = due_date

        # 5. Extract description after colon / "description:" / "note:"
        for sep in [r'\bdescription\s*:\s*', r'\bdesc\s*:\s*',
                     r'\bnote\s*:\s*', r'\bdetails?\s*:\s*']:
            m = re.search(sep, body, flags=re.IGNORECASE)
            if m:
                after = body[m.end():].strip()
                if after:
                    params['description'] = after
                    body = body[:m.start()].strip()
                    break

        # 6. Strip leading "to " / "for " from body
        body = re.sub(r'^(?:to|for)\s+', '', body, flags=re.IGNORECASE).strip()

        # 7. Remaining body → title
        title = _extract_title(body)
        if title:
            params['title'] = title

        return params

    def _resolve_contact(self, raw_name, user):
        if not raw_name or not user:
            return None
        try:
            from contacts.models import Contact
            return Contact.objects.filter(
                owner=user, full_name__icontains=raw_name,
            ).first()
        except Exception:
            return None

    def _find_contact_in_text(self, text, user):
        """Scan *text* for words that match contact names in the DB."""
        if not text or not user:
            return None
        try:
            from contacts.models import Contact
            contacts = Contact.objects.filter(owner=user)
            text_lower = text.lower()
            for c in contacts:
                if c.full_name and c.full_name.lower() in text_lower:
                    return c
                first = c.full_name.split()[0] if c.full_name else ''
                if first and first.lower() in text_lower:
                    return c
        except Exception:
            pass
        return None


@register
class UpdateTaskAction(BaseAction):
    action_type = 'update_task'
    keywords = frozenset({
        'update', 'edit', 'change', 'modify', 'rename', 'mark', 'set',
        'task', 'done', 'complete', 'finish',
    })
    patterns = [
        re.compile(r'(update|edit|change|modify|rename|mark|set).*(task)'),
        re.compile(r'(task).*(as|to)\s+(completed|done|finished|pending|in.progress|in_progress)'),
    ]

    def _parse(self, text):
        """Parse *text* into params dict: keys ``title``, ``field``, ``value``."""
        params = {}
        body = text

        # 1. Strip action verb
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:update|edit|change|modify|rename|mark|set)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Strip entity type "task"
        body = re.sub(r'^task\s+', '', body, flags=re.IGNORECASE).strip()

        # 3. Try field-value extraction
        field, value, remaining = _parse_update_field_value(body, _TASK_UPDATE_FIELDS)
        if field:
            params['field'] = field
            params['value'] = value
            params['title'] = _extract_title(remaining)
            return params

        # 4. Fallback: extract date / time / priority from body
        d, body = _parse_date_from_text(body)
        if d:
            params['field'] = 'due_date'
            params['value'] = d
            params['title'] = _extract_title(body)
            return params

        priority, body = _extract_priority(body)
        if priority:
            params['field'] = 'priority'
            params['value'] = priority
            params['title'] = _extract_title(body)
            return params

        # 5. Remaining body is the title (for "mark task X as done", etc.)
        #    But first check for trailing status word
        m = re.search(r'\b(as\s+)?(completed|done|finished|pending|in.progress|in_progress)\s*$', body, flags=re.IGNORECASE)
        if m:
            params['field'] = 'status'
            params['value'] = m.group(2)
            params['title'] = _extract_title(body[:m.start()])
        else:
            params['title'] = _extract_title(body)

        return params

    def execute(self, text, user):
        params = self._parse(text)
        title = params.get('title', '').strip()
        if not title:
            return (
                'I need a task title to update. '
                'Which task should I update?'
            )

        field = params.get('field', '')
        value = params.get('value')

        from tasks.models import Task
        from django.db import transaction
        from django.core.exceptions import ValidationError

        # Find the task
        qs = user.tasks.all()
        task = qs.filter(title__icontains=title).first()
        if not task:
            # Try exact match
            task = qs.filter(title__iexact=title).first()
        if not task:
            return f'I could not find a task matching "{title}".'

        # Normalise the field + value
        try:
            norm_field, norm_value = _normalise_task_field_value(field, str(value), user)
        except ValueError as e:
            return str(e)

        old_value = getattr(task, norm_field)

        # Update
        try:
            with transaction.atomic():
                setattr(task, norm_field, norm_value)
                task.full_clean()
                task.save()
                task.refresh_from_db()
        except ValidationError as e:
            error_details = []
            for fld, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{fld}: {err}')
            return (
                'Failed to update task — validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception('Failed to update task for user=%s', user)
            return f'Failed to update task: {e}'

        lines = [f'Task **"{task.title}"** updated.']
        if norm_field == 'status':
            lines.append(f'Status: {task.get_status_display()}')
        elif norm_field == 'priority':
            lines.append(f'Priority: {task.get_priority_display()}')
        elif norm_field == 'due_date':
            lines.append(f'Due: {task.due_date.strftime("%b %d, %Y") if task.due_date else "None"}')
        else:
            lines.append(f'{norm_field.replace("_", " ").title()}: {norm_value}')
        return '  \n'.join(lines)


@register
class DeleteTaskAction(BaseAction):
    action_type = 'delete_task'
    keywords = frozenset({'delete', 'remove', 'erase', 'cancel', 'task'})
    patterns = [
        re.compile(r'(delete|remove|erase|cancel)\s+task\b'),
        re.compile(r'(delete|remove|erase|cancel).*\btask\b'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:delete|remove|erase|cancel)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^task\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+task\s*$', '', body, flags=re.IGNORECASE).strip()
        return _extract_title(body)

    def execute(self, text, user):
        title = self._parse(text)
        if not title:
            return 'I need a task title to delete. Which task should I delete?'

        from tasks.models import Task

        qs = user.tasks.all()
        matches = list(qs.filter(title__icontains=title))
        if len(matches) == 0:
            return f'I could not find a task matching "{title}".'
        if len(matches) > 1:
            names = '\n'.join(f'  {i+1}. **{t.title}**' for i, t in enumerate(matches))
            return (
                f'I found multiple tasks matching "{title}":\n'
                f'{names}\n'
                f'Please specify which one you want to delete.'
            )

        task = matches[0]
        try:
            from django.db import transaction
            with transaction.atomic():
                task.delete()
        except Exception as e:
            logger.exception('Failed to delete task for user=%s', user)
            return f'Failed to delete task: {e}'

        return f'Task **"{title}"** has been deleted.'


@register
class ViewTaskAction(BaseAction):
    action_type = 'view_task'
    keywords = frozenset({'task', 'show', 'view', 'open', 'details', 'tell', 'about'})
    patterns = [
        re.compile(r'(show|view|open).*(task)'),
        re.compile(r'(task).*(details|info|information)'),
        re.compile(r'(tell|show).*(about).*(task)'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:show|view|open)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(
            r'^(?:tell\s+me\s+about|tell\s+about|tell\s+me)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^task\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'^(?:details|info|information)\s+(?:for|about|on)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'\s+(?:details|info|information)\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+task\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'^about\s+', '', body, flags=re.IGNORECASE).strip()
        return _extract_title(body)

    def execute(self, text, user):
        title = self._parse(text)
        if not title:
            return 'I need a task title. Which task would you like to view?'

        from tasks.models import Task

        qs = user.tasks.all()
        task = qs.filter(title__icontains=title).first()
        if not task:
            task = qs.filter(title__iexact=title).first()
        if not task:
            return f'I could not find a task matching "{title}".'

        due_date = task.due_date.strftime('%b %d, %Y') if task.due_date else '—'
        due_time = task.due_time.strftime('%I:%M %p').lstrip('0') if task.due_time else ''
        due_str = f'{due_date} {due_time}'.strip() if due_time else due_date

        contact_name = task.contact.full_name if task.contact else '—'

        rows = [
            f'| **Title**       | {task.title}',
            f'| **Description** | {task.description or "—"}',
            f'| **Due**         | {due_str}',
            f'| **Priority**    | {task.get_priority_display()}',
            f'| **Status**      | {task.get_status_display()}',
            f'| **Contact**     | {contact_name}',
        ]
        table = '\n'.join(rows)
        return f'### Task Details\n{table}'


@register
class CompleteTaskAction(BaseAction):
    action_type = 'complete_task'
    keywords = frozenset({'mark', 'complete', 'finish', 'done', 'task'})
    patterns = [
        re.compile(r'(mark|complete|finish|done).*(task)'),
        re.compile(r'(task).*(complete|done|finished)'),
    ]

    def extract_params(self, text):
        return {}


@register
class ReopenTaskAction(BaseAction):
    action_type = 'reopen_task'
    keywords = frozenset({'reopen', 'unarchive', 'task'})
    patterns = [re.compile(r'(reopen|unarchive).*(task)')]

    def extract_params(self, text):
        return {}


@register
class CreateContactAction(BaseAction):
    action_type = 'create_contact'
    keywords = frozenset({'create', 'add', 'new', 'contact', 'person'})
    patterns = [re.compile(r'(create|add|new).*(contact|person)')]

    def execute(self, text, user):
        params = self._parse(text)
        full_name = params.get('full_name', '').strip()
        if not full_name:
            return (
                'I need a contact name to create a contact. '
                'What should the contact be called?'
            )

        from contacts.models import Contact
        from django.db import transaction
        from django.core.exceptions import ValidationError

        sid = None
        try:
            with transaction.atomic():
                sid = transaction.savepoint()
                contact = Contact(
                    owner=user,
                    full_name=full_name,
                    company=params.get('company', ''),
                    job_title=params.get('job_title', ''),
                    email=params.get('email', ''),
                    phone=params.get('phone', ''),
                    tags=params.get('tags', ''),
                    notes=params.get('notes', ''),
                )
                contact.full_clean()
                contact.save()
                contact.refresh_from_db()

                saved_pk = contact.pk
                try:
                    reloaded = Contact.objects.get(pk=saved_pk)
                except Contact.DoesNotExist:
                    transaction.savepoint_rollback(sid)
                    logger.error(
                        'Contact pk=%s was NOT committed -- DB get() returned None. '
                        'user=%s msg=%s',
                        saved_pk, user, text[:120],
                    )
                    return (
                        'Failed to create contact: the record was not persisted '
                        'to the database. Please try again.'
                    )

        except ValidationError as e:
            logger.error(
                'Contact validation failed for user=%s msg=%s error=%s',
                user, text[:120], e.message_dict,
            )
            error_details = []
            for field, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{field}: {err}')
            return (
                'Failed to create contact -- validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception(
                'Failed to create contact for user=%s msg=%s', user, text[:120],
            )
            if sid is not None:
                logger.warning('Transaction rolled back at savepoint %s', sid)
            return f'Failed to create contact: {e}'

        lines = [
            'Contact created successfully (ID: {}): **{}**'.format(
                contact.pk, contact.full_name,
            ),
        ]
        if contact.job_title:
            lines.append(f'Title: {contact.job_title}')
        if contact.company:
            lines.append(f'Company: {contact.company}')
        if contact.email:
            lines.append(f'Email: {contact.email}')
        if contact.phone:
            lines.append(f'Phone: {contact.phone}')
        if contact.tags:
            lines.append(f'Tags: {contact.tags}')
        if contact.notes:
            lines.append(f'Notes: {contact.notes[:200]}')
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Strip action prefix -- find "contact" or "person" after verb
        m = re.search(
            r'\b(?:create|add|new)\s+(?:a\s+|an\s+)?(?:new\s+)?'
            r'(?:contact|person)\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        body = re.sub(
            r'^(?:for|named|called|about)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Extract structured fields via keyword:value patterns
        _end = r'(?=\s+(?:company|title|tags?|notes?|phone|email)|$)'
        field_patterns = [
            ('email', r'\bemail\s*[:=]\s*(\S+@\S+\.\S+)'),
            ('email', r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
            ('phone', r'\bphone\s*[:=]\s*(.+?)' + _end),
            ('phone', r'\b(?:tel|mobile|cell|phone)\s*[:=]\s*(.+?)' + _end),
            ('company', r'\bcompany\s*[:=]\s*(.+?)' + _end),
            ('job_title', r'\btitle\s*[:=]\s*(.+?)' + _end),
            ('tags', r'\btags?\s*[:=]\s*(.+?)' + _end),
            ('notes', r'\bnotes?\s*[:=]\s*(.+?)$'),
        ]
        for key, pattern in field_patterns:
            if key in params and params[key]:
                continue
            m = re.search(pattern, body, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if key == 'email':
                    val = val.lower()
                if val:
                    params[key] = val
                    body = _remove_match(body, m)

        # 3. Extract company from natural language ("at X", "from X")
        if 'company' not in params:
            m = re.search(
                r'\b(?:at|from)\s+'
                r'([A-Z][A-Za-z0-9\s]{1,40}?)'
                r'(?=\s+(?:tags?|notes?|phone|email|title)|$)',
                body,
            )
            if m:
                cand = m.group(1).strip()
                if len(cand) > 1:
                    params['company'] = cand
                    body = _remove_match(body, m)

        # 4. Extract standalone phone number
        if 'phone' not in params:
            m = re.search(
                r'\b(\+?\d[\d\s\-().]{6,20}\d)\b', body,
            )
            if m:
                params['phone'] = m.group(1).strip()
                body = _remove_match(body, m)

        # 5. Remaining body -> full_name
        name = _extract_title(body)
        if name:
            params['full_name'] = name

        return params


@register
class UpdateContactAction(BaseAction):
    """Update a contact's fields from natural language."""
    action_type = 'update_contact'
    keywords = frozenset({
        'update', 'edit', 'change', 'modify', 'set', 'rename',
        'contact', 'person', 'phone', 'email', 'company',
        'notes', 'tags', 'mobile', 'number',
    })
    patterns = [
        re.compile(r'(update|edit|change|modify|rename|set)\b'),
        re.compile(r"(contact|person).*(?:'s\s+)?(?:phone|email|company|number|mobile|tag)"),
        re.compile(r"(?:phone|email|mobile|telephone|company|organization|notes?|tags?|job.?title|designation)\s+(?:number\s+)?(?:to|as)"),
        re.compile(r"(?:phone|email|mobile|telephone|company|organization|notes?|tags?|job.?title|designation)\s*:"),
    ]

    def _parse(self, text):
        """Parse text → ``{name, updates: [(field, value), ...]}``."""
        params = {'updates': []}
        body = text

        # 1. Strip action verb
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:update|edit|change|modify|rename|set)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Strip entity type
        body = re.sub(r'^(?:contact|person)\s+', '', body, flags=re.IGNORECASE).strip()

        keys = sorted(_CONTACT_UPDATE_FIELDS.keys(), key=len, reverse=True)
        field_alt = '|'.join(re.escape(k) for k in keys)

        # 3a. Format "field of name to value" (single update)
        m = re.search(
            r'\b(' + field_alt + r')\s+of\s+(.+?)\s+(?:to|as)\s+(.+?)$',
            body, flags=re.IGNORECASE,
        )
        if m:
            raw_field = m.group(1).lower()
            params['updates'].append((_CONTACT_UPDATE_FIELDS[raw_field], m.group(3).strip()))
            params['name'] = _extract_title(m.group(2).strip())
            return params

        # 3b. Extract all "field: value" / "field to value" pairs
        pair_re = r'\b(' + field_alt + r')(?:\s+(?:to|as|is|=)|:\s*)\s*'
        matches = list(re.finditer(pair_re, body, flags=re.IGNORECASE))
        if matches:
            name_text = body[:matches[0].start()].strip()
            params['name'] = _extract_title(name_text)
            for i, m in enumerate(matches):
                raw_field = m.group(1).lower()
                val_start = m.end()
                val_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
                value = body[val_start:val_end].strip().rstrip('. ')
                if value:
                    params['updates'].append((_CONTACT_UPDATE_FIELDS[raw_field], value))
            return params

        # 4. Fallback: extract phone/email from body
        m = re.search(r'\b(\+?\d[\d\s\-().]{6,20}\d)\b', body)
        if m:
            params['updates'].append(('phone', m.group(1).strip()))
            params['name'] = _extract_title(body[:m.start()])
            return params

        m = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', body)
        if m:
            params['updates'].append(('email', m.group(1).lower()))
            params['name'] = _extract_title(body[:m.start()])
            return params

        # 5. No field-value identified — remaining body is just a name
        params['name'] = _extract_title(body)
        return params

    def execute(self, text, user):
        params = self._parse(text)
        name = params.get('name', '').strip()
        if not name:
            return 'I need a contact name to update. Which contact should I update?'

        updates = params.get('updates', [])
        if not updates:
            return (
                f'I found contact "{name}", but what would you like to change? '
                f'You can update phone, email, company, job title, tags, or notes.'
            )

        from contacts.models import Contact
        from django.db import transaction
        from django.core.exceptions import ValidationError

        # Find the contact
        qs = user.contacts.all()
        contact = qs.filter(full_name__icontains=name).first()
        if not contact:
            contact = qs.filter(full_name__iexact=name).first()
        if not contact:
            return f'I could not find a contact matching "{name}".'

        # Normalise and set all field values
        changed = []
        for field, raw_value in updates:
            try:
                norm_field, norm_value = _normalise_contact_field_value(
                    field, str(raw_value), user,
                )
            except ValueError as e:
                return str(e)
            setattr(contact, norm_field, norm_value)
            changed.append((norm_field, norm_value))

        # Save once with all changes
        try:
            with transaction.atomic():
                contact.full_clean()
                contact.save()
                contact.refresh_from_db()
        except ValidationError as e:
            error_details = []
            for fld, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{fld}: {err}')
            return (
                'Failed to update contact — validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception('Failed to update contact for user=%s', user)
            return f'Failed to update contact: {e}'

        lines = [f'Contact **"{contact.full_name}"** updated.']
        for norm_field, norm_value in changed:
            readable = norm_field.replace('_', ' ').title()
            lines.append(f'{readable}: {norm_value}')
        return '  \n'.join(lines)


@register
class DeleteContactAction(BaseAction):
    action_type = 'delete_contact'
    keywords = frozenset({'delete', 'remove', 'erase', 'contact', 'person'})
    patterns = [
        re.compile(r'(delete|remove|erase)\b'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:delete|remove|erase)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^(?:contact|person)\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+(?:contact|person)\s*$', '', body, flags=re.IGNORECASE).strip()
        return _extract_title(body)

    def execute(self, text, user):
        name = self._parse(text)
        if not name:
            return 'Contact not found.'

        from contacts.models import Contact

        qs = user.contacts.all()
        contact = qs.filter(full_name__icontains=name).first()
        if not contact:
            contact = qs.filter(full_name__iexact=name).first()
        if not contact:
            return 'Contact not found.'

        from django.db import transaction
        try:
            with transaction.atomic():
                contact.delete()
        except Exception as e:
            logger.exception('Failed to delete contact for user=%s', user)
            return f'Failed to delete contact: {e}'

        # Verify deletion
        if Contact.objects.filter(pk=contact.pk).exists():
            return 'Failed to delete contact.'

        return 'Contact deleted successfully.'


@register
class ViewContactAction(BaseAction):
    action_type = 'view_contact'
    keywords = frozenset({
        'contact', 'person', 'show', 'view', 'open', 'details',
        'tell', 'about', 'who', 'give', 'information',
    })
    patterns = [
        re.compile(r'(tell|show).*(about)'),
        re.compile(r'^who\s+is\b'),
        re.compile(r'(show|view|open).*(details?|info|information)'),
        re.compile(r'^(contact|give)\b'),
        re.compile(r'(details?|info|information)\s+(about|on|for|of)'),
    ]

    def _parse(self, text):
        body = text

        # Strip any leading intent prefix
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:'
            r'tell\s+(?:me\s+)?(?:about|everything\s+about)\s+|'
            r'show\s+(?:me\s+)?(?:details?\s+(?:of|for|about|on)\s+|'
            r'(?:everything|full|complete)\s+about\s+|about\s+)|'
            r'who\s+is\s+|'
            r'contact\s+|'
            r'give\s+(?:me\s+)?(?:information\s+(?:about|on)\s+|'
            r'details?\s+(?:about|on)\s+)?|'
            r'information\s+(?:about|on)\s+|'
            r'details?\s+(?:about|on|for|of)\s+|'
            r'about\s+|'
            r'(?:view|open|see|display)\s+'
            r')',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # Strip remaining noise words anywhere
        body = re.sub(
            r'\b(?:about|details?|info|information|everything|full|'
            r'complete|my|the|a|an|contact|person|entry|record|profile)\b\s*',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # Strip trailing context clauses
        body = re.sub(
            r"\s+(?:in|from|of|for|under)\s+(?:my|the|your)?\s*"
            r"(?:contacts?|crm|database|system|directory|roster|list|address\s*book)?\s*$",
            '', body, flags=re.IGNORECASE,
        ).strip()

        # Trim punctuation and normalize whitespace
        body = re.sub(r'^[\s"\'.,;:!?\-]+|[\s"\'.,;:!?\-]+$', '', body).strip()
        body = re.sub(r'\s+', ' ', body).strip()

        return body

    def _related_leads(self, contact, user):
        from leads.models import Lead
        from django.db.models import Q
        q = Q()
        if contact.email:
            q |= Q(email__iexact=contact.email)
        if contact.phone:
            q |= Q(phone=contact.phone)
        if contact.full_name:
            parts = contact.full_name.split()
            for part in parts:
                if len(part) > 2:
                    q |= Q(contact_person__icontains=part)
        return user.leads.filter(q).distinct()[:10]

    def _related_tasks(self, contact, user):
        return contact.tasks.all()[:10]

    def _related_events(self, contact, user):
        return contact.events.all()[:10]

    def _related_notifications(self, contact, user):
        from django.db.models import Q
        q = Q()
        if contact.full_name:
            parts = contact.full_name.split()
            for part in parts:
                if len(part) > 2:
                    q |= Q(title__icontains=part) | Q(message__icontains=part)
        if contact.email:
            q |= Q(title__icontains=contact.email) | Q(message__icontains=contact.email)
        return user.notifications.filter(q).distinct()[:10] if q else []

    def _related_campaigns(self, contact, user):
        from django.db.models import Q
        q = Q()
        if contact.full_name:
            parts = contact.full_name.split()
            for part in parts:
                if len(part) > 2:
                    q |= Q(name__icontains=part) | Q(subject__icontains=part)
        if contact.email:
            q |= Q(name__icontains=contact.email) | Q(subject__icontains=contact.email)
        return user.campaigns.filter(q).distinct()[:10] if q else []

    def execute(self, text, user):
        name = self._parse(text)
        if not name:
            return 'I need a contact name. Which contact would you like to view?'

        from django.db.models import Q
        from contacts.models import Contact

        qs = user.contacts.all()
        contact = qs.filter(
            Q(full_name__icontains=name) |
            Q(email__icontains=name) |
            Q(phone__icontains=name)
        ).first()
        if not contact:
            return f'I could not find a contact matching "{name}".'

        created = contact.created_at.strftime('%b %d, %Y') if contact.created_at else '—'
        updated = contact.updated_at.strftime('%b %d, %Y') if contact.updated_at else '—'

        rows = [
            f'| **Name**     | {contact.full_name}',
            f'| **Email**    | {contact.email or "—"}',
            f'| **Phone**    | {contact.phone or "—"}',
            f'| **Company**  | {contact.company or "—"}',
            f'| **Position** | {contact.job_title or "—"}',
            f'| **Tags**     | {contact.tags or "—"}',
            f'| **Notes**    | {contact.notes or "—"}',
            f'| **Created**  | {created}',
            f'| **Updated**  | {updated}',
        ]
        parts = [f'### Contact Details\n' + '\n'.join(rows)]

        # ── Related Leads ──
        related_leads = self._related_leads(contact, user)
        if related_leads:
            lead_rows = []
            for l in related_leads:
                status = l.get_status_display()
                priority = l.get_priority_display()
                rev = f'${l.expected_revenue:,.2f}' if l.expected_revenue else '—'
                lead_rows.append(
                    f'| **{l.lead_name}** | {status} | {priority} | {rev}'
                )
            header = '| Lead | Status | Priority | Expected Revenue |'
            sep = '|---|---|---|---|'
            parts.append(
                '#### Related Leads\n' + header + '\n' + sep + '\n' + '\n'.join(lead_rows)
            )

        # ── Related Tasks ──
        related_tasks = self._related_tasks(contact, user)
        if related_tasks:
            task_rows = []
            for t in related_tasks:
                due = t.due_date.strftime('%b %d') if t.due_date else '—'
                task_rows.append(
                    f'| **{t.title}** | {t.get_status_display()} | {t.get_priority_display()} | {due}'
                )
            header = '| Task | Status | Priority | Due |'
            sep = '|---|---|---|---|'
            parts.append(
                '#### Related Tasks\n' + header + '\n' + sep + '\n' + '\n'.join(task_rows)
            )

        # ── Related Events ──
        related_events = self._related_events(contact, user)
        if related_events:
            event_rows = []
            for e in related_events:
                d = e.start_date.strftime('%b %d') if e.start_date else '—'
                t = e.start_time.strftime('%I:%M %p').lstrip('0') if e.start_time else '—'
                event_rows.append(
                    f'| **{e.title}** | {d} | {t} | {e.get_event_type_display()} | {e.get_status_display()}'
                )
            header = '| Event | Date | Time | Type | Status |'
            sep = '|---|---|---|---|---|'
            parts.append(
                '#### Related Events\n' + header + '\n' + sep + '\n' + '\n'.join(event_rows)
            )

        # ── Related Notifications ──
        related_notifications = self._related_notifications(contact, user)
        if related_notifications:
            notif_rows = []
            for n in related_notifications:
                read = '✓' if n.is_read else '○'
                notif_rows.append(
                    f'| {read} | **{n.title}** | {n.created_at.strftime("%b %d")}'
                )
            header = '| | Notification | Created |'
            sep = '|---|---|---|'
            parts.append(
                '#### Related Notifications\n' + header + '\n' + sep + '\n' + '\n'.join(notif_rows)
            )

        # ── Related Campaigns ──
        related_campaigns = self._related_campaigns(contact, user)
        if related_campaigns:
            camp_rows = []
            for c in related_campaigns:
                camp_rows.append(
                    f'| **{c.name}** | {c.get_status_display()} | {c.created_at.strftime("%b %d")}'
                )
            header = '| Campaign | Status | Created |'
            sep = '|---|---|---|'
            parts.append(
                '#### Related Campaigns\n' + header + '\n' + sep + '\n' + '\n'.join(camp_rows)
            )

        return '\n\n'.join(parts)


@register
class CreateLeadAction(BaseAction):
    action_type = 'create_lead'
    keywords = frozenset({'create', 'add', 'new', 'lead', 'prospect', 'deal'})
    patterns = [re.compile(r'(create|add|new).*(lead|prospect|deal)')]

    _STATUS_MAP = {
        'new': 'New', 'contacted': 'Contacted', 'qualified': 'Qualified',
        'proposal sent': 'Proposal Sent', 'proposal': 'Proposal Sent',
        'negotiation': 'Negotiation', 'won': 'Won', 'lost': 'Lost',
        'closed won': 'Won', 'closed lost': 'Lost',
    }

    _SOURCE_MAP = {
        'website': 'Website', 'referral': 'Referral',
        'linkedin': 'LinkedIn', 'facebook': 'Facebook',
        'instagram': 'Instagram', 'cold email': 'Cold Email',
        'email': 'Cold Email', 'event': 'Event',
        'other': 'Other', 'call': 'Other', 'phone': 'Other',
    }

    def execute(self, text, user):
        params = self._parse(text)
        lead_name = params.get('lead_name', '').strip()
        if not lead_name:
            return (
                'I need a lead name to create a lead. '
                'What should the lead be called?'
            )

        from leads.models import Lead
        from django.db import transaction
        from django.core.exceptions import ValidationError

        sid = None
        try:
            with transaction.atomic():
                sid = transaction.savepoint()
                lead = Lead(
                    owner=user,
                    lead_name=lead_name,
                    company=params.get('company', ''),
                    contact_person=params.get('contact_person', ''),
                    email=params.get('email', ''),
                    phone=params.get('phone', ''),
                    status=params.get('status', 'New'),
                    priority=params.get('priority', 'Medium'),
                    source=params.get('source', 'Website'),
                    expected_revenue=params.get('revenue'),
                    notes=params.get('notes', ''),
                )
                lead.full_clean()
                lead.save()
                lead.refresh_from_db()

                # ── Post-save existence verification ──
                saved_pk = lead.pk
                try:
                    reloaded = Lead.objects.get(pk=saved_pk)
                except Lead.DoesNotExist:
                    transaction.savepoint_rollback(sid)
                    logger.error(
                        'Lead pk=%s was NOT committed — DB get() returned None. '
                        'user=%s msg=%s',
                        saved_pk, user, text[:120],
                    )
                    return (
                        'Failed to create lead: the record was not persisted to '
                        'the database. Please try again.'
                    )

        except ValidationError as e:
            logger.error(
                'Lead validation failed for user=%s msg=%s error=%s',
                user, text[:120], e.message_dict,
            )
            error_details = []
            for field, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{field}: {err}')
            return (
                'Failed to create lead — validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception(
                'Failed to create lead for user=%s msg=%s', user, text[:120],
            )
            if sid is not None:
                logger.warning('Transaction rolled back at savepoint %s', sid)
            return f'Failed to create lead: {e}'

        lines = [f'Lead created successfully: **{lead.lead_name}**']
        if lead.company:
            lines.append(f'Company: {lead.company}')
        if lead.contact_person:
            lines.append(f'Contact: {lead.contact_person}')
        if lead.email:
            lines.append(f'Email: {lead.email}')
        if lead.phone:
            lines.append(f'Phone: {lead.phone}')
        lines.append(f'Status: {lead.status}')
        lines.append(f'Priority: {lead.priority}')
        if lead.source:
            lines.append(f'Source: {lead.source}')
        if lead.expected_revenue is not None:
            lines.append(f'Expected Revenue: ${lead.expected_revenue}')
        if lead.notes:
            lines.append(f'Notes: {lead.notes[:200]}')
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Extract lead-specific priority (has 'Urgent' as separate value)
        priority, body = self._extract_lead_priority(body)
        if priority:
            params['priority'] = priority

        # 2. Strip action prefix — find "lead", "prospect", or "deal" after verb
        m = re.search(
            r'\b(?:create|add|new)\s+(?:a\s+|an\s+)?(?:new\s+)?'
            r'(?:lead|prospect|deal)\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        # Also strip leading "for " / "named " / "called " after prefix
        body = re.sub(
            r'^(?:for|named|called|about)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 3. Extract structured fields via keyword:value patterns
        #    Using lookahead (?=...) so trailing keywords aren't consumed.
        _end = r'(?=\s+(?:status|source|priority|revenue|company|contact|notes?|phone|email)|$)'
        field_patterns = [
            ('email', r'\bemail\s*[:=]\s*(\S+@\S+\.\S+)'),
            ('email', r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
            ('phone', r'\bphone\s*[:=]\s*(.+?)' + _end),
            ('phone', r'\b(?:tel|mobile|cell|phone)\s*[:=]\s*(.+?)' + _end),
            ('source', r'\bsource\s*[:=]\s*(.+?)' + _end),
            ('status', r'\bstatus\s*[:=]\s*(.+?)' + _end),
            ('revenue', r'\b(?:expected\s+)?revenue\s*[:=]\s*\$?([\d,]+(?:\.\d{1,2})?)'),
            ('revenue', r'\b(?:expected\s+)?revenue\s*(?:of|:)?\s*\$?([\d,]+(?:\.\d{1,2})?)'),
            ('company', r'\bcompany\s*[:=]\s*(.+?)' + _end),
            ('contact_person', r'\bcontact\s*(?:person\s+)?[:=]\s*(.+?)' + _end),
            ('notes', r'\bnotes?\s*[:=]\s*(.+?)$'),
        ]
        for key, pattern in field_patterns:
            if key in params and params[key]:
                continue
            m = re.search(pattern, body, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if key == 'source':
                    val = self._normalise_source(val)
                elif key == 'status':
                    val = self._normalise_status(val)
                elif key == 'revenue':
                    val = self._parse_revenue(val)
                elif key == 'email':
                    val = val.lower()
                if val:
                    params[key] = val
                    body = _remove_match(body, m)

        # 4. Extract company/contact from natural language (not keyworded)
        if 'company' not in params:
            m = re.search(r'\b(?:at|from|of)\s+([A-Z][A-Za-z0-9\s]{1,40}?)(?:\s+(?:contact|status|source|priority|revenue|notes|phone|email)|$)', body)
            if m:
                cand = m.group(1).strip()
                if len(cand) > 1:
                    params['company'] = cand
                    body = _remove_match(body, m)

        # 5. Extract phone pattern (standalone phone number)
        if 'phone' not in params:
            m = re.search(
                r'\b(\+?\d[\d\s\-().]{6,20}\d)\b', body,
            )
            if m:
                params['phone'] = m.group(1).strip()
                body = _remove_match(body, m)

        # 6. Source from context words
        if 'source' not in params:
            src = self._detect_source_in_text(body)
            if src:
                params['source'] = src
                # Don't remove from body — the source word might be part of the name

        # 7. Remaining body → lead name
        name = _extract_title(body)
        if name:
            params['lead_name'] = name

        return params

    @staticmethod
    def _extract_lead_priority(text):
        """Lead-specific priority extraction (includes 'Urgent' as separate value)."""
        text_lower = text.lower()
        rules = [
            (r'\burgent\b', 'Urgent'),
            (r'\bhigh\s+priority\b', 'High'),
            (r'\bpriority\s+high\b', 'High'),
            (r'\bcritical\b', 'High'),
            (r'\bmedium\s+priority\b', 'Medium'),
            (r'\bpriority\s+medium\b', 'Medium'),
            (r'\bnormal\s+priority\b', 'Medium'),
            (r'\blow\s+priority\b', 'Low'),
            (r'\bpriority\s+low\b', 'Low'),
            (r'\bminor\b', 'Low'),
        ]
        for pattern, value in rules:
            m = re.search(pattern, text_lower)
            if m:
                return (value, _remove_match(text, m))
        return (None, text)

    @staticmethod
    def _normalise_source(val):
        val = val.strip().lower()
        for key, mapped in CreateLeadAction._SOURCE_MAP.items():
            if val == key or val.startswith(key):
                return mapped
        return val.title()

    @staticmethod
    def _normalise_status(val):
        val = val.strip().lower()
        for key, mapped in CreateLeadAction._STATUS_MAP.items():
            if val == key or val.startswith(key):
                return mapped
        return val.title()

    @staticmethod
    def _parse_revenue(val):
        val = val.strip().replace(',', '')
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _detect_source_in_text(text):
        text_lower = text.lower()
        for key, mapped in CreateLeadAction._SOURCE_MAP.items():
            if key in text_lower:
                return mapped
        return None


@register
class UpdateLeadAction(BaseAction):
    """Update a lead's fields from natural language."""
    action_type = 'update_lead'
    keywords = frozenset({
        'update', 'edit', 'change', 'modify', 'set', 'move',
        'lead', 'prospect', 'deal',
        'qualified', 'won', 'lost', 'contacted',
    })
    patterns = [
        re.compile(r'\b(update|edit|change|modify|set|move)\b.*(lead|prospect|deal)'),
        re.compile(r'(lead|prospect|deal).*(?:status|priority|source)\s+(?:to|as|is)'),
        re.compile(r'(lead|prospect|deal).*(qualified|won|lost|contacted)'),
    ]

    _STATUS_MAP = {
        'new': 'New', 'contacted': 'Contacted', 'qualified': 'Qualified',
        'proposal sent': 'Proposal Sent', 'proposal': 'Proposal Sent',
        'negotiation': 'Negotiation', 'won': 'Won', 'lost': 'Lost',
        'closed won': 'Won', 'closed lost': 'Lost',
    }

    def _parse(self, text):
        """Parse text → ``{name, updates: [(field, value), ...]}``."""
        params = {'updates': []}
        body = text

        # 1. Strip action verb
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:update|edit|change|modify|rename|set|move)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Strip entity type
        body = re.sub(r'^(?:lead|prospect|deal)\s+', '', body, flags=re.IGNORECASE).strip()

        keys = sorted(_LEAD_UPDATE_FIELDS.keys(), key=len, reverse=True)
        field_alt = '|'.join(re.escape(k) for k in keys)

        # 3a. Format "field of name to value" (single update)
        m = re.search(
            r'\b(' + field_alt + r')\s+of\s+(.+?)\s+(?:to|as)\s+(.+?)$',
            body, flags=re.IGNORECASE,
        )
        if m:
            raw_field = m.group(1).lower()
            params['updates'].append((_LEAD_UPDATE_FIELDS[raw_field], m.group(3).strip()))
            params['name'] = _extract_title(m.group(2).strip())
            return params

        # 3b. Extract all "field value" / "field to value" / "field: value" pairs
        pair_re = r'\b(' + field_alt + r')(?:\s+(?:to|as|is|=)|:\s*|\s+)(?=\S)'
        matches = list(re.finditer(pair_re, body, flags=re.IGNORECASE))
        if matches:
            name_text = body[:matches[0].start()].strip()
            params['name'] = _extract_title(name_text)
            for i, m in enumerate(matches):
                raw_field = m.group(1).lower()
                val_start = m.end()
                val_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
                value = body[val_start:val_end].strip().rstrip('. ')
                if value:
                    params['updates'].append((_LEAD_UPDATE_FIELDS[raw_field], value))
            return params

        # 4. Fallback: check for status-only: "<name> qualified/won/lost/contacted"
        m = re.search(r'\b(qualified|won|lost|contacted)\b', body, flags=re.IGNORECASE)
        if m:
            params['updates'].append(('status', m.group(1)))
            params['name'] = _extract_title(body[:m.start()].strip())
            return params

        # 5. No field-value identified — remaining body is just the name
        params['name'] = _extract_title(body)
        return params

    def execute(self, text, user):
        params = self._parse(text)
        name = params.get('name', '').strip()
        if not name:
            return 'I need a lead name to update. Which lead should I update?'

        updates = params.get('updates', [])
        if not updates:
            return (
                f'I found lead "{name}", but what would you like to change? '
                f'You can update status, priority, source, company, email, phone, '
                f'contact person, revenue, or notes.'
            )

        from leads.models import Lead
        from django.db import transaction
        from django.core.exceptions import ValidationError

        # Find the lead
        qs = user.leads.all()
        lead = qs.filter(lead_name__icontains=name).first()
        if not lead:
            lead = qs.filter(lead_name__iexact=name).first()
        if not lead:
            return f'I could not find a lead matching "{name}".'

        # Normalise and set all field values
        changed = []
        for field, raw_value in updates:
            try:
                norm_field, norm_value = _normalise_lead_field_value(
                    field, str(raw_value), user,
                )
            except ValueError as e:
                return str(e)
            setattr(lead, norm_field, norm_value)
            changed.append((norm_field, norm_value))

        # Save once with all changes
        try:
            with transaction.atomic():
                lead.full_clean()
                lead.save()
                lead.refresh_from_db()
        except ValidationError as e:
            error_details = []
            for fld, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{fld}: {err}')
            return (
                'Failed to update lead — validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception('Failed to update lead for user=%s', user)
            return f'Failed to update lead: {e}'

        lines = [f'Lead **"{lead.lead_name}"** updated.']
        for norm_field, norm_value in changed:
            readable = norm_field.replace('_', ' ').title()
            lines.append(f'{readable}: {norm_value}')
        return '  \n'.join(lines)

    @staticmethod
    def _normalise_status(val):
        """Map raw status string to Lead STATUS_CHOICES value."""
        val = val.strip().lower()
        for key, mapped in UpdateLeadAction._STATUS_MAP.items():
            if val == key or val.startswith(key) or key.startswith(val):
                return mapped
        return val.title()


@register
class DeleteLeadAction(BaseAction):
    action_type = 'delete_lead'
    keywords = frozenset({'delete', 'remove', 'erase', 'cancel', 'lead', 'prospect', 'deal'})
    patterns = [
        re.compile(r'(delete|remove|erase|cancel)\b'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:delete|remove|erase|cancel)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^(?:lead|prospect|deal)\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+(?:lead|prospect|deal)\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'\s+from\s+(?:the\s+)?(?:crm|database|system|records)\s*$',
            '', body, flags=re.IGNORECASE,
        ).strip()
        return _extract_title(body)

    def execute(self, text, user):
        lead_name = self._parse(text)
        if not lead_name:
            return 'Lead not found.'

        from leads.models import Lead

        qs = user.leads.all()
        lead = qs.filter(lead_name__icontains=lead_name).first()
        if not lead:
            lead = qs.filter(lead_name__iexact=lead_name).first()
        if not lead:
            return 'Lead not found.'

        from django.db import transaction
        try:
            with transaction.atomic():
                lead.delete()
        except Exception as e:
            logger.exception('Failed to delete lead for user=%s', user)
            return f'Failed to delete lead: {e}'

        # Verify deletion
        if Lead.objects.filter(pk=lead.pk).exists():
            return 'Failed to delete lead.'

        return 'Lead deleted successfully.'


@register
class ViewLeadAction(BaseAction):
    action_type = 'view_lead'
    keywords = frozenset({
        'lead', 'prospect', 'deal', 'show', 'view', 'open', 'details',
        'tell', 'about',
    })
    patterns = [
        re.compile(r'(show|view|open).*(lead|prospect|deal)'),
        re.compile(r'(lead|prospect|deal).*(details|info|information|about)'),
        re.compile(r'(tell|show).*(about).*(lead|prospect|deal)'),
        re.compile(r'^(lead|prospect|deal)\b'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:show|view|open)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(
            r'^(?:tell\s+me\s+about|tell\s+about|tell\s+me)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^about\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'^(?:lead|prospect|deal)\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'^(?:details?|info|information)(?:\s+(?:for|about|on)\s+|\s+)',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'\s+(?:lead|prospect|deal)\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+(?:details?|info|information)\s*$', '', body, flags=re.IGNORECASE).strip()
        return _extract_title(body)

    def execute(self, text, user):
        lead_name = self._parse(text)
        if not lead_name:
            return 'I need a lead name. Which lead would you like to view?'

        from leads.models import Lead

        qs = user.leads.all()
        lead = qs.filter(lead_name__icontains=lead_name).first()
        if not lead:
            lead = qs.filter(lead_name__iexact=lead_name).first()
        if not lead:
            return f'I could not find a lead matching "{lead_name}".'

        revenue = f'${lead.expected_revenue:,.2f}' if lead.expected_revenue else '—'
        assigned_to = lead.assigned_user.get_full_name() or str(lead.assigned_user) if lead.assigned_user else '—'
        created = lead.created_at.strftime('%b %d, %Y') if lead.created_at else '—'
        updated = lead.updated_at.strftime('%b %d, %Y') if lead.updated_at else '—'

        rows = [
            f'| **Name**            | {lead.lead_name}',
            f'| **Email**           | {lead.email or "—"}',
            f'| **Phone**           | {lead.phone or "—"}',
            f'| **Status**          | {lead.get_status_display()}',
            f'| **Priority**        | {lead.get_priority_display()}',
            f'| **Source**          | {lead.get_source_display()}',
            f'| **Expected Revenue**| {revenue}',
            f'| **Assigned To**     | {assigned_to}',
            f'| **Notes**           | {lead.notes or "—"}',
            f'| **Created**         | {created}',
            f'| **Updated**         | {updated}',
        ]
        table = '\n'.join(rows)
        return f'### Lead Details\n{table}'


@register
class AssignLeadAction(BaseAction):
    action_type = 'assign_lead'
    keywords = frozenset({'assign', 'reassign', 'transfer', 'lead'})
    patterns = [re.compile(r'(assign|reassign|transfer).*(lead)')]

    def extract_params(self, text):
        return {}


def _extract_event_times(text):
    """Extract start and end times from *text*.

    Returns ``(start_time, end_time, cleaned_text)``.
    Handles ``from 3pm to 4pm``, ``3pm - 4pm``, ``at 3pm``.
    """
    from datetime import time as time_class

    body = text
    text_lower = text.lower()

    # "from 3pm to 4pm", "from 3:00 PM until 4:00 PM"
    m = re.search(
        r'\bfrom\s+'
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*'
        r'(?:to|until|-)\s*'
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        text_lower,
    )
    if m:
        hour1 = int(m.group(1))
        min1 = int(m.group(2)) if m.group(2) else 0
        ampm1 = m.group(3).lower() if m.group(3) else None
        hour2 = int(m.group(4))
        min2 = int(m.group(5)) if m.group(5) else 0
        ampm2 = m.group(6).lower()
        if ampm1 == 'pm' and hour1 < 12:
            hour1 += 12
        elif ampm1 == 'am' and hour1 == 12:
            hour1 = 0
        if ampm2 == 'pm' and hour2 < 12:
            hour2 += 12
        elif ampm2 == 'am' and hour2 == 12:
            hour2 = 0
        try:
            start = time_class(hour1, min1)
            end = time_class(hour2, min2)
            return (start, end, _remove_match(text, m))
        except ValueError:
            pass

    # "3pm - 4:30pm", "3:00 PM - 4:00 PM"
    m = re.search(
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*-\s*'
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        text_lower,
    )
    if m:
        hour1 = int(m.group(1))
        min1 = int(m.group(2)) if m.group(2) else 0
        ampm1 = m.group(3).lower() if m.group(3) else None
        hour2 = int(m.group(4))
        min2 = int(m.group(5)) if m.group(5) else 0
        ampm2 = m.group(6).lower()
        if ampm1 == 'pm' and hour1 < 12:
            hour1 += 12
        elif ampm1 == 'am' and hour1 == 12:
            hour1 = 0
        if ampm2 == 'pm' and hour2 < 12:
            hour2 += 12
        elif ampm2 == 'am' and hour2 == 12:
            hour2 = 0
        try:
            start = time_class(hour1, min1)
            end = time_class(hour2, min2)
            return (start, end, _remove_match(text, m))
        except ValueError:
            pass

    # Single time (start only)
    t, body = _parse_time_from_text(text)
    return (t, None, body)


@register
class CreateEventAction(BaseAction):
    action_type = 'create_event'
    keywords = frozenset({
        'create', 'add', 'schedule', 'new', 'event', 'meeting',
        'appointment', 'call', 'reminder',
    })
    patterns = [
        re.compile(r'(create|add|schedule|new).*(event|meeting|appointment|call|reminder)'),
    ]

    _STATUS_MAP = {
        'scheduled': 'scheduled', 'confirmed': 'scheduled',
        'completed': 'completed', 'done': 'completed',
        'cancelled': 'cancelled', 'canceled': 'cancelled',
        'cancel': 'cancelled',
    }

    _EVENT_TYPE_MAP = {
        'meeting': 'meeting',
        'call': 'call',
        'phone': 'call',
        'phone call': 'call',
        'reminder': 'reminder',
        'personal': 'personal',
    }

    def execute(self, text, user):
        params = self._parse(text)
        title = params.get('title', '').strip()
        if not title:
            return (
                'I need a title to create an event. '
                'What should the event be called?'
            )

        start_date = params.get('start_date') or date.today()

        from calendars.models import Event
        from django.db import transaction
        from django.core.exceptions import ValidationError

        sid = None
        try:
            with transaction.atomic():
                sid = transaction.savepoint()
                event = Event(
                    owner=user,
                    title=title,
                    description=params.get('description', ''),
                    start_date=start_date,
                    start_time=params.get('start_time'),
                    end_time=params.get('end_time'),
                    location=params.get('location', ''),
                    status=params.get('status', 'scheduled'),
                    event_type=params.get('event_type', 'meeting'),
                )
                event.full_clean()
                event.save()
                event.refresh_from_db()

                saved_pk = event.pk
                try:
                    reloaded = Event.objects.get(pk=saved_pk)
                except Event.DoesNotExist:
                    transaction.savepoint_rollback(sid)
                    logger.error(
                        'Event pk=%s was NOT committed -- DB get() returned None. '
                        'user=%s msg=%s',
                        saved_pk, user, text[:120],
                    )
                    return (
                        'Failed to create event: the record was not persisted '
                        'to the database. Please try again.'
                    )

        except ValidationError as e:
            logger.error(
                'Event validation failed for user=%s msg=%s error=%s',
                user, text[:120], e.message_dict,
            )
            error_details = []
            for field, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{field}: {err}')
            return (
                'Failed to create event -- validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception(
                'Failed to create event for user=%s msg=%s', user, text[:120],
            )
            if sid is not None:
                logger.warning('Transaction rolled back at savepoint %s', sid)
            return f'Failed to create event: {e}'

        lines = [
            'Event created successfully (ID: {}): **{}**'.format(
                event.pk, event.title,
            ),
        ]
        if event.start_date:
            label = event.start_date.strftime('%b %d, %Y')
            if event.start_time:
                label += event.start_time.strftime(' at %I:%M %p').lstrip('0')
            lines.append(f'When: {label}')
        if event.end_time:
            lines.append(
                'End: {}'.format(event.end_time.strftime('%I:%M %p').lstrip('0')),
            )
        if event.location:
            lines.append(f'Location: {event.location}')
        if event.description:
            lines.append(f'Description: {event.description[:200]}')
        lines.append(f'Status: {event.status.title()}')
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Strip action prefix
        m = re.search(
            r'\b(?:create|add|schedule|new)\s+(?:a\s+|an\s+)?(?:new\s+)?'
            r'(?:event|meeting|appointment|call|reminder)\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        body = re.sub(
            r'^(?:for|named|called|about)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Extract structured fields via keyword:value patterns
        _end = r'(?=\s+(?:location|status|type|notes?|description)|$)'
        field_patterns = [
            ('location', r'\blocation\s*[:=]\s*(.+?)' + _end),
            ('status', r'\bstatus\s*[:=]\s*(.+?)' + _end),
            ('event_type', r'\b(?:event\s+)?type\s*[:=]\s*(.+?)' + _end),
            ('description', r'\bdescription\s*[:=]\s*(.+?)$'),
            ('notes', r'\bnotes?\s*[:=]\s*(.+?)$'),
        ]
        for key, pattern in field_patterns:
            if key in params and params[key]:
                continue
            m = re.search(pattern, body, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if key == 'status':
                    val = self._normalise_event_status(val)
                if key == 'event_type':
                    val = self._normalise_event_type(val)
                if val:
                    params[key] = val
                    body = _remove_match(body, m)

        # 3. Extract event type from natural language
        if 'event_type' not in params:
            text_lower = body.lower()
            if re.search(r'\b(phone|call)\b', text_lower):
                params['event_type'] = 'call'
            elif re.search(r'\breminder\b', text_lower):
                params['event_type'] = 'reminder'
            elif re.search(r'\bpersonal\b', text_lower):
                params['event_type'] = 'personal'
        if 'event_type' in params:
            params['event_type'] = self._normalise_event_type(params['event_type'])

        # 4. Extract date
        start_date, body = _parse_date_from_text(body)
        if start_date:
            params['start_date'] = start_date

        # 5. Extract start / end times
        start_time, end_time, body = _extract_event_times(body)
        if start_time:
            params['start_time'] = start_time
        if end_time:
            params['end_time'] = end_time

        # 6. Strip leading prepositions that may have been exposed after
        #    date/time removal (e.g. "for project review" -> "project review")
        body = re.sub(
            r'^(?:for|with|about|regarding|at)\s+', '',
            body, flags=re.IGNORECASE,
        ).strip()

        # 7. Remaining body -> title
        title = _extract_title(body)
        if title:
            params['title'] = title

        return params

    @staticmethod
    def _normalise_event_status(val):
        val = val.strip().lower()
        for key, mapped in CreateEventAction._STATUS_MAP.items():
            if val == key or val.startswith(key):
                return mapped
        return val

    @staticmethod
    def _normalise_event_type(val):
        val_lower = val.strip().lower()
        return CreateEventAction._EVENT_TYPE_MAP.get(val_lower, val)


@register
class UpdateEventAction(BaseAction):
    """Update an event's fields from natural language."""
    action_type = 'update_event'
    keywords = frozenset({
        'update', 'edit', 'change', 'modify', 'reschedule', 'move',
        'event', 'meeting', 'appointment', 'call', 'reminder',
    })
    patterns = [
        re.compile(r'(update|edit|change|modify|reschedule|move).*(event|meeting|appointment|call|reminder)'),
        re.compile(r'(event|meeting|appointment).*(?:to|as)\s+(?:\d|\w+)'),
        re.compile(r'(move|reschedule)\s+'),
        re.compile(r'(change|update|set|modify)\s+(?:the\s+)?'
                   r'(?:time|date|location|status|type|description|title|name|link|'
                   r'end\s*time|start\s*time)\b'),
    ]

    def _parse(self, text):
        """Parse text → ``{identifier, field, value}``."""
        params = {}
        body = text

        # 1. Strip action verb
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:update|edit|change|modify|reschedule|move)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Strip entity type
        body = re.sub(
            r'^(?:event|meeting|appointment|call|reminder)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 3. Try direct field-value extraction (supports plain "field value")
        keys = sorted(_EVENT_UPDATE_FIELDS.keys(), key=len, reverse=True)
        field_alt = '|'.join(re.escape(k) for k in keys)
        m = re.search(
            r'\b(' + field_alt + r')(?:\s+(?:to|as|is|=)|:\s*|\s+)(.+?)$',
            body, flags=re.IGNORECASE,
        )
        if m:
            raw_field = m.group(1).lower()
            params['field'] = _EVENT_UPDATE_FIELDS[raw_field]
            params['value'] = m.group(2).strip()
            params['identifier'] = _extract_title(body[:m.start()])
            return params

        # 4. Try _parse_update_field_value for possessive / "as" formats
        field, value, remaining = _parse_update_field_value(body, _EVENT_UPDATE_FIELDS)
        if field:
            params['field'] = field
            params['value'] = value
            params['identifier'] = remaining
            return params

        # 5. For "move/reschedule <event> to <time/date>":
        #    Try time first
        t, time_body = _parse_time_from_text(body)
        if t:
            params['field'] = 'start_time'
            params['value'] = t
            cleaned = re.sub(r'\b(?:to|at)\s+', '', time_body, flags=re.IGNORECASE).strip()
            params['identifier'] = _extract_title(cleaned)
            return params

        #    Then try date
        d, date_body = _parse_date_from_text(body)
        if d:
            params['field'] = 'start_date'
            params['value'] = d
            cleaned = re.sub(r'\b(?:to|on)\s+', '', date_body, flags=re.IGNORECASE).strip()
            params['identifier'] = _extract_title(cleaned)
            return params

        # 6. Check for status word at end
        m = re.search(
            r'\b(as\s+)?(completed|done|finished|cancelled|scheduled)\s*$',
            body, flags=re.IGNORECASE,
        )
        if m:
            params['field'] = 'status'
            params['value'] = m.group(2)
            params['identifier'] = _extract_title(body[:m.start()])
            return params

        # 7. Check for "to <time>" pattern (without explicit field)
        m = re.search(
            r'\b(?:to|at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b',
            body, flags=re.IGNORECASE,
        )
        if m:
            from datetime import time as time_class
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            ampm = m.group(3).lower()
            if ampm == 'pm' and hour < 12:
                hour += 12
            elif ampm == 'am' and hour == 12:
                hour = 0
            try:
                t = time_class(hour, minute)
                params['field'] = 'start_time'
                params['value'] = t
                params['identifier'] = _extract_title(body[:m.start()])
                return params
            except ValueError:
                pass

        # 8. No field-value — body is the identifier
        params['identifier'] = _extract_title(body)
        return params

    def _find_event(self, identifier, user):
        """Find an event matching *identifier* (title or date)."""
        from calendars.models import Event
        qs = user.events.all()

        # Try title match first
        if identifier:
            event = qs.filter(title__icontains=identifier).first()
            if event:
                return event

        # Try date match (today/this week)
        d, _ = _parse_date_from_text(identifier)
        if d:
            event = qs.filter(start_date=d).first()
            if event:
                return event

        # Try exact title
        if identifier:
            event = qs.filter(title__iexact=identifier).first()
            if event:
                return event

        return None

    def execute(self, text, user):
        params = self._parse(text)
        identifier = params.get('identifier', '').strip()
        field = params.get('field', '')
        value = params.get('value')

        # If we have a field+value but no explicit identifier, try to find
        # the most relevant event (e.g. today's events for status updates)
        if not identifier and field and value is not None:
            from calendars.models import Event
            from django.utils import timezone
            today = timezone.now().date()
            recent = user.events.filter(start_date__gte=today).order_by('start_date').first()
            if recent:
                identifier = recent.title

        if not identifier:
            return (
                'I need to know which event to update. '
                'Please provide the event title or date.'
            )

        if not field or value is None:
            return (
                f'I found event matching "{identifier}", but what would you like to change? '
                f'You can update the title, date, time, end time, location, status, type, '
                f'description, or link.'
            )

        from calendars.models import Event
        from django.db import transaction
        from django.core.exceptions import ValidationError

        event = self._find_event(identifier, user)
        if not event:
            return f'I could not find an event matching "{identifier}".'

        try:
            norm_field, norm_value = _normalise_event_field_value(field, str(value), user)
        except ValueError as e:
            return str(e)

        try:
            with transaction.atomic():
                setattr(event, norm_field, norm_value)
                event.full_clean()
                event.save()
                event.refresh_from_db()
        except ValidationError as e:
            error_details = []
            for fld, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{fld}: {err}')
            return (
                'Failed to update event — validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception('Failed to update event for user=%s', user)
            return f'Failed to update event: {e}'

        readable_field = norm_field.replace('_', ' ').title()
        if norm_field == 'start_date':
            display = event.start_date.strftime('%b %d, %Y')
        elif norm_field == 'start_time':
            display = event.start_time.strftime('%I:%M %p').lstrip('0') if event.start_time else 'None'
        elif norm_field == 'end_time':
            display = event.end_time.strftime('%I:%M %p').lstrip('0') if event.end_time else 'None'
        elif norm_field == 'status':
            display = event.get_status_display()
        elif norm_field == 'event_type':
            display = event.get_event_type_display()
        else:
            display = str(norm_value)

        lines = [
            f'Event **"{event.title}"** updated.',
            f'{readable_field}: {display}',
        ]
        return '  \n'.join(lines)


@register
class DeleteEventAction(BaseAction):
    action_type = 'delete_event'
    keywords = frozenset({'delete', 'remove', 'cancel', 'erase', 'event', 'meeting', 'appointment'})
    patterns = [
        re.compile(r'(delete|remove|cancel|erase)\s+(event|meeting|appointment)'),
        re.compile(r'(delete|remove|cancel|erase).*\b(event|meeting|appointment)\b'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:delete|remove|erase|cancel)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^(?:event|meeting|appointment)\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'\s+from\s+(?:the\s+)?(?:event|meeting|appointment|calendar|model|database|system)'
            r'(?:\s+(?:event|meeting|appointment|calendar|model|database|system))*\s*$',
            '', body, flags=re.IGNORECASE,
        ).strip()
        return _extract_title(body)

    def _find_event(self, identifier, user):
        """Find an event matching *identifier* (title or date)."""
        from calendars.models import Event
        qs = user.events.all()

        if identifier:
            event = qs.filter(title__icontains=identifier).first()
            if event:
                return event

        d, _ = _parse_date_from_text(identifier)
        if d:
            event = qs.filter(start_date=d).first()
            if event:
                return event

        if identifier:
            event = qs.filter(title__iexact=identifier).first()
            if event:
                return event

        return None

    def execute(self, text, user):
        identifier = self._parse(text)
        if not identifier:
            return 'I need to know which event to delete. Please provide the event title or date.'

        from calendars.models import Event

        # Try to find the event — first by title, then by date
        event = self._find_event(identifier, user)

        if not event:
            # Try using the original text to extract a date
            d, _ = _parse_date_from_text(text)
            if d:
                matches = list(user.events.filter(start_date=d))
                if len(matches) == 1:
                    event = matches[0]
                elif len(matches) > 1:
                    names = '\n'.join(f'  {i+1}. **{e.title}** ({e.start_date})' for i, e in enumerate(matches))
                    return (
                        f'I found multiple events on that date:\n'
                        f'{names}\n'
                        f'Please specify which one you want to delete.'
                    )
                else:
                    return f'I could not find any events on {d.strftime("%b %d, %Y")}.'

        if not event:
            return f'I could not find an event matching "{identifier}".'

        from django.db import transaction
        try:
            with transaction.atomic():
                event.delete()
        except Exception as e:
            logger.exception('Failed to delete event for user=%s', user)
            return f'Failed to delete event: {e}'

        # Verify deletion
        if Event.objects.filter(pk=event.pk).exists():
            return 'Failed to delete event.'

        return f'Event **"{event.title}"** has been deleted.'


@register
class ViewEventAction(BaseAction):
    action_type = 'view_event'
    keywords = frozenset({
        'event', 'meeting', 'appointment', 'show', 'view', 'open', 'details',
        'tell', 'about',
    })
    patterns = [
        re.compile(r'(show|view|open).*(event|meeting|appointment)'),
        re.compile(r'(event|meeting|appointment).*(details|info|information)'),
        re.compile(r'(tell|show).*(about).*(event|meeting|appointment)'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:show\s+(?:me\s+)?|view\s+|open\s+|see\s+|display\s+)',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(
            r'^(?:tell\s+me\s+about|tell\s+about|tell\s+me)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^about\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'^(?:event|meeting|appointment)\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'^(?:details?|info|information)(?:\s+(?:for|about|on)\s+|\s+)',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'\s+(?:event|meeting|appointment)\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+(?:details?|info|information)\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'^(?:details?|info|information)\s*$', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'^(?:(?:my|the|a|an)\s+)?(?:event|meeting|appointment)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(
            r'^(?:in|from|of|for|on)\s+(?:my|the|your)?\s*'
            r'(?:calendar|schedule|event|meeting|appointment)\s*',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(
            r"\s+(?:in|from|of|for|on)\s+(?:my|the|your)?\s*"
            r"(?:calendars?|schedule|events?|meetings?|appointments?)?\s*$",
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^[\s"\'.,;:!?\-]+|[\s"\'.,;:!?\-]+$', '', body).strip()
        body = re.sub(r'\s+', ' ', body).strip()
        return body

    def _find_event(self, identifier, user):
        from calendars.models import Event
        qs = user.events.all()

        if identifier:
            event = qs.filter(title__icontains=identifier).first()
            if event:
                return event

        d, _ = _parse_date_from_text(identifier)
        if d:
            event = qs.filter(start_date=d).first()
            if event:
                return event

        if identifier:
            event = qs.filter(title__iexact=identifier).first()
            if event:
                return event

        return None

    def execute(self, text, user):
        identifier = self._parse(text)
        if not identifier:
            return 'I need to know which event to show. Please provide the event title or date.'

        event = self._find_event(identifier, user)

        if not event:
            d, _ = _parse_date_from_text(text)
            if d:
                event = user.events.filter(start_date=d).first()

        if not event:
            return f'I could not find an event matching "{identifier}".'

        start_date = event.start_date.strftime('%b %d, %Y') if event.start_date else '—'
        start_time = event.start_time.strftime('%I:%M %p').lstrip('0') if event.start_time else '—'
        end_time = event.end_time.strftime('%I:%M %p').lstrip('0') if event.end_time else '—'
        time_str = f'{start_time} – {end_time}' if event.start_time else '—'
        created = event.created_at.strftime('%b %d, %Y') if event.created_at else '—'
        updated = event.updated_at.strftime('%b %d, %Y') if event.updated_at else '—'

        rows = [
            f'| **Title**      | {event.title}',
            f'| **Date**       | {start_date}',
            f'| **Time**       | {time_str}',
            f'| **Location**   | {event.location or "—"}',
            f'| **Type**       | {event.get_event_type_display()}',
            f'| **Status**     | {event.get_status_display()}',
            f'| **Description**| {event.description or "—"}',
            f'| **Created**    | {created}',
            f'| **Updated**    | {updated}',
        ]
        table = '\n'.join(rows)
        return f'### Event Details\n{table}'


@register
class CreateCampaignAction(BaseAction):
    action_type = 'create_campaign'
    keywords = frozenset({'create', 'add', 'new', 'campaign', 'email'})
    patterns = [re.compile(r'(create|add|new).*(campaign)')]

    _STATUS_MAP = {
        'draft': 'Draft',
        'scheduled': 'Scheduled',
        'sent': 'Sent',
    }

    def execute(self, text, user):
        params = self._parse(text)
        name = params.get('name', '').strip()
        if not name:
            return (
                'I need a campaign name to create a campaign. '
                'What should the campaign be called?'
            )

        from campaigns.models import Campaign
        from django.db import transaction
        from django.core.exceptions import ValidationError

        sid = None
        try:
            with transaction.atomic():
                sid = transaction.savepoint()
                campaign = Campaign(
                    owner=user,
                    name=name,
                    subject=params.get('subject', name),
                    body=params.get('body', ''),
                    status=params.get('status', 'Draft'),
                    scheduled_at=params.get('scheduled_at'),
                )
                campaign.full_clean()
                campaign.save()
                campaign.refresh_from_db()

                saved_pk = campaign.pk
                try:
                    reloaded = Campaign.objects.get(pk=saved_pk)
                except Campaign.DoesNotExist:
                    transaction.savepoint_rollback(sid)
                    logger.error(
                        'Campaign pk=%s was NOT committed -- DB get() returned None. '
                        'user=%s msg=%s',
                        saved_pk, user, text[:120],
                    )
                    return (
                        'Failed to create campaign: the record was not persisted '
                        'to the database. Please try again.'
                    )

        except ValidationError as e:
            logger.error(
                'Campaign validation failed for user=%s msg=%s error=%s',
                user, text[:120], e.message_dict,
            )
            error_details = []
            for field, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{field}: {err}')
            return (
                'Failed to create campaign -- validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception(
                'Failed to create campaign for user=%s msg=%s',
                user, text[:120],
            )
            if sid is not None:
                logger.warning('Transaction rolled back at savepoint %s', sid)
            return f'Failed to create campaign: {e}'

        lines = [
            'Campaign created successfully (ID: {}): **{}**'.format(
                campaign.pk, campaign.name,
            ),
        ]
        if campaign.subject and campaign.subject != campaign.name:
            lines.append(f'Subject: {campaign.subject}')
        if campaign.scheduled_at:
            lines.append(
                'Scheduled: {}'.format(
                    campaign.scheduled_at.strftime('%b %d, %Y at %I:%M %p'),
                ),
            )
        lines.append(f'Status: {campaign.status}')
        if campaign.body:
            lines.append(f'Body: {campaign.body[:200]}')
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Strip action prefix
        m = re.search(
            r'\b(?:create|add|new)\s+(?:a\s+|an\s+)?(?:new\s+)?'
            r'(?:email\s+)?campaign\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        body = re.sub(
            r'^(?:for|named|called|about)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Extract structured fields via keyword:value patterns
        _end = r'(?=\s+(?:name|subject|body|description|status)|$)'
        field_patterns = [
            ('name', r'\bname\s*[:=]\s*(.+?)' + _end),
            ('subject', r'\bsubject\s*[:=]\s*(.+?)' + _end),
            ('body', r'\b(?:body|description|content)\s*[:=]\s*(.+?)' + _end),
            ('status', r'\bstatus\s*[:=]\s*(.+?)' + _end),
        ]
        for key, pattern in field_patterns:
            if key in params and params[key]:
                continue
            m = re.search(pattern, body, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if key == 'status':
                    val = self._normalise_campaign_status(val)
                if val:
                    params[key] = val
                    body = _remove_match(body, m)

        # 3. Parse scheduled_at from natural language date/time
        dt, body = _parse_datetime_from_text(body)
        if dt:
            params['scheduled_at'] = dt

        # 4. Strip schedule/target noise words left after date removal
        body = re.sub(
            r'\bschedule(?:d)?\s+(?:for|on|at)?\s*',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(
            r'^(?:for|about|regarding)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 5. Remaining body -> campaign name (if not already extracted via name: field)
        if 'name' not in params:
            name = _extract_title(body)
            if name:
                params['name'] = name

        return params

    @staticmethod
    def _normalise_campaign_status(val):
        val = val.strip().lower()
        for key, mapped in CreateCampaignAction._STATUS_MAP.items():
            if val == key or val.startswith(key):
                return mapped
        return val.title()


@register
class PauseCampaignAction(BaseAction):
    action_type = 'pause_campaign'
    keywords = frozenset({'pause', 'stop', 'halt', 'campaign'})
    patterns = [re.compile(r'(pause|stop|halt).*(campaign)')]

    def extract_params(self, text):
        return {}


@register
class ResumeCampaignAction(BaseAction):
    action_type = 'resume_campaign'
    keywords = frozenset({'resume', 'unpause', 'continue', 'campaign'})
    patterns = [re.compile(r'(resume|unpause|continue).*(campaign)')]

    def extract_params(self, text):
        return {}


@register
class DeleteCampaignAction(BaseAction):
    action_type = 'delete_campaign'
    keywords = frozenset({'delete', 'remove', 'erase', 'cancel', 'campaign'})
    patterns = [
        re.compile(r'(delete|remove|erase|cancel)\s+campaign\b'),
        re.compile(r'(delete|remove|erase|cancel).*\bcampaign\b'),
    ]

    def _parse(self, text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:delete|remove|erase|cancel)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^campaign\s+', '', body, flags=re.IGNORECASE).strip()
        body = re.sub(r'\s+campaign\s*$', '', body, flags=re.IGNORECASE).strip()
        return _extract_title(body)

    def execute(self, text, user):
        name = self._parse(text)
        if not name:
            return 'I need a campaign name to delete. Which campaign should I delete?'

        from campaigns.models import Campaign

        qs = user.campaigns.all()
        matches = list(qs.filter(name__icontains=name))
        if len(matches) == 0:
            return f'I could not find a campaign matching "{name}".'
        if len(matches) > 1:
            names = '\n'.join(f'  {i+1}. **{c.name}**' for i, c in enumerate(matches))
            return (
                f'I found multiple campaigns matching "{name}":\n'
                f'{names}\n'
                f'Please specify which one you want to delete.'
            )

        campaign = matches[0]
        try:
            from django.db import transaction
            with transaction.atomic():
                campaign.delete()
        except Exception as e:
            logger.exception('Failed to delete campaign for user=%s', user)
            return f'Failed to delete campaign: {e}'

        return f'Campaign **"{name}"** has been deleted.'


@register
class CreateNotificationAction(BaseAction):
    action_type = 'create_notification'
    keywords = frozenset({
        'create', 'add', 'send', 'new', 'notification', 'alert', 'notify',
    })
    patterns = [
        re.compile(r'(create|add|send|new).*(notification|alert|notify)'),
    ]

    def execute(self, text, user):
        params = self._parse(text)
        title = params.get('title', '').strip()
        if not title:
            return (
                'I need a title to create a notification. '
                'What should the notification be about?'
            )

        from workflows.models import Notification
        from django.db import transaction
        from django.core.exceptions import ValidationError

        sid = None
        try:
            with transaction.atomic():
                sid = transaction.savepoint()
                notification = Notification(
                    owner=user,
                    title=title,
                    message=params.get('message', ''),
                    link=params.get('link', ''),
                )
                notification.full_clean()
                notification.save()
                notification.refresh_from_db()

                saved_pk = notification.pk
                try:
                    reloaded = Notification.objects.get(pk=saved_pk)
                except Notification.DoesNotExist:
                    transaction.savepoint_rollback(sid)
                    logger.error(
                        'Notification pk=%s was NOT committed -- DB get() '
                        'returned None. user=%s msg=%s',
                        saved_pk, user, text[:120],
                    )
                    return (
                        'Failed to create notification: the record was not '
                        'persisted to the database. Please try again.'
                    )

        except ValidationError as e:
            logger.error(
                'Notification validation failed for user=%s msg=%s error=%s',
                user, text[:120], e.message_dict,
            )
            error_details = []
            for field, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{field}: {err}')
            return (
                'Failed to create notification -- validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception(
                'Failed to create notification for user=%s msg=%s',
                user, text[:120],
            )
            if sid is not None:
                logger.warning('Transaction rolled back at savepoint %s', sid)
            return f'Failed to create notification: {e}'

        lines = [
            'Notification created successfully (ID: {}): **{}**'.format(
                notification.pk, notification.title,
            ),
        ]
        if notification.message:
            lines.append(f'Message: {notification.message[:200]}')
        if notification.link:
            lines.append(f'Link: {notification.link}')
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Strip action prefix
        m = re.search(
            r'\b(?:create|add|send|new)\s+(?:a\s+|an\s+)?(?:new\s+)?'
            r'(?:notification|alert)\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        body = re.sub(
            r'^(?:for|about|regarding)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Extract structured fields via keyword:value patterns
        _end = r'(?=\s+(?:title|message|msg|link|priority)|$)'
        field_patterns = [
            ('title', r'\btitle\s*[:=]\s*(.+?)' + _end),
            ('message', r'\b(?:message|msg)\s*[:=]\s*(.+?)' + _end),
            ('link', r'\blink\s*[:=]\s*(.+?)' + _end),
        ]
        for key, pattern in field_patterns:
            if key in params and params[key]:
                continue
            m = re.search(pattern, body, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val:
                    params[key] = val
                    body = _remove_match(body, m)

        # 3. Remaining body -> title (if not already extracted)
        if 'title' not in params:
            t = _extract_title(body)
            if t:
                params['title'] = t

        return params


@register
class CreateWorkflowAction(BaseAction):
    action_type = 'create_workflow'
    keywords = frozenset({
        'create', 'add', 'new', 'workflow', 'automation', 'rule',
    })
    patterns = [
        re.compile(r'(create|add|new).*(workflow|automation|rule)'),
    ]

    _TRIGGER_MAP = {
        'one day before a meeting': 'meeting_reminder',
        'day before a meeting': 'meeting_reminder',
        'before a meeting': 'meeting_reminder',
        'meeting reminder': 'meeting_created',
        'remind me about a meeting': 'meeting_created',
        'remind me before a meeting': 'meeting_created',
        'meeting_reminder': 'meeting_reminder',
        'when a new lead is created': 'lead_created',
        'when a lead is created': 'lead_created',
        'when a new contact is added': 'contact_created',
        'when a contact is added': 'contact_created',
        'when a contact is created': 'contact_created',
        'when a contact is updated': 'contact_updated',
        'contact updated': 'contact_updated',
        'contact update': 'contact_updated',
        'when a task is completed': 'task_completed',
        'when a task is created': 'task_created',
        'when a campaign starts': 'campaign_started',
        'when a campaign is started': 'campaign_started',
        'when a campaign is created': 'campaign_created',
        'when a campaign completes': 'campaign_completed',
        'when a campaign is completed': 'campaign_completed',
        'contact created': 'contact_created',
        'contact creation': 'contact_created',
        'new contact': 'contact_created',
        'lead created': 'lead_created',
        'lead creation': 'lead_created',
        'new lead': 'lead_created',
        'lead updated': 'lead_updated',
        'lead qualified': 'lead_qualified',
        'lead won': 'lead_won',
        'won lead': 'lead_won',
        'won deal': 'lead_won',
        'lead lost': 'lead_lost',
        'lost lead': 'lead_lost',
        'lost deal': 'lead_lost',
        'task created': 'task_created',
        'task creation': 'task_created',
        'new task': 'task_created',
        'task completed': 'task_completed',
        'task completion': 'task_completed',
        'task overdue': 'task_overdue',
        'meeting created': 'meeting_created',
        'meeting creation': 'meeting_created',
        'new meeting': 'meeting_created',
        'meeting finished': 'meeting_finished',
        'campaign started': 'campaign_started',
        'campaign created': 'campaign_created',
        'campaign creation': 'campaign_created',
        'new campaign': 'campaign_created',
        'campaign completed': 'campaign_completed',
        'daily': 'scheduled_daily',
        'weekly': 'scheduled_weekly',
        'monthly': 'scheduled_monthly',
    }

    _ACTION_MAP = {
        'create a task': 'create_task',
        'create task': 'create_task',
        'creates a task': 'create_task',
        'follow up task': 'create_task',
        'followup task': 'create_task',
        'follow-up task': 'create_task',
        'update task': 'update_task',
        'update a task': 'update_task',
        'send an email': 'send_email',
        'send email': 'send_email',
        'sends an email': 'send_email',
        'create a calendar event': 'create_event',
        'create calendar event': 'create_event',
        'create an event': 'create_event',
        'create event': 'create_event',
        'create calendar_event': 'create_calendar_event',
        'create_calendar_event': 'create_calendar_event',
        'assign a lead': 'assign_lead',
        'assign lead': 'assign_lead',
        'change lead status': 'change_lead_status',
        'add a tag': 'add_tag',
        'add tag': 'add_tag',
        'remove a tag': 'remove_tag',
        'remove tag': 'remove_tag',
        'generate ai summary': 'ai_summary',
        'generate summary': 'ai_summary',
        'generate ai email': 'ai_email',
        'generate email': 'ai_email',
        'generate ai followup': 'ai_followup',
        'generate follow up': 'ai_followup',
        'generate followup': 'ai_followup',
        'create a notification': 'create_notification',
        'create notification': 'create_notification',
        'send a notification': 'create_notification',
        'send notification': 'create_notification',
        'notify user': 'create_notification',
        'notify me': 'create_notification',
        'send_notification': 'send_notification',
        'create a contact': 'create_contact',
        'create contact': 'create_contact',
        'creates a contact': 'create_contact',
        'create_contact': 'create_contact',
        'create a lead': 'create_lead',
        'create lead': 'create_lead',
        'creates a lead': 'create_lead',
        'create_lead': 'create_lead',
        'webhook': 'webhook',
    }

    def execute(self, text, user):
        params = self._parse(text)

        name = params.get('name', '').strip()
        if not name:
            return (
                'I need a name to create a workflow. '
                'What should the workflow be called?'
            )

        trigger_type = params.get('trigger_type', '').strip()
        if not trigger_type:
            return (
                'I need a trigger for the workflow. '
                'When should it run? (e.g. lead_created, task_completed)'
            )

        from workflows.models import Workflow, WorkflowAction
        from django.db import transaction
        from django.core.exceptions import ValidationError

        sid = None
        try:
            with transaction.atomic():
                sid = transaction.savepoint()
                workflow = Workflow(
                    owner=user,
                    name=name,
                    description=params.get('description', ''),
                    trigger_type=trigger_type,
                    is_active=params.get('is_active', True),
                )
                workflow.full_clean()
                workflow.save()
                workflow.refresh_from_db()

                saved_pk = workflow.pk
                try:
                    reloaded = Workflow.objects.get(pk=saved_pk)
                except Workflow.DoesNotExist:
                    transaction.savepoint_rollback(sid)
                    logger.error(
                        'Workflow pk=%s was NOT committed -- DB get() '
                        'returned None. user=%s msg=%s',
                        saved_pk, user, text[:120],
                    )
                    return (
                        'Failed to create workflow: the record was not '
                        'persisted to the database. Please try again.'
                    )

                actions = params.get('actions', [])
                created_actions = []
                for idx, action_type in enumerate(actions):
                    wa = WorkflowAction(
                        workflow=workflow,
                        action_type=action_type,
                        order=idx,
                    )
                    wa.full_clean()
                    wa.save()
                    created_actions.append(wa)

        except ValidationError as e:
            logger.error(
                'Workflow validation failed for user=%s msg=%s error=%s',
                user, text[:120], e.message_dict,
            )
            error_details = []
            for field, errors in e.message_dict.items():
                for err in errors:
                    error_details.append(f'{field}: {err}')
            return (
                'Failed to create workflow -- validation error(s):\n'
                + '\n'.join(error_details)
            )
        except Exception as e:
            logger.exception(
                'Failed to create workflow for user=%s msg=%s',
                user, text[:120],
            )
            if sid is not None:
                logger.warning('Transaction rolled back at savepoint %s', sid)
            return f'Failed to create workflow: {e}'

        lines = [
            'Workflow created successfully (ID: {}): **{}**'.format(
                workflow.pk, workflow.name,
            ),
        ]
        lines.append('Trigger: {}'.format(workflow.get_trigger_type_display()))
        lines.append('Active: {}'.format('Yes' if workflow.is_active else 'No'))
        if workflow.description:
            lines.append('Description: {}'.format(workflow.description[:200]))
        if created_actions:
            acts = ', '.join(
                wa.get_action_type_display() for wa in created_actions
            )
            lines.append('Actions: {}'.format(acts))
        return '  \n'.join(lines)

    def _parse(self, text):
        """Parse *text* into a params dict."""
        params = {}
        body = text

        # 1. Strip action prefix
        m = re.search(
            r'\b(?:create|add|new)\s+(?:a\s+|an\s+)?(?:new\s+)?'
            r'(?:workflow|automation|rule)\s*',
            body, flags=re.IGNORECASE,
        )
        if m:
            body = body[m.end():].strip()
        body = re.sub(
            r'^(?:for|about|regarding)\s+', '', body, flags=re.IGNORECASE,
        ).strip()

        # 2. Extract structured fields
        _end = r'(?=\s+(?:name|trigger|action|actions|description|status|active)|$)'
        field_patterns = [
            ('name', r'\bname\s*[:=]?\s*(.+?)' + _end),
            ('trigger_raw', r'\btrigger\s*[:=]?\s*(.+?)' + _end),
            ('actions_raw', r'\b(?:action|actions)\s*[:=]?\s*(.+?)' + _end),
            ('description', r'\bdescription\s*[:=]?\s*(.+?)' + _end),
            ('status', r'\b(?:status|active)\s*[:=]?\s*(.+?)' + _end),
        ]
        actions_raw = None
        for key, pattern in field_patterns:
            if key in params and params[key]:
                continue
            m = re.search(pattern, body, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if key == 'trigger_raw':
                    mapped = self._resolve_trigger(val)
                    if mapped:
                        params['trigger_type'] = mapped
                        body = _remove_match(body, m)
                    continue
                if key == 'actions_raw':
                    actions_raw = val
                    body = _remove_match(body, m)
                    continue
                if key == 'status':
                    params['is_active'] = val.lower() in (
                        'active', 'true', 'yes', '1', 'on',
                    )
                    body = _remove_match(body, m)
                    continue
                if val:
                    params[key] = val
                    body = _remove_match(body, m)

        # Resolve action strings to action_type slugs
        if actions_raw:
            parts = [a.strip() for a in re.split(r'[,;]', actions_raw) if a.strip()]
            for part in parts:
                mapped = self._resolve_action(part)
                if mapped:
                    params.setdefault('actions', []).append(mapped)

        # 3. Try to detect trigger from natural language
        if 'trigger_type' not in params:
            body_lower = body.lower()
            for phrase, mapped in sorted(
                self._TRIGGER_MAP.items(),
                key=lambda x: -len(x[0]),
            ):
                if phrase in body_lower:
                    params['trigger_type'] = mapped
                    body = re.sub(
                        r'\b' + re.escape(phrase) + r's?\b', '', body,
                        flags=re.IGNORECASE,
                    ).strip()
                    break
            else:
                for slug in [
                    'contact_created', 'lead_created', 'lead_updated',
                    'lead_qualified', 'lead_won', 'lead_lost',
                    'task_created', 'task_completed', 'task_overdue',
                    'meeting_created', 'meeting_finished',
                    'campaign_started', 'campaign_completed',
                ]:
                    words = slug.split('_')
                    pattern = r'\b' + r'\s.*\b'.join(words) + r'\b'
                    if re.search(pattern, body_lower):
                        params['trigger_type'] = slug
                        for w in words:
                            body = re.sub(
                                r'\b' + re.escape(w) + r'\b', '', body,
                                flags=re.IGNORECASE,
                            ).strip()
                        body = ''
                        break

        # 4. Detect actions from remaining natural language
        if 'actions' not in params:
            body_lower = body.lower()
            for phrase, mapped in sorted(
                self._ACTION_MAP.items(),
                key=lambda x: -len(x[0]),
            ):
                if phrase in body_lower:
                    params.setdefault('actions', []).append(mapped)
                    body = re.sub(
                        r'\b' + re.escape(phrase) + r's?\b', '', body,
                        flags=re.IGNORECASE,
                    ).strip()

        # 5. Remaining body -> name (if not already extracted)
        if 'name' not in params:
            n = _extract_title(body)
            if n:
                params['name'] = n

        # 6. Fallback name from trigger when body is empty
        if 'name' not in params and 'trigger_type' in params:
            params['name'] = params['trigger_type'].replace(
                '_', ' ',
            ).title() + ' Workflow'

        return params

    @staticmethod
    def _resolve_trigger(val):
        val_lower = val.strip().lower()
        for choice_key in [
            'contact_created', 'contact_updated',
            'lead_created', 'lead_updated',
            'lead_qualified', 'lead_won', 'lead_lost',
            'task_created', 'task_completed', 'task_overdue',
            'meeting_created', 'meeting_finished', 'meeting_reminder',
            'campaign_created', 'campaign_started', 'campaign_completed',
            'scheduled_daily', 'scheduled_weekly', 'scheduled_monthly',
        ]:
            if val_lower == choice_key or val_lower == choice_key.replace('_', ' '):
                return choice_key
        for phrase, mapped in CreateWorkflowAction._TRIGGER_MAP.items():
            if phrase in val_lower or val_lower in phrase:
                return mapped
        return None

    @staticmethod
    def _resolve_action(val):
        val_lower = val.strip().lower()
        for choice_key in [
            'create_task', 'update_task', 'send_email', 'create_event',
            'create_calendar_event',
            'assign_lead', 'change_lead_status', 'add_tag', 'remove_tag',
            'ai_summary', 'ai_email', 'ai_followup',
            'create_notification', 'send_notification',
            'create_contact', 'create_lead',
            'webhook',
        ]:
            if val_lower == choice_key or val_lower == choice_key.replace('_', ' '):
                return choice_key
        for phrase, mapped in CreateWorkflowAction._ACTION_MAP.items():
            if phrase in val_lower or val_lower in phrase:
                return mapped
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  modify_anything — catch-all update / delete / cancel
# ═══════════════════════════════════════════════════════════════════════════

@register
class ModifyAnythingAction(BaseAction):
    """Catch-all for update/delete/cancel patterns that specific actions miss
    (e.g. plural entity names like "contacts" / "tasks", indirect references
    like "change company of John").
    """

    action_type = 'modify_anything'
    keywords = frozenset({
        'update', 'edit', 'change', 'modify', 'set', 'rename',
        'delete', 'remove', 'erase', 'cancel',
    })
    patterns = [
        # Any text containing an update verb
        re.compile(r'\b(?:update|edit|change|modify|set|rename|delete|remove|erase|cancel)\b'),
        # "I want to ..."
        re.compile(r'\bi\s+(?:want\s+)?(?:to\s+)?(?:update|edit|change|modify|set|rename|delete|remove|erase|cancel)\b'),
        # Possessive "<name>'s <attr> to <value>"
        re.compile(r"'s\s+(?:phone|email|company|status|priority|name|title|number)\s+(?:to|as)\b"),
    ]

    _ENTITY_MAP = {
        'contact': ('contacts', 'full_name'),
        'person': ('contacts', 'full_name'),
        'lead': ('leads', 'lead_name'),
        'prospect': ('leads', 'lead_name'),
        'deal': ('leads', 'lead_name'),
        'task': ('tasks', 'title'),
        'event': ('events', 'title'),
        'meeting': ('events', 'title'),
        'appointment': ('events', 'title'),
        'reminder': ('events', 'title'),
        'campaign': ('campaigns', 'name'),
        'workflow': ('workflows', 'name'),
        'notification': ('notifications', 'title'),
        'alert': ('notifications', 'title'),
    }

    _QUERYSET_BUILDERS = {
        'contacts': lambda u: u.contacts.all(),
        'leads': lambda u: u.leads.all(),
        'tasks': lambda u: u.tasks.all(),
        'events': lambda u: u.events.all(),
        'campaigns': lambda u: u.campaigns.all(),
        'workflows': lambda u: u.workflows.all() if hasattr(u, 'workflows') else None,
        'notifications': lambda u: u.notifications.all() if hasattr(u, 'notifications') else None,
    }

    _NAME_FIELDS = {
        'contacts': 'full_name',
        'leads': 'lead_name',
        'tasks': 'title',
        'events': 'title',
        'campaigns': 'name',
        'workflows': 'name',
        'notifications': 'title',
    }


    # ── helpers ──

    @staticmethod
    def _strip_prefix(text):
        body = text
        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:update|edit|change|modify|set|rename|'
            r'delete|remove|erase|cancel)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()
        body = re.sub(r'^(?:the|my|this|that|a|an)\s+', '', body, flags=re.IGNORECASE).strip()
        return body

    @staticmethod
    def _get_queryset(user, rel):
        builder = ModifyAnythingAction._QUERYSET_BUILDERS.get(rel)
        if builder:
            return builder(user)
        return None

    @staticmethod
    def _get_name_field(rel):
        return ModifyAnythingAction._NAME_FIELDS.get(rel, 'title')

    @staticmethod
    def _is_delete(text_lower):
        return bool(re.search(r'\b(?:delete|remove|erase|cancel)\b', text_lower))

    @staticmethod
    def _is_update(text_lower):
        return bool(re.search(r'\b(?:update|edit|change|modify|set|rename)\b', text_lower))

    @staticmethod
    def _is_question(text_lower):
        """Return True if *text_lower* looks like a question, not a command."""
        return bool(re.search(
            r'\b(?:how\s+(?:do|can|should|would|will|to|does)'
            r'|what\s+(?:is|are|does|do)'
            r'|can\s+you'
            r'|tell\s+(?:me|us)\s+(?:how|what|about))',
            text_lower,
        ))

    @staticmethod
    def _normalise_value(field, value, entity_type):
        """Map raw value strings to model-choice-friendly values."""
        val_lower = value.strip().lower()

        # Status normalisation
        status_map = {
            'contacts': {
                'active': 'active', 'inactive': 'inactive',
            },
            'leads': {
                'new': 'New', 'contacted': 'Contacted',
                'qualified': 'Qualified', 'proposal': 'Proposal Sent',
                'proposal sent': 'Proposal Sent',
                'negotiation': 'Negotiation',
                'won': 'Won', 'lost': 'Lost',
            },
            'tasks': {
                'pending': 'pending', 'in progress': 'in_progress',
                'in progress': 'in_progress', 'completed': 'completed',
                'done': 'completed', 'finished': 'completed',
                'cancelled': 'cancelled',
            },
            'events': {
                'scheduled': 'Scheduled', 'completed': 'Completed',
                'cancelled': 'Cancelled', 'rescheduled': 'Rescheduled',
            },
        }
        if field == 'status':
            mapping = status_map.get(entity_type, {})
            if val_lower in mapping:
                return mapping[val_lower]
            return value

        # Priority normalisation
        priority_map = {
            'high': 'High', 'medium': 'Medium', 'low': 'Low',
        }
        if field == 'priority' and val_lower in priority_map:
            return priority_map[val_lower]

        return value

    @staticmethod
    def _extract_field_value_for_entity(body, entity_type):
        """Try to extract ``(field, value)`` from *body* for *entity_type*."""
        # Phone
        m = re.search(r'(\+?\d[\d\s\-().]{6,20}\d)\b', body)
        if m:
            return ('phone', m.group(1).strip())
        # Email
        m = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', body)
        if m:
            return ('email', m.group(1).lower())

        # Status / priority keywords
        for pat, field, vals in [
            (r'\b(?:qualified|won|lost|new|contacted)\b', 'status',
             ['new', 'contacted', 'qualified', 'won', 'lost']),
            (r'\b(?:high|medium|low)\b', 'priority',
             ['high', 'medium', 'low']),
            (r'\b(?:completed|done|finished|pending|cancelled|active)\b', 'status',
             ['completed', 'done', 'finished', 'pending', 'cancelled', 'active']),
        ]:
            m = re.search(pat, body, re.IGNORECASE)
            if m:
                val = m.group(0).lower()
                norm = {
                    'done': 'completed', 'finished': 'completed',
                }
                return (field, norm.get(val, val))

        field_map = {
            'contacts': _CONTACT_UPDATE_FIELDS,
            'leads': _LEAD_UPDATE_FIELDS,
            'tasks': _TASK_UPDATE_FIELDS,
            'events': _EVENT_UPDATE_FIELDS,
        }.get(entity_type)

        if field_map:
            keys = sorted(field_map.keys(), key=len, reverse=True)
            field_alt = '|'.join(re.escape(k) for k in keys)

            # Pattern A: "<attr> to <value>" (simple, e.g. "company to MegaCorp")
            m = re.search(
                r'\b(' + field_alt + r')\s+(?:to|as)\s+(.+)', body, re.IGNORECASE,
            )
            if m:
                raw_field = m.group(1).lower()
                value = m.group(2).strip()
                norm_field = field_map.get(raw_field)
                if norm_field:
                    return (norm_field, value)

            # Pattern B: "<attr> of <entity> to <value>" (e.g. "company of John to Acme")
            m = re.search(
                r'\b(' + field_alt + r')\s+(?:of|for)\s+'
                r'.*?\s+(?:to|as)\s+(.+)',
                body, re.IGNORECASE,
            )
            if m:
                raw_field = m.group(1).lower()
                value = m.group(2).strip()
                norm_field = field_map.get(raw_field)
                if norm_field:
                    return (norm_field, value)

        return (None, None)

    # ── Name extraction pipeline ──

    def _clean_name_body(self, text):
        """Strip prefix, attribute phrases, entity words, and trailing
        prepositions from *text* to extract a candidate entity name."""
        body = self._strip_prefix(text)

        # 1) Strip trailing "to <value>" / "as <value>"
        body = re.sub(
            r'\s+(?:to|as)\s+\S+(?:\s+\S+)*\s*$', '', body,
            flags=re.IGNORECASE,
        ).strip()

        # 2) Strip attribute-field phrase (e.g. "company of John" → "John")
        body = re.sub(
            r'\b(?:name|title|status|priority|phone|email|company|'
            r'date|time|location|description|number)\s+(?:of|for)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 3) Strip possessive "'s" and trailing noise words
        body = re.sub(r"'s\b", '', body, flags=re.IGNORECASE).strip()
        body = re.sub(
            r'\b(?:the|my|this|that|a|an|phone|email|company|status|'
            r'priority|name|title|number)\s*$',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 4) Strip entity-type words
        body = re.sub(
            r'\b(?:contacts?|leads?|tasks?|events?|meetings?|'
            r'campaigns?|appointments?|reminders?|persons?|'
            r'workflows?|notifications?|alerts?)\b',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # 5) Strip trailing prepositions + remainder
        body = re.sub(
            r'\b(?:from|in|of|to|at|for)\b.*$', '', body,
            flags=re.IGNORECASE,
        ).strip()

        return body

    # ── execute ──

    def execute(self, text, user):
        if not user or not user.is_authenticated:
            return None

        text_lower = text.lower().strip()

        # Don't interfere with questions
        if self._is_question(text_lower):
            return None

        is_delete = self._is_delete(text_lower)
        is_update = self._is_update(text_lower)
        if not is_delete and not is_update:
            return None

        from django.db.models import Q

        # ── Extract candidate name ──
        name_body = self._clean_name_body(text)
        if not name_body:
            return 'I need to know which item to modify.'

        # ── Search every entity type ──
        seen = set()
        candidates = []
        for rel_key, name_fld in self._NAME_FIELDS.items():
            if rel_key in seen:
                continue
            seen.add(rel_key)
            qs = self._get_queryset(user, rel_key)
            if qs is None:
                continue
            for m in qs.filter(Q(**{f'{name_fld}__icontains': name_body}))[:3]:
                candidates.append((rel_key, m))

        if len(candidates) == 0:
            return f'I could not find anything matching **"{name_body}"**.'
        if len(candidates) > 1:
            lines = [f'I found multiple matches for **"{name_body}"**:']
            for rel_key, m in candidates:
                nf = self._get_name_field(rel_key)
                lines.append(
                    f'- **{getattr(m, nf)}** ({rel_key.rstrip("s")})'
                )
            lines.append('Please specify which one you want to modify.')
            return '\n'.join(lines)

        rel, obj = candidates[0]
        name_field = self._get_name_field(rel)
        obj_name = getattr(obj, name_field)
        label = rel.rstrip('s')

        # ── DELETE ──
        if is_delete:
            from django.db import transaction
            try:
                with transaction.atomic():
                    obj.delete()
            except Exception as e:
                logger.exception('Failed to delete %s for user=%s', label, user)
                return f'Failed to delete {label}: {e}'
            return f'{label.title()} **"{obj_name}"** has been deleted.'

        # ── UPDATE ──
        field, value = self._extract_field_value_for_entity(text, rel)
        if field and value is not None:
            from django.db import transaction
            from django.core.exceptions import ValidationError
            value = self._normalise_value(field, value, rel)
            try:
                with transaction.atomic():
                    setattr(obj, field, value)
                    obj.full_clean()
                    obj.save()
            except ValidationError as e:
                errors = []
                for fld, errs in e.message_dict.items():
                    for err in errs:
                        errors.append(f'{fld}: {err}')
                return 'Validation error(s):\n' + '\n'.join(errors)
            except Exception as e:
                logger.exception('Failed to update %s for user=%s', label, user)
                return f'Failed to update {label}: {e}'
            return (
                f'{label.title()} **"{obj_name}"** updated.\n'
                f'{field.replace("_", " ").title()}: {value}'
            )

        return (
            f'I found {label} **"{obj_name}"**. '
            f'What would you like to change?'
        )


# ═══════════════════════════════════════════════════════════════════════════
#  compose_email — AI Email Composer
# ═══════════════════════════════════════════════════════════════════════════

@register
class ComposeEmailAction(BaseAction):
    """Detect email-writing intents, extract recipient/purpose, look up
    Contact model, and use the LLM to generate a professional email draft."""

    action_type = 'compose_email'
    keywords = frozenset({
        'write', 'draft', 'compose', 'create', 'send',
        'email', 'mail', 'follow', 'up',
    })
    patterns = [
        re.compile(r'(?:write|draft|compose|create|send)\s+(?:an?\s+)?(?:email|mail)\b'),
        re.compile(r'(?:write|draft|compose|create|send)\s+(?:a\s+)?follow[-\s]up'),
        re.compile(r'email\s+\w+'),
    ]

    _EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')

    def _parse(self, text):
        params = {'recipient': '', 'subject': '', 'purpose': '', 'email_address': ''}
        body = text

        body = re.sub(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?'
            r'(?:write|draft|compose|create|send)\s+'
            r'(?:an?\s+)?(?:follow[-\s]up\s+)?(?:email|mail)\s+(?:to|for)\s+',
            '', body, flags=re.IGNORECASE,
        ).strip()

        # If still matched the verb-prefix above, try "email <name>"
        if body == text and re.match(
            r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?email\s+', body, re.IGNORECASE,
        ):
            body = re.sub(
                r'^(?:please\s+)?(?:i\s+(?:want\s+(?:to\s+)?)?)?email\s+',
                '', body, flags=re.IGNORECASE,
            ).strip()

        # Extract purpose after "about / regarding / concerning"
        m = re.search(
            r'\b(?:about|regarding|concerning)\s+(.+?)$',
            body, flags=re.IGNORECASE,
        )
        if m:
            params['purpose'] = m.group(1).strip()
            body = body[:m.start()].strip()
        else:
            # Extract purpose after action verbs (thanking, to discuss, etc.)
            m = re.search(
                r'\b(?:thanking|to\s+(?:thank|discuss|follow\s+up|schedule|confirm|update|share|provide|review|go\s+over))\s+(.+?)$',
                body, flags=re.IGNORECASE,
            )
            if m:
                params['purpose'] = m.group(0).strip()
                body = body[:m.start()].strip()

        # Detect inline email address
        m = self._EMAIL_RE.search(body)
        if m:
            params['email_address'] = m.group()
            pre = body[:m.start()].strip().rstrip(' <(')
            if pre:
                pre = re.sub(
                    r'\s+(?:at|@)\s*$', '', pre, flags=re.IGNORECASE,
                ).strip()
                params['recipient'] = _extract_title(pre)
        else:
            params['recipient'] = _extract_title(body)

        return params

    def _build_prompt(self, recipient_name, email_addr, company, position, purpose, sender_name, sender_email, sender_company):
        lines = [
            'You are a professional email writer for a CRM platform.',
            'Generate ONLY the subject and email body.',
            'Do NOT include To, From, or signature — those are added by the system.',
            '',
            '--- RECIPIENT ---',
            f'Name: {recipient_name or "Unknown"}',
        ]
        if email_addr:
            lines.append(f'Email: {email_addr}')
        if company:
            lines.append(f'Company: {company}')
        if position:
            lines.append(f'Position: {position}')
        if purpose:
            lines.append(f'Purpose / Topic: {purpose}')

        lines += [
            '',
            '--- SENDER (YOU) ---',
            f'Name: {sender_name}',
            f'Email: {sender_email}',
        ]
        if sender_company:
            lines.append(f'Company: {sender_company}')

        lines += [
            '',
            'Instructions:',
            '- Write in a professional yet warm tone.',
            '- Keep the email concise (3-5 sentences).',
            '- Start the body with "Dear <First Name>," as the salutation.',
            '- Use proper closing before the system signature.',
            '- NEVER include "To:", "From:", or a signature block in the body.',
            '- NEVER use placeholders like [Your Name], Your Name, or [Your Email].',
            '- If recipient email is not known, address them by name without email.',
            '',
            'Respond ONLY with valid JSON (no markdown, no code fences):',
            '{',
            '  "subject": "<subject line>",',
            '  "body": "<email body — salutation + message + closing line only>"',
            '}',
        ]
        return '\n'.join(lines)

    @staticmethod
    def _strip_reasoning(text):
        """Strip internal reasoning / chain-of-thought from LLM output."""
        if not text:
            return text
        # Remove blocks wrapped in  think...  tags (standard CoT)
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Remove lines that are pure reasoning headers (case-insensitive)
        reasoning_headers = [
            r'think\s*:',
            r'thought\s*:',
            r'reasoning\s*:',
            r'analysis\s*:',
            r'planning\s*:',
            r'internal\s+notes\s*:',
        ]
        pattern = '|'.join(f'(?:{h})' for h in reasoning_headers)
        text = re.sub(
            rf'^(?:{pattern}).*$',
            '', text, flags=re.MULTILINE | re.IGNORECASE,
        ).strip()
        # Collapse repeated blank lines left behind
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _post_process_body(body, sender_name, sender_email):
        if not body:
            return body
        # 1 — Replace all known placeholders with actual sender info
        body = body.replace('[Your Name]', sender_name)
        body = body.replace('[your name]', sender_name)
        body = body.replace('[YOUR NAME]', sender_name)
        body = body.replace('[Your Email]', sender_email or '')
        body = body.replace('[your email]', sender_email or '')
        body = body.replace('[YOUR EMAIL]', sender_email or '')
        body = body.replace('[email address]', sender_email or '')
        body = body.replace('[Email Address]', sender_email or '')
        if sender_name:
            body = body.replace('Your Name', sender_name)
        if sender_email:
            body = body.replace('Your Email', sender_email)

        # 2 — Strip any trailing LLM-generated signature (closing phrase +
        #     optional name/email lines) so the canonical one always wins.
        body = re.sub(
            r'(?:\n\s*)?'
            r'(?:Best\s+regards|Kind\s+regards|Regards|Sincerely|'
            r'Thanks|Thank\s+you|Warmly|Best|Cheers|'
            r'Yours\s+truly|Yours\s+sincerely|Respectfully)'
            r'[,!.]?[ \t]*'
            r'(?:\n.*)?$',
            '', body, flags=re.IGNORECASE | re.DOTALL,
        ).strip()

        # 3 — Append canonical sender signature
        sig = f'Best regards,\n\n{sender_name}'
        if sender_email:
            sig += f'\n{sender_email}'
        if body:
            return body + '\n\n' + sig
        return sig

    def _parse_json_response(self, text):
        cleaned = text.strip()
        if cleaned.startswith('```') and '```' in cleaned[3:]:
            start = cleaned.find('\n') + 1
            end = cleaned.rfind('```')
            cleaned = cleaned[start:end].strip()
        import json
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

    def _find_matching_people(self, name, user):
        """Search across every CRM module that could reference a person.
        Returns a list of dicts {source, name, email, company, position}
        ordered by module priority (structured person data first)."""
        seen = set()
        results = []

        def add(source, obj):
            key = (type(obj).__name__, obj.pk)
            if key not in seen:
                seen.add(key)
                pname = (
                    obj.full_name
                    if hasattr(obj, 'full_name')
                    else obj.lead_name
                )
                results.append({
                    'source': source,
                    'name': pname,
                    'email': (obj.email or '').strip(),
                    'company': (obj.company or '').strip(),
                    'position': (obj.job_title or '').strip() if hasattr(obj, 'job_title') else '',
                })

        def add_owner(source, obj):
            """Extract the owner (User FK) as the person for entity modules."""
            key = (type(obj).__name__, obj.pk)
            if key not in seen:
                seen.add(key)
                owner = getattr(obj, 'owner', None)
                if owner:
                    oname = owner.get_full_name() or owner.username
                    oemail = (owner.email or '').strip()
                    results.append({
                        'source': source,
                        'name': oname,
                        'email': oemail,
                        'company': '',
                        'position': '',
                    })
                # If no owner, skip (no person data to extract)

        def add_linked_person(source, obj, field_name):
            """Extract a linked Contact or Lead as the person."""
            related = getattr(obj, field_name, None)
            if related:
                key = (type(related).__name__, related.pk)
                if key not in seen:
                    seen.add(key)
                    pname = (
                        related.full_name
                        if hasattr(related, 'full_name')
                        else getattr(related, 'lead_name', str(related))
                    )
                    results.append({
                        'source': source,
                        'name': pname,
                        'email': (getattr(related, 'email', '') or '').strip(),
                        'company': (getattr(related, 'company', '') or '').strip(),
                        'position': (getattr(related, 'job_title', '') or '').strip(),
                    })

        from contacts.models import Contact
        from leads.models import Lead
        from calendars.models import Event
        from tasks.models import Task
        from campaigns.models import Campaign
        from workflows.models import Workflow, Notification

        # ── 1. Contacts (structured person data) ──
        for c in user.contacts.filter(full_name__icontains=name):
            add('Contact', c)

        # ── 2. Leads (structured person data) ──
        for l in user.leads.filter(lead_name__icontains=name):
            add('Lead', l)
        for l in user.leads.filter(contact_person__icontains=name):
            add('Lead', l)

        # ── 3. Events → linked Contact / Lead / Owner ──
        for e in user.events.filter(
            contact__full_name__icontains=name,
        ).select_related('contact'):
            add_linked_person('Event', e, 'contact')
        for e in user.events.filter(
            lead__lead_name__icontains=name,
        ).select_related('lead'):
            add_linked_person('Event', e, 'lead')
        for e in user.events.filter(title__icontains=name).select_related('owner'):
            add_owner('Event', e)

        # ── 4. Tasks → linked Contact / Lead / Owner ──
        for t in user.tasks.filter(
            contact__full_name__icontains=name,
        ).select_related('contact'):
            add_linked_person('Task', t, 'contact')
        for t in user.tasks.filter(
            lead__lead_name__icontains=name,
        ).select_related('lead'):
            add_linked_person('Task', t, 'lead')
        for t in user.tasks.filter(title__icontains=name).select_related('owner'):
            add_owner('Task', t)

        # ── 5. Campaigns ──
        for c in user.campaigns.filter(name__icontains=name).select_related('owner'):
            add_owner('Campaign', c)
        for c in user.campaigns.filter(subject__icontains=name).select_related('owner'):
            add_owner('Campaign', c)

        # ── 6. Workflows ──
        for w in user.workflows.filter(name__icontains=name).select_related('owner'):
            add_owner('Workflow', w)
        for w in user.workflows.filter(description__icontains=name).select_related('owner'):
            add_owner('Workflow', w)

        # ── 7. Notifications ──
        for n in user.notifications.filter(title__icontains=name).select_related('owner'):
            add_owner('Notification', n)
        for n in user.notifications.filter(message__icontains=name).select_related('owner'):
            add_owner('Notification', n)

        return results

    def execute(self, text, user):
        if not user or not user.is_authenticated:
            return None

        params = self._parse(text)
        recipient_name = params.get('recipient', '').strip()
        email_addr = params.get('email_address', '').strip() or None
        purpose = params.get('purpose', '').strip()

        if email_addr:
            # Direct email provided — skip CRM module search
            if not recipient_name:
                recipient_name = email_addr.split('@')[0]
            company_name = None
        else:
            if not recipient_name:
                return (
                    'Who would you like to send the email to? '
                    'Please provide a recipient name or email address.'
                )

            # Search across CRM modules
            people = self._find_matching_people(recipient_name, user)

            if not people:
                return (
                    "I couldn't find this person in your CRM.\n\n"
                    'Please provide an email address.'
                )

            if len(people) > 1:
                lines = [
                    f'I found multiple people matching **"{recipient_name}"**:',
                    '',
                ]
                for idx, p in enumerate(people, 1):
                    lines.append(f'{idx}.')
                    lines.append(p['name'])
                    lines.append(f'({p["source"]})')
                    if p['email']:
                        lines.append(p['email'])
                    lines.append('')
                lines.append('Which one would you like to email? Please specify.')
                return '\n'.join(lines)

            person = people[0]
            recipient_name = person['name']
            email_addr = person['email'] or None
            company_name = person['company'] or None
            position_name = person.get('position') or None

        # Retrieve logged-in sender info
        sender_name = user.get_full_name() or user.username
        sender_email = user.email or ''
        sender_company = (getattr(user, 'company', None) or '').strip() or None

        # Build prompt and call LLM
        prompt = self._build_prompt(
            recipient_name, email_addr, company_name, position_name, purpose,
            sender_name, sender_email, sender_company,
        )

        from assistant.services.ai_service import AIService
        from assistant.services.ai_crm_service import MockMessage
        ai = AIService()
        raw = ai.generate_response([MockMessage('user', prompt)])

        # Strip any internal reasoning / chain-of-thought before display
        raw = self._strip_reasoning(raw)

        # Parse JSON or fall back to raw text
        result = self._parse_json_response(raw)
        if result:
            subject = result.get('subject', '').strip()
            body = result.get('body', '').strip()
        else:
            subject = ''
            body = raw.strip()

        # Replace any hallucinated placeholders with real sender info
        body = self._post_process_body(body, sender_name, sender_email)

        to_lines = ['To:']
        if email_addr:
            to_lines.append(f'{recipient_name} <{email_addr}>')
        else:
            to_lines.append(recipient_name)

        from_lines = ['From:']
        from_lines.append(f'{sender_name} <{sender_email}>')

        lines = ['\n'.join(to_lines), '', '\n'.join(from_lines), '']
        if subject:
            lines.append(f'Subject:\n{subject}')
            lines.append('')
        lines.append('Body:')
        lines.append('')
        lines.append(body)
        return '\n'.join(lines)
