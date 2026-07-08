"""Action executor — maps action types to handler functions."""

import json
import logging
import re
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from workflows.models import Notification

logger = logging.getLogger(__name__)
User = get_user_model()


class ActionExecutionError(Exception):
    pass


def _resolve_template(text, context):
    """Replace {{ field.path }} with values from the context object."""
    if not text or not context:
        return text or ''

    def replacer(match):
        path = match.group(1).strip()
        obj = context
        for part in path.split('.'):
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict):
                obj = obj.get(part, match.group(0))
            else:
                return match.group(0)
            if callable(obj):
                try:
                    obj = obj()
                except Exception:
                    return match.group(0)
        return str(obj) if obj is not None else ''

    return re.sub(r'\{\{\s*([^}]+)\s*\}\}', replacer, text)


def _resolve_config(config, context):
    """Resolve all template variables in a config dict."""
    resolved = {}
    for key, value in config.items():
        if isinstance(value, str):
            resolved[key] = _resolve_template(value, context)
        elif isinstance(value, dict):
            resolved[key] = _resolve_config(value, context)
        elif isinstance(value, list):
            resolved[key] = [
                _resolve_template(v, context) if isinstance(v, str) else v
                for v in value
            ]
        else:
            resolved[key] = value
    return resolved


def _create_notification(user, title, message='', link=''):
    Notification.objects.create(
        owner=user, title=title, message=message, link=link,
    )


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    val = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def handle_create_task(user, config, context):
    p = _resolve_config(config, context)
    title = p.get('title', '').strip()
    if not title:
        raise ActionExecutionError('Task title is required.')
    offset = p.get('due_date_offset')
    due_date = None
    if offset:
        try:
            due_date = date.today() + timedelta(days=int(offset))
        except (ValueError, TypeError):
            pass
    due_date = _parse_date(p.get('due_date')) or due_date
    task = user.tasks.create(
        title=title,
        description=p.get('description', ''),
        due_date=due_date,
        priority=p.get('priority', 'medium'),
    )
    _create_notification(
        user, f'Task Created: {task.title}',
        f'Workflow created task "{task.title}".',
    )
    logger.info('Workflow create_task: pk=%s', task.pk)


def handle_update_task(user, config, context):
    p = _resolve_config(config, context)
    identifier = p.get('task_id') or p.get('task_title', '')
    if not identifier:
        raise ActionExecutionError('Task identifier required.')
    qs = user.tasks.all()
    if identifier.isdigit():
        task = qs.filter(pk=int(identifier)).first()
    else:
        task = qs.filter(title__icontains=identifier).first()
    if not task:
        raise ActionExecutionError(f'Task "{identifier}" not found.')
    fields = []
    if p.get('title'):
        task.title = p['title']
        fields.append('title')
    if p.get('status'):
        task.status = p['status']
        fields.append('status')
    if p.get('priority'):
        task.priority = p['priority']
        fields.append('priority')
    if p.get('description'):
        task.description = p['description']
        fields.append('description')
    if fields:
        task.save(update_fields=fields)
    logger.info('Workflow update_task: pk=%s fields=%s', task.pk, fields)


def handle_create_event(user, config, context):
    p = _resolve_config(config, context)
    title = p.get('title', '').strip()
    if not title:
        raise ActionExecutionError('Event title required.')
    start_date = _parse_date(p.get('start_date')) or date.today()
    event = user.events.create(
        title=title,
        description=p.get('description', ''),
        start_date=start_date,
        start_time=p.get('start_time'),
        event_type=p.get('event_type', 'meeting'),
        location=p.get('location', ''),
    )
    _create_notification(
        user, f'Event Created: {event.title}',
        f'Scheduled for {event.start_date}.',
    )
    logger.info('Workflow create_event: pk=%s', event.pk)


def handle_assign_lead(user, config, context):
    p = _resolve_config(config, context)
    identifier = p.get('lead_id') or p.get('lead_name', '')
    if not identifier:
        raise ActionExecutionError('Lead identifier required.')
    qs = user.leads.all()
    if identifier.isdigit():
        lead = qs.filter(pk=int(identifier)).first()
    else:
        lead = qs.filter(lead_name__icontains=identifier).first()
    if not lead:
        raise ActionExecutionError(f'Lead "{identifier}" not found.')
    assign_to = p.get('assigned_to', '')
    if assign_to:
        target = User.objects.filter(
            email__iexact=assign_to,
        ).exclude(is_active=False).first()
        if target:
            lead.assigned_user = target
            lead.save(update_fields=['assigned_user'])
    logger.info('Workflow assign_lead: pk=%s', lead.pk)


def handle_change_lead_status(user, config, context):
    p = _resolve_config(config, context)
    identifier = p.get('lead_id') or p.get('lead_name', '')
    if not identifier:
        raise ActionExecutionError('Lead identifier required.')
    qs = user.leads.all()
    if identifier.isdigit():
        lead = qs.filter(pk=int(identifier)).first()
    else:
        lead = qs.filter(lead_name__icontains=identifier).first()
    if not lead:
        raise ActionExecutionError(f'Lead "{identifier}" not found.')
    new_status = p.get('status', '').strip()
    if new_status:
        lead.status = new_status
        lead.save(update_fields=['status'])
    logger.info('Workflow change_lead_status: pk=%s -> %s', lead.pk, new_status)


def handle_add_tag(user, config, context):
    p = _resolve_config(config, context)
    tags = p.get('tags', '').strip()
    if not tags:
        return
    target_type = p.get('target_type', 'contact')
    if target_type == 'lead':
        identifier = p.get('lead_id') or p.get('lead_name', '')
        qs = user.leads.all()
        if identifier.isdigit():
            obj = qs.filter(pk=int(identifier)).first()
        else:
            obj = qs.filter(lead_name__icontains=identifier).first()
    else:
        identifier = p.get('contact_id') or p.get('contact_name', '')
        qs = user.contacts.all()
        if identifier.isdigit():
            obj = qs.filter(pk=int(identifier)).first()
        else:
            obj = qs.filter(full_name__icontains=identifier).first()
    if not obj:
        return
    existing = set(obj.tag_list()) if hasattr(obj, 'tag_list') else set()
    for t in tags.split(','):
        t = t.strip()
        if t:
            existing.add(t)
    obj.tags = ', '.join(existing)
    obj.save(update_fields=['tags'])
    logger.info('Workflow add_tag: %s', obj.pk)


def handle_remove_tag(user, config, context):
    p = _resolve_config(config, context)
    tags = p.get('tags', '').strip()
    if not tags:
        return
    target_type = p.get('target_type', 'contact')
    if target_type == 'lead':
        identifier = p.get('lead_id') or p.get('lead_name', '')
        qs = user.leads.all()
        if identifier.isdigit():
            obj = qs.filter(pk=int(identifier)).first()
        else:
            obj = qs.filter(lead_name__icontains=identifier).first()
    else:
        identifier = p.get('contact_id') or p.get('contact_name', '')
        qs = user.contacts.all()
        if identifier.isdigit():
            obj = qs.filter(pk=int(identifier)).first()
        else:
            obj = qs.filter(full_name__icontains=identifier).first()
    if not obj:
        return
    existing = set(obj.tag_list()) if hasattr(obj, 'tag_list') else set()
    remove_set = {t.strip() for t in tags.split(',') if t.strip()}
    remaining = existing - remove_set
    obj.tags = ', '.join(remaining)
    obj.save(update_fields=['tags'])
    logger.info('Workflow remove_tag: %s', obj.pk)


def handle_create_notification(user, config, context):
    p = _resolve_config(config, context)
    title = p.get('title', 'Workflow Notification')
    message = p.get('message', '')
    link = p.get('link', '')
    _create_notification(user, title, message, link)


def handle_webhook(user, config, context):
    p = _resolve_config(config, context)
    url = p.get('url', '')
    if not url:
        return
    payload = json.dumps({
        'event': p.get('event', 'workflow_triggered'),
        'timestamp': datetime.now().isoformat(),
        'data': config,
    })
    try:
        import requests
        requests.post(
            url, data=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
    except Exception:
        logger.exception('Webhook failed: %s', url)


ACTION_HANDLERS = {
    'create_task': handle_create_task,
    'update_task': handle_update_task,
    'create_event': handle_create_event,
    'assign_lead': handle_assign_lead,
    'change_lead_status': handle_change_lead_status,
    'add_tag': handle_add_tag,
    'remove_tag': handle_remove_tag,
    'create_notification': handle_create_notification,
    'webhook': handle_webhook,
}


def execute_action(user, action_type, config, context):
    handler = ACTION_HANDLERS.get(action_type)
    if not handler:
        logger.warning('No handler for action type: %s', action_type)
        return
    handler(user, config, context)
