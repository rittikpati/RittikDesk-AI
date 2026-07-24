"""Core workflow engine — fires triggers, executes workflows."""

import json
import logging
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from workflows.models import (
    Workflow, WorkflowAction, WorkflowExecutionLog, Notification,
)
from workflows.services.actions import execute_action, ActionExecutionError
from workflows.services.ai_actions import execute_ai_action

logger = logging.getLogger(__name__)

AI_ACTIONS = frozenset({'ai_summary', 'ai_email', 'ai_followup'})
SKIPPED_NOTIFICATION_ACTIONS = frozenset({'create_notification'})

_trigger_event_handlers = []


def on_trigger(handler_func):
    """Decorator to register a trigger event handler."""
    _trigger_event_handlers.append(handler_func)
    return handler_func


def fire_trigger(trigger_type, context_object, user=None):
    """Find and execute all active workflows matching this trigger.

    Called from CRM views after an event occurs.
    """
    if user is None:
        if hasattr(context_object, 'owner'):
            user = context_object.owner
        else:
            return

    workflows = Workflow.objects.filter(
        owner=user, trigger_type=trigger_type, is_active=True,
    ).prefetch_related('actions')

    if not workflows:
        return

    context = _build_context(trigger_type, context_object)

    for workflow in workflows:
        _run_workflow(workflow, context, trigger_type)

    for handler in _trigger_event_handlers:
        try:
            handler(trigger_type, context_object, user)
        except Exception:
            logger.exception('Trigger event handler failed: %s', trigger_type)


def fire_trigger_for_user(trigger_type, context_object, user):
    """Explicit user-scoped trigger (used when context_object has no owner)."""
    workflows = Workflow.objects.filter(
        owner=user, trigger_type=trigger_type, is_active=True,
    ).prefetch_related('actions')

    if not workflows:
        return

    context = _build_context(trigger_type, context_object)

    for workflow in workflows:
        _run_workflow(workflow, context, trigger_type)


def _build_context(trigger_type, obj):
    """Build the context dict passed to action handlers."""
    return {
        'trigger_type': trigger_type,
        'object': obj,
        'model_name': obj._meta.verbose_name.title() if hasattr(obj, '_meta') else 'Record',
        'timestamp': datetime.now().isoformat(),
    }


def _run_workflow(workflow, context, trigger_type):
    """Execute all actions in a workflow, with logging."""
    log_entry = WorkflowExecutionLog.objects.create(
        workflow=workflow,
        trigger_type=trigger_type,
        status='running',
    )

    actions = list(workflow.actions.all())
    if not actions:
        log_entry.status = 'success'
        log_entry.completed_at = timezone.now()
        log_entry.save(update_fields=['status', 'completed_at'])
        return

    results = []
    overall_status = 'success'

    for action in actions:
        action_result = _execute_single_action(workflow.owner, action, context)
        results.append({
            'action': action.action_type,
            'order': action.order,
            'status': action_result.get('status'),
            'error': action_result.get('error', ''),
        })
        if action_result.get('status') == 'failed':
            overall_status = 'failed'

    log_entry.status = overall_status
    log_entry.completed_at = timezone.now()
    log_entry.result = {'actions': results}
    log_entry.save(update_fields=['status', 'completed_at', 'result'])

    if overall_status != 'failed':
        Notification.objects.create(
            owner=workflow.owner,
            title=f'Workflow: {workflow.name}',
            message=f'Triggered by {trigger_type}. All actions completed.',
            link='/workflows/',
        )

        try:
            from activities.services import log_activity
            log_activity(
                workflow.owner,
                'workflow_executed',
                name=workflow.name,
                object_id=workflow.pk,
                object_repr=workflow.name,
                detail_url='/workflows/',
                description=f'Workflow "{workflow.name}" triggered by {trigger_type}',
            )
        except Exception:
            logger.debug('Failed to log workflow activity')


def _execute_single_action(user, action, context):
    """Execute one action and return result dict."""
    try:
        if action.action_type in AI_ACTIONS:
            execute_ai_action(user, action.action_type, action.config, context)
        else:
            execute_action(user, action.action_type, action.config, context)
        return {'status': 'success'}
    except ActionExecutionError as e:
        logger.warning(
            'Action failed: workflow=%s action=%s error=%s',
            action.workflow_id, action.pk, e,
        )
        return {'status': 'failed', 'error': str(e)}
    except Exception as e:
        logger.exception(
            'Action error: workflow=%s action=%s', action.workflow_id, action.pk,
        )
        return {'status': 'failed', 'error': str(e)[:500]}
