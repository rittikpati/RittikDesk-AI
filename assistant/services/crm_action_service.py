import json
import logging
import time
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from .ai_service import AIService

logger = logging.getLogger(__name__)

User = get_user_model()

ACTION_KEYWORDS = frozenset({
    'create', 'add', 'new', 'make', 'schedule', 'set', 'assign',
    'delete', 'remove', 'erase', 'destroy', 'cancel',
    'update', 'edit', 'change', 'modify', 'rename',
    'mark', 'complete', 'finish', 'done',
    'archive', 'pause', 'resume', 'reopen', 'unarchive',
    'search', 'find', 'lookup',
})

DESTRUCTIVE_ACTIONS = frozenset({
    'delete_task', 'delete_contact', 'delete_lead',
    'delete_event', 'archive_campaign',
})

CONFIRMATION_PREFIX = '__confirm__'


def _user_full_name(u):
    return u.get_full_name() or u.email.split('@')[0]


class CRMActionError(Exception):
    pass


class CRMActionService:
    _pending = {}

    def __init__(self, user):
        self.user = user

    # ── Pending confirmation management ──

    @classmethod
    def _pending_key(cls, conversation_pk):
        return f'crm_action:{conversation_pk}'

    @classmethod
    def set_pending(cls, conversation_pk, data):
        cls._pending[cls._pending_key(conversation_pk)] = {
            'data': data,
            'ts': time.time(),
        }

    @classmethod
    def get_pending(cls, conversation_pk):
        entry = cls._pending.get(cls._pending_key(conversation_pk))
        if entry and time.time() - entry['ts'] < 300:
            return entry['data']
        return None

    @classmethod
    def clear_pending(cls, conversation_pk):
        cls._pending.pop(cls._pending_key(conversation_pk), None)

    @classmethod
    def is_confirmation(cls, text):
        lowered = text.strip().lower()
        return lowered in {'yes', 'yeah', 'yep', 'sure', 'ok', 'okay',
                           'confirm', 'do it', 'go ahead', 'yes please'}

    @classmethod
    def is_denial(cls, text):
        lowered = text.strip().lower()
        return lowered in {'no', 'nope', 'nah', 'cancel', 'stop',
                           "don't", "dont", "never mind", "forget it"}

    # ── Intent detection ──

    def has_action_keywords(self, text):
        text_lower = text.lower()
        return any(kw in text_lower for kw in ACTION_KEYWORDS)

    def parse_action(self, text):
        """Use LLM to parse natural language into a structured action.

        Returns dict with keys: action, params, needs_confirmation
        or None if not an action.
        """
        today = date.today()
        now = datetime.now()
        prompt = (
            f'Analyze the user message below. If they want to perform a CRM '
            f'action, return ONLY valid JSON with no extra text.\n\n'
            f'User message: {text}\n\n'
            f'Today is {today}. Current time is {now.strftime("%H:%M")}.\n\n'
            f'Return JSON:\n'
            f'{{"action": "action_type", "params": {{...}}, '
            f'"needs_confirmation": true/false}}\n\n'
            f'Available actions with required params:\n\n'
            f'create_task — title (required), description, due_date (YYYY-MM-DD), '
            f'due_time (HH:MM), priority (low/medium/high)\n'
            f'update_task — task_id or task_title (required to find the task), '
            f'title, description, due_date, due_time, priority\n'
            f'delete_task — task_id or task_title (required)\n'
            f'complete_task — task_id or task_title (required)\n'
            f'reopen_task — task_id or task_title (required)\n\n'
            f'create_contact — full_name (required), company, job_title, '
            f'email, phone, tags, notes\n'
            f'edit_contact — contact_id or contact_name (required), '
            f'full_name, company, job_title, email, phone\n'
            f'delete_contact — contact_id or contact_name (required)\n'
            f'search_contact — query (required, name/email/company)\n\n'
            f'create_lead — lead_name (required), company, contact_person, '
            f'email, phone, expected_revenue (number), priority (Low/Medium/High/Urgent), '
            f'source (Website/Referral/LinkedIn/Facebook/Instagram/Cold Email/Event/Other)\n'
            f'update_lead_status — lead_id or lead_name (required), '
            f'status (required: New/Contacted/Qualified/Proposal Sent/Negotiation/Won/Lost)\n'
            f'delete_lead — lead_id or lead_name (required)\n'
            f'assign_lead — lead_id or lead_name (required), '
            f'assigned_to (required, name or email of user)\n\n'
            f'create_event — title (required), start_date (required, YYYY-MM-DD), '
            f'start_time (HH:MM), end_time (HH:MM), '
            f'event_type (meeting/call/reminder/personal), description, location\n'
            f'update_event — event_id or event_title (required), '
            f'title, start_date, start_time\n'
            f'delete_event — event_id or event_title (required)\n\n'
            f'create_campaign — name (required), subject (required), body\n'
            f'pause_campaign — campaign_id or campaign_name (required)\n'
            f'resume_campaign — campaign_id or campaign_name (required)\n'
            f'archive_campaign — campaign_id or campaign_name (required)\n\n'
            f'needs_confirmation must be true for: '
            f'delete_task, delete_contact, delete_lead, delete_event, archive_campaign.\n'
            f'For everything else set needs_confirmation to false.\n\n'
            f'If the user is NOT requesting a CRM action, return: '
            f'{{"action": null}}'
        )

        service = AIService()
        raw = service.generate_response([_msg('user', prompt)])
        if not raw:
            return None

        cleaned = raw.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[-1]
            cleaned = cleaned.rsplit('```', 1)[0]
        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning('Action parse JSON failed: %s', raw[:200])
            return None

        if not parsed.get('action'):
            return None
        return parsed

    # ── Execution ──

    def execute(self, action_data, conversation_pk=None):
        action_type = action_data['action']
        params = action_data.get('params', {})

        if action_type in DESTRUCTIVE_ACTIONS and conversation_pk:
            pending = self.get_pending(conversation_pk)
            if not pending:
                self.set_pending(conversation_pk, action_data)
                obj_name = self._describe_target(action_type, params)
                return {
                    'type': 'confirmation',
                    'message': (
                        f"Are you sure you want to {self._action_verb(action_type)} "
                        f"'{obj_name}'? Reply **yes** to confirm or **no** to cancel."
                    ),
                }

        try:
            result = self._dispatch(action_type, params)
            self.clear_pending(conversation_pk)
            return {'type': 'success', 'message': result}
        except CRMActionError as e:
            self.clear_pending(conversation_pk)
            return {'type': 'error', 'message': str(e)}

    def execute_pending(self, conversation_pk):
        pending = self.get_pending(conversation_pk)
        if not pending:
            return {
                'type': 'error',
                'message': (
                    "I don't have any pending action to confirm. "
                    "What would you like to do?"
                ),
            }
        return self.execute(pending, conversation_pk)

    def _dispatch(self, action_type, params):
        m = {
            'create_task': self._create_task,
            'update_task': self._update_task,
            'delete_task': self._delete_task,
            'complete_task': self._complete_task,
            'reopen_task': self._reopen_task,
            'create_contact': self._create_contact,
            'edit_contact': self._edit_contact,
            'delete_contact': self._delete_contact,
            'search_contact': self._search_contact,
            'create_lead': self._create_lead,
            'update_lead_status': self._update_lead_status,
            'delete_lead': self._delete_lead,
            'assign_lead': self._assign_lead,
            'create_event': self._create_event,
            'update_event': self._update_event,
            'delete_event': self._delete_event,
            'create_campaign': self._create_campaign,
            'pause_campaign': self._pause_campaign,
            'resume_campaign': self._resume_campaign,
            'archive_campaign': self._archive_campaign,
        }
        handler = m.get(action_type)
        if not handler:
            raise CRMActionError(f"Unknown action '{action_type}'.")
        return handler(params)

    def _describe_target(self, action_type, params):
        for key in ('task_title', 'contact_name', 'lead_name',
                    'event_title', 'campaign_name', 'task_id',
                    'contact_id', 'lead_id', 'event_id', 'campaign_id'):
            val = params.get(key)
            if val:
                return str(val)
        return 'this item'

    def _action_verb(self, action_type):
        verbs = {
            'delete_task': 'delete task', 'delete_contact': 'delete contact',
            'delete_lead': 'delete lead', 'delete_event': 'delete event',
            'archive_campaign': 'archive campaign',
        }
        return verbs.get(action_type, 'perform')

    # ── Task operations ──

    def _find_task(self, identifier):
        qs = self.user.tasks.all()
        if isinstance(identifier, int) or identifier.isdigit():
            obj = qs.filter(pk=int(identifier)).first()
            if obj:
                return obj
        return qs.filter(
            Q(title__iexact=identifier) | Q(title__icontains=identifier)
        ).first()

    @transaction.atomic
    def _create_task(self, p):
        title = p.get('title', '').strip()
        if not title:
            raise CRMActionError(
                "I need a title to create a task. "
                "What should the task be called?"
            )
        task = self.user.tasks.create(
            title=title,
            description=p.get('description', ''),
            due_date=self._parse_date(p.get('due_date')),
            due_time=self._parse_time(p.get('due_time')),
            priority=p.get('priority', 'medium'),
        )
        logger.info('Task created: pk=%s user=%s', task.pk, self.user)
        due = ''
        if task.due_date:
            due = f' due {task.due_date}'
            if task.due_time:
                due += f' at {task.due_time}'
        return f"Task '{task.title}' created successfully.{due}"

    @transaction.atomic
    def _update_task(self, p):
        task = self._find_task(p.get('task_id') or p.get('task_title') or '')
        if not task:
            raise CRMActionError(
                "I couldn't find that task. "
                "Please check the task name and try again."
            )
        changed = []
        if p.get('title'):
            task.title = p['title']
            changed.append('title')
        if 'description' in p:
            task.description = p.get('description', '')
            changed.append('description')
        if 'due_date' in p:
            task.due_date = self._parse_date(p['due_date'])
            changed.append('due date')
        if 'due_time' in p:
            task.due_time = self._parse_time(p['due_time'])
            changed.append('due time')
        if p.get('priority'):
            task.priority = p['priority']
            changed.append('priority')
        if changed:
            task.save(update_fields=changed)
        logger.info('Task updated: pk=%s fields=%s', task.pk, changed)
        return f"Task '{task.title}' updated successfully."

    @transaction.atomic
    def _delete_task(self, p):
        task = self._find_task(p.get('task_id') or p.get('task_title') or '')
        if not task:
            raise CRMActionError(
                "I couldn't find that task to delete it."
            )
        title = task.title
        task.delete()
        logger.info('Task deleted: pk=%s user=%s', task.pk, self.user)
        return f"Task '{title}' has been deleted."

    @transaction.atomic
    def _complete_task(self, p):
        task = self._find_task(p.get('task_id') or p.get('task_title') or '')
        if not task:
            raise CRMActionError(
                "I couldn't find that task. "
                "Please check the task name and try again."
            )
        task.status = 'completed'
        task.save(update_fields=['status'])
        logger.info('Task completed: pk=%s', task.pk)
        return f"Task '{task.title}' marked as completed."

    @transaction.atomic
    def _reopen_task(self, p):
        task = self._find_task(p.get('task_id') or p.get('task_title') or '')
        if not task:
            raise CRMActionError(
                "I couldn't find that task to reopen it."
            )
        task.status = 'pending'
        task.save(update_fields=['status'])
        logger.info('Task reopened: pk=%s', task.pk)
        return f"Task '{task.title}' has been reopened."

    # ── Contact operations ──

    def _find_contact(self, identifier):
        qs = self.user.contacts.all()
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            obj = qs.filter(pk=int(identifier)).first()
            if obj:
                return obj
        return qs.filter(
            Q(full_name__iexact=identifier)
            | Q(full_name__icontains=identifier)
            | Q(email__iexact=identifier)
        ).first()

    @transaction.atomic
    def _create_contact(self, p):
        name = p.get('full_name', '').strip()
        if not name:
            raise CRMActionError(
                "I need a name to create a contact. "
                "What's the person's name?"
            )
        email = p.get('email', '').strip()
        if email:
            exists = self.user.contacts.filter(email__iexact=email).exists()
            if exists:
                raise CRMActionError(
                    f"A contact with email '{email}' already exists."
                )
        contact = self.user.contacts.create(
            full_name=name,
            company=p.get('company', ''),
            job_title=p.get('job_title', ''),
            email=email,
            phone=p.get('phone', ''),
            tags=p.get('tags', ''),
            notes=p.get('notes', ''),
        )
        logger.info('Contact created: pk=%s', contact.pk)
        return f"Contact '{contact.full_name}' added successfully."

    @transaction.atomic
    def _edit_contact(self, p):
        contact = self._find_contact(
            p.get('contact_id') or p.get('contact_name') or ''
        )
        if not contact:
            raise CRMActionError(
                "I couldn't find that contact. "
                "Please check the name and try again."
            )
        changed = []
        if p.get('full_name'):
            contact.full_name = p['full_name']
            changed.append('full_name')
        if p.get('company'):
            contact.company = p['company']
            changed.append('company')
        if p.get('job_title'):
            contact.job_title = p['job_title']
            changed.append('job_title')
        if 'email' in p:
            new_email = p.get('email', '').strip()
            if new_email and new_email != contact.email:
                exists = self.user.contacts.filter(
                    email__iexact=new_email
                ).exclude(pk=contact.pk).exists()
                if exists:
                    raise CRMActionError(
                        f"Another contact already uses '{new_email}'."
                    )
            contact.email = new_email
            changed.append('email')
        if 'phone' in p:
            contact.phone = p.get('phone', '')
            changed.append('phone')
        if changed:
            contact.save(update_fields=changed)
        logger.info('Contact updated: pk=%s', contact.pk)
        return f"Contact '{contact.full_name}' updated successfully."

    @transaction.atomic
    def _delete_contact(self, p):
        contact = self._find_contact(
            p.get('contact_id') or p.get('contact_name') or ''
        )
        if not contact:
            raise CRMActionError(
                "I couldn't find that contact to delete."
            )
        name = contact.full_name
        contact.delete()
        logger.info('Contact deleted: pk=%s', contact.pk)
        return f"Contact '{name}' has been deleted."

    def _search_contact(self, p):
        query = p.get('query', '').strip()
        if not query:
            raise CRMActionError(
                "Please tell me who you're looking for — "
                "a name, email, or company."
            )
        results = self.user.contacts.filter(
            Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(company__icontains=query)
            | Q(phone__icontains=query)
        )[:5]
        if not results:
            return f"I couldn't find any contacts matching '{query}'."
        lines = [f"Here are the contacts matching '{query}':"]
        for c in results:
            details = []
            if c.email:
                details.append(c.email)
            if c.phone:
                details.append(c.phone)
            if c.company:
                details.append(c.company)
            extra = f' ({", ".join(details)})' if details else ''
            lines.append(f"  - {c.full_name}{extra}")
        return '\n'.join(lines)

    # ── Lead operations ──

    def _find_lead(self, identifier):
        qs = self.user.leads.all()
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            obj = qs.filter(pk=int(identifier)).first()
            if obj:
                return obj
        return qs.filter(
            Q(lead_name__iexact=identifier)
            | Q(lead_name__icontains=identifier)
            | Q(company__iexact=identifier)
        ).first()

    @transaction.atomic
    def _create_lead(self, p):
        name = p.get('lead_name', '').strip()
        if not name:
            raise CRMActionError(
                "I need a name to create a lead. "
                "What's the lead's name or company?"
            )
        lead = self.user.leads.create(
            lead_name=name,
            company=p.get('company', ''),
            contact_person=p.get('contact_person', ''),
            email=p.get('email', ''),
            phone=p.get('phone', ''),
            priority=p.get('priority', 'Medium'),
            source=p.get('source', 'Website'),
            expected_revenue=self._parse_number(p.get('expected_revenue')),
        )
        logger.info('Lead created: pk=%s', lead.pk)
        return f"Lead '{lead.lead_name}' created successfully."

    @transaction.atomic
    def _update_lead_status(self, p):
        lead = self._find_lead(
            p.get('lead_id') or p.get('lead_name') or ''
        )
        if not lead:
            raise CRMActionError(
                "I couldn't find that lead. "
                "Please check the name and try again."
            )
        new_status = p.get('status', '').strip()
        valid_statuses = [
            'New', 'Contacted', 'Qualified', 'Proposal Sent',
            'Negotiation', 'Won', 'Lost',
        ]
        if new_status not in valid_statuses:
            raise CRMActionError(
                f"'{new_status}' is not a valid lead status. "
                f"Valid options: {', '.join(valid_statuses)}."
            )
        lead.status = new_status
        lead.save(update_fields=['status'])
        logger.info('Lead status updated: pk=%s status=%s', lead.pk, new_status)
        return (
            f"Lead '{lead.lead_name}' status updated to **{new_status}**."
        )

    @transaction.atomic
    def _delete_lead(self, p):
        lead = self._find_lead(
            p.get('lead_id') or p.get('lead_name') or ''
        )
        if not lead:
            raise CRMActionError(
                "I couldn't find that lead to delete."
            )
        name = lead.lead_name
        lead.delete()
        logger.info('Lead deleted: pk=%s', lead.pk)
        return f"Lead '{name}' has been deleted."

    @transaction.atomic
    def _assign_lead(self, p):
        lead = self._find_lead(
            p.get('lead_id') or p.get('lead_name') or ''
        )
        if not lead:
            raise CRMActionError(
                "I couldn't find that lead to assign."
            )
        assign_to = p.get('assigned_to', '').strip()
        if not assign_to:
            raise CRMActionError(
                "Who should I assign this lead to? "
                "Please provide a name or email."
            )
        target = User.objects.filter(
            Q(email__iexact=assign_to)
            | Q(username__iexact=assign_to)
            | Q(first_name__icontains=assign_to)
            | Q(email__icontains=assign_to)
        ).exclude(is_active=False).first()
        if not target:
            raise CRMActionError(
                f"I couldn't find a user matching '{assign_to}'. "
                "Please check the name and try again."
            )
        lead.assigned_user = target
        lead.save(update_fields=['assigned_user'])
        name_display = _user_full_name(target)
        logger.info(
            'Lead assigned: pk=%s assigned_to=%s',
            lead.pk, target.pk,
        )
        return (
            f"Lead '{lead.lead_name}' assigned to **{name_display}**."
        )

    # ── Event operations ──

    def _find_event(self, identifier):
        qs = self.user.events.all()
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            obj = qs.filter(pk=int(identifier)).first()
            if obj:
                return obj
        return qs.filter(
            Q(title__iexact=identifier) | Q(title__icontains=identifier)
        ).first()

    @transaction.atomic
    def _create_event(self, p):
        title = p.get('title', '').strip()
        if not title:
            raise CRMActionError(
                "I need a title to create an event. "
                "What's the event called?"
            )
        start_date = self._parse_date(p.get('start_date'))
        if not start_date:
            raise CRMActionError(
                "I need a date for the event. "
                "When is it scheduled?"
            )
        event = self.user.events.create(
            title=title,
            description=p.get('description', ''),
            start_date=start_date,
            start_time=self._parse_time(p.get('start_time')),
            end_time=self._parse_time(p.get('end_time')),
            event_type=p.get('event_type', 'meeting'),
            location=p.get('location', ''),
        )
        logger.info('Event created: pk=%s', event.pk)
        time_str = f' at {event.start_time}' if event.start_time else ''
        return (
            f"Event '{event.title}' scheduled for "
            f"**{event.start_date}{time_str}**."
        )

    @transaction.atomic
    def _update_event(self, p):
        event = self._find_event(
            p.get('event_id') or p.get('event_title') or ''
        )
        if not event:
            raise CRMActionError(
                "I couldn't find that event. "
                "Please check the name and try again."
            )
        changed = []
        if p.get('title'):
            event.title = p['title']
            changed.append('title')
        if 'start_date' in p:
            parsed = self._parse_date(p['start_date'])
            if parsed:
                event.start_date = parsed
                changed.append('start_date')
        if 'start_time' in p:
            parsed = self._parse_time(p['start_time'])
            if parsed:
                event.start_time = parsed
                changed.append('start_time')
        if changed:
            event.save(update_fields=changed)
        return f"Event '{event.title}' updated successfully."

    @transaction.atomic
    def _delete_event(self, p):
        event = self._find_event(
            p.get('event_id') or p.get('event_title') or ''
        )
        if not event:
            raise CRMActionError(
                "I couldn't find that event to delete."
            )
        title = event.title
        event.delete()
        logger.info('Event deleted: pk=%s', event.pk)
        return f"Event '{title}' has been deleted."

    # ── Campaign operations ──

    def _find_campaign(self, identifier):
        qs = self.user.campaigns.all()
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            obj = qs.filter(pk=int(identifier)).first()
            if obj:
                return obj
        return qs.filter(
            Q(name__iexact=identifier) | Q(name__icontains=identifier)
        ).first()

    @transaction.atomic
    def _create_campaign(self, p):
        name = p.get('name', '').strip()
        subject = p.get('subject', '').strip()
        if not name:
            raise CRMActionError(
                "I need a name to create a campaign. "
                "What should the campaign be called?"
            )
        if not subject:
            raise CRMActionError(
                "I need a subject line for the campaign email."
            )
        campaign = self.user.campaigns.create(
            name=name,
            subject=subject,
            body=p.get('body', ''),
        )
        logger.info('Campaign created: pk=%s', campaign.pk)
        return f"Campaign '{campaign.name}' created successfully."

    @transaction.atomic
    def _pause_campaign(self, p):
        campaign = self._find_campaign(
            p.get('campaign_id') or p.get('campaign_name') or ''
        )
        if not campaign:
            raise CRMActionError(
                "I couldn't find that campaign."
            )
        campaign.status = 'Draft'
        campaign.save(update_fields=['status'])
        logger.info('Campaign paused: pk=%s', campaign.pk)
        return f"Campaign '{campaign.name}' has been paused."

    @transaction.atomic
    def _resume_campaign(self, p):
        campaign = self._find_campaign(
            p.get('campaign_id') or p.get('campaign_name') or ''
        )
        if not campaign:
            raise CRMActionError(
                "I couldn't find that campaign."
            )
        campaign.status = 'Scheduled'
        campaign.save(update_fields=['status'])
        logger.info('Campaign resumed: pk=%s', campaign.pk)
        return f"Campaign '{campaign.name}' has been resumed."

    @transaction.atomic
    def _archive_campaign(self, p):
        campaign = self._find_campaign(
            p.get('campaign_id') or p.get('campaign_name') or ''
        )
        if not campaign:
            raise CRMActionError(
                "I couldn't find that campaign to archive."
            )
        name = campaign.name
        campaign.delete()
        logger.info('Campaign archived: pk=%s', campaign.pk)
        return f"Campaign '{name}' has been archived."

    # ── Helpers ──

    @staticmethod
    def _parse_date(val):
        if not val:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        val = str(val).strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d',
                     '%d-%m-%Y', '%m-%d-%Y'):
            try:
                return datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_time(val):
        if not val:
            return None
        if hasattr(val, 'strftime'):
            return val
        val = str(val).strip()
        for fmt in ('%H:%M', '%I:%M %p', '%I:%M%p', '%H:%M:%S'):
            try:
                return datetime.strptime(val, fmt).time()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_number(val):
        if not val:
            return None
        try:
            return float(str(val).replace(',', '').replace('₹', '').replace('$', ''))
        except (ValueError, TypeError):
            return None


def _msg(role, content):
    """Minimal message-like object for AIService."""
    return type('_Msg', (), {'role': role, 'content': content})()
