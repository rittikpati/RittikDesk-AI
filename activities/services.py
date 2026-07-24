"""Lightweight activity logging service.

Usage::

    from activities.services import log_activity
    log_activity(user, activity_type='contact_created', title='Contact "John" created',
                 module='contacts', icon='fa-user-plus', color='#6C63FF',
                 description='Created via dashboard', object_id=42,
                 object_repr='John Doe', detail_url='/contacts/42/')

All parameters except *user* and *title* have sensible defaults.
Silently catches DB errors so logging never breaks the main flow.
"""

import logging

logger = logging.getLogger(__name__)

# ── Predefined activity configs ──────────────────────────────────────

ACTIVITY_TYPES = {
    # Contacts
    'contact_created':  {'module': 'contacts', 'icon': 'fa-user-plus', 'color': '#6C63FF', 'title_tpl': 'Contact "{name}" created'},
    'contact_updated':  {'module': 'contacts', 'icon': 'fa-user-edit', 'color': '#00B4D8', 'title_tpl': 'Contact "{name}" updated'},
    'contact_deleted':  {'module': 'contacts', 'icon': 'fa-user-minus', 'color': '#FF6B6B', 'title_tpl': 'Contact "{name}" deleted'},
    # Companies
    'company_created':  {'module': 'companies', 'icon': 'fa-building', 'color': '#6C63FF', 'title_tpl': 'Company "{name}" created'},
    'company_updated':  {'module': 'companies', 'icon': 'fa-building', 'color': '#00B4D8', 'title_tpl': 'Company "{name}" updated'},
    'company_deleted':  {'module': 'companies', 'icon': 'fa-building', 'color': '#FF6B6B', 'title_tpl': 'Company "{name}" deleted'},
    # Leads
    'lead_created':     {'module': 'leads', 'icon': 'fa-tag', 'color': '#FFB800', 'title_tpl': 'Lead "{name}" created'},
    'lead_updated':     {'module': 'leads', 'icon': 'fa-tag', 'color': '#00B4D8', 'title_tpl': 'Lead "{name}" updated'},
    'lead_converted':   {'module': 'leads', 'icon': 'fa-exchange-alt', 'color': '#00D9A6', 'title_tpl': 'Lead "{name}" converted'},
    'lead_deleted':     {'module': 'leads', 'icon': 'fa-tag', 'color': '#FF6B6B', 'title_tpl': 'Lead "{name}" deleted'},
    # Deals
    'deal_created':     {'module': 'deals', 'icon': 'fa-handshake', 'color': '#8B85FF', 'title_tpl': 'Deal "{name}" created'},
    'deal_stage_changed': {'module': 'deals', 'icon': 'fa-arrow-right', 'color': '#FFB800', 'title_tpl': 'Deal "{name}" moved to {stage}'},
    'deal_won':         {'module': 'deals', 'icon': 'fa-trophy', 'color': '#00D9A6', 'title_tpl': 'Deal "{name}" won'},
    'deal_lost':        {'module': 'deals', 'icon': 'fa-times-circle', 'color': '#FF6B6B', 'title_tpl': 'Deal "{name}" lost'},
    'deal_updated':     {'module': 'deals', 'icon': 'fa-edit', 'color': '#00B4D8', 'title_tpl': 'Deal "{name}" updated'},
    'deal_deleted':     {'module': 'deals', 'icon': 'fa-trash', 'color': '#FF6B6B', 'title_tpl': 'Deal "{name}" deleted'},
    # Tasks
    'task_created':     {'module': 'tasks', 'icon': 'fa-plus-circle', 'color': '#3699FF', 'title_tpl': 'Task "{name}" created'},
    'task_completed':   {'module': 'tasks', 'icon': 'fa-check-circle', 'color': '#00D9A6', 'title_tpl': 'Task "{name}" completed'},
    'task_updated':     {'module': 'tasks', 'icon': 'fa-edit', 'color': '#00B4D8', 'title_tpl': 'Task "{name}" updated'},
    'task_deleted':     {'module': 'tasks', 'icon': 'fa-trash', 'color': '#FF6B6B', 'title_tpl': 'Task "{name}" deleted'},
    # Campaigns
    'campaign_created': {'module': 'campaigns', 'icon': 'fa-bullhorn', 'color': '#00D9A6', 'title_tpl': 'Campaign "{name}" created'},
    'campaign_updated': {'module': 'campaigns', 'icon': 'fa-bullhorn', 'color': '#00B4D8', 'title_tpl': 'Campaign "{name}" updated'},
    'campaign_deleted': {'module': 'campaigns', 'icon': 'fa-trash', 'color': '#FF6B6B', 'title_tpl': 'Campaign "{name}" deleted'},
    # Emails
    'email_sent':       {'module': 'emails', 'icon': 'fa-paper-plane', 'color': '#8B85FF', 'title_tpl': 'Email sent: "{name}"'},
    'email_scheduled':  {'module': 'emails', 'icon': 'fa-clock', 'color': '#FFB800', 'title_tpl': 'Email scheduled: "{name}"'},
    'email_draft':      {'module': 'emails', 'icon': 'fa-pencil-alt', 'color': '#3699FF', 'title_tpl': 'Email draft saved: "{name}"'},
    # Calendar
    'meeting_created':  {'module': 'calendar', 'icon': 'fa-calendar-plus', 'color': '#00B4D8', 'title_tpl': 'Meeting "{name}" scheduled'},
    'meeting_updated':  {'module': 'calendar', 'icon': 'fa-calendar-check', 'color': '#00B4D8', 'title_tpl': 'Meeting "{name}" updated'},
    'meeting_completed': {'module': 'calendar', 'icon': 'fa-calendar-check', 'color': '#00D9A6', 'title_tpl': 'Meeting "{name}" completed'},
    'meeting_deleted':  {'module': 'calendar', 'icon': 'fa-calendar-minus', 'color': '#FF6B6B', 'title_tpl': 'Meeting "{name}" deleted'},
    # Workflows
    'workflow_executed': {'module': 'workflows', 'icon': 'fa-cogs', 'color': '#3699FF', 'title_tpl': 'Workflow "{name}" executed'},
    # AI
    'ai_created_contact': {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI created contact "{name}"'},
    'ai_created_task':    {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI created task "{name}"'},
    'ai_created_deal':    {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI created deal "{name}"'},
    'ai_created_company': {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI created company "{name}"'},
    'ai_created_lead':    {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI created lead "{name}"'},
    'ai_sent_email':      {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI sent email "{name}"'},
    'ai_created_campaign': {'module': 'ai', 'icon': 'fa-robot', 'color': '#8B85FF', 'title_tpl': 'AI created campaign "{name}"'},
    # System
    'user_login':       {'module': 'system', 'icon': 'fa-sign-in-alt', 'color': '#3699FF', 'title_tpl': 'User logged in'},
}


def log_activity(user, activity_type=None, title=None, description='',
                 module=None, icon=None, color=None,
                 object_id=None, object_repr='', detail_url='',
                 **kwargs):
    """Create an ActivityLog entry.

    If *activity_type* is one of the predefined types in ACTIVITY_TYPES,
    module/icon/color are filled in automatically.  Override any of them
    explicitly to customize.

    This function never raises — DB errors are logged and swallowed.
    """
    from activities.models import ActivityLog

    config = ACTIVITY_TYPES.get(activity_type, {}) if activity_type else {}

    # Resolve name from kwargs if title template uses {name}
    name = kwargs.pop('name', '')
    if not title and config.get('title_tpl'):
        title = config['title_tpl'].format(name=name, **kwargs)

    entry = ActivityLog(
        user=user,
        activity_type=activity_type or 'unknown',
        title=title or 'Activity recorded',
        description=description or '',
        module=module or config.get('module', 'system'),
        icon=icon or config.get('icon', 'fa-info-circle'),
        color=color or config.get('color', '#6C63FF'),
        object_id=object_id,
        object_repr=object_repr or str(name),
        detail_url=detail_url or '',
    )

    try:
        entry.save()
    except Exception:
        logger.exception('Failed to save ActivityLog for user=%s type=%s', user, activity_type)
