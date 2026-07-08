"""AI-powered workflow actions using the assistant's AI services."""

import json
import logging

from assistant.services.ai_crm_service import AICRMService, MockMessage
from workflows.models import Notification
from workflows.services.actions import _create_notification, ActionExecutionError

logger = logging.getLogger(__name__)


def _get_ai_service():
    return AICRMService()


def _make_msg(role, content):
    return MockMessage(role=role, content=content)


def handle_ai_summary(user, config, context):
    obj = context.get('object')
    if not obj:
        return
    model_name = context.get('model_name', 'record')
    prompt = (
        f'Generate a concise professional summary for this {model_name}:\n\n'
        f'{json.dumps(_serialize(obj), indent=2, default=str)}'
    )
    try:
        svc = _get_ai_service()
        summary = svc._call([_make_msg('user', prompt)])
    except Exception:
        logger.exception('AI summary failed')
        _create_notification(user, 'AI Summary Failed',
                             f'Could not generate summary for {model_name}.')
        return
    _create_notification(
        user, f'AI Summary: {getattr(obj, "name", getattr(obj, "title", model_name))}',
        summary[:300],
    )


def handle_ai_email(user, config, context):
    obj = context.get('object')
    if not obj:
        return
    email_type = config.get('email_type', 'follow-up')
    contact_name = config.get('contact_name') or getattr(obj, 'contact_person', '') or getattr(obj, 'full_name', 'Customer')
    prompt = (
        f'Write a professional {email_type} email to {contact_name} '
        f'regarding this {context.get("model_name", "record")}:\n\n'
        f'{json.dumps(_serialize(obj), indent=2, default=str)}'
    )
    try:
        svc = _get_ai_service()
        result = svc._call([_make_msg('user', prompt)])
    except Exception:
        logger.exception('AI email failed')
        return
    _create_notification(
        user, f'AI Email: {email_type.capitalize()}',
        f'Generated {email_type} email for {contact_name}.\n\n{result[:500]}',
    )


def handle_ai_followup(user, config, context):
    obj = context.get('object')
    if not obj:
        return
    model_name = context.get('model_name', 'record')
    prompt = (
        f'Suggest 3-5 follow-up actions for this {model_name}:\n\n'
        f'{json.dumps(_serialize(obj), indent=2, default=str)}'
    )
    try:
        svc = _get_ai_service()
        suggestions = svc._call([_make_msg('user', prompt)])
    except Exception:
        logger.exception('AI follow-up failed')
        return
    _create_notification(
        user, f'AI Follow-up: {getattr(obj, "name", getattr(obj, "title", model_name))}',
        suggestions[:500],
    )


def _serialize(obj):
    """Extract relevant fields from a model instance."""
    if obj is None:
        return {}
    fields = {}
    for f in obj._meta.fields:
        name = f.name
        if name in ('id', 'owner', 'assigned_user'):
            continue
        val = getattr(obj, name)
        if hasattr(val, 'strftime'):
            val = str(val)
        fields[name] = val
    return fields


AI_ACTION_HANDLERS = {
    'ai_summary': handle_ai_summary,
    'ai_email': handle_ai_email,
    'ai_followup': handle_ai_followup,
}


def execute_ai_action(user, action_type, config, context):
    handler = AI_ACTION_HANDLERS.get(action_type)
    if not handler:
        return
    handler(user, config, context)
