"""Checks for due scheduled workflows and fires them."""

import logging

from django.utils import timezone

from workflows.models import WorkflowSchedule
from workflows.services.engine import fire_trigger_for_user, _build_context

logger = logging.getLogger(__name__)

SCHEDULE_MAP = {
    'daily': 'scheduled_daily',
    'weekly': 'scheduled_weekly',
    'monthly': 'scheduled_monthly',
}


def run_scheduler():
    """Find all active schedules that are due and fire their workflows."""
    now = timezone.localtime()
    current_time = now.time()
    today = now.date()
    current_weekday = now.weekday()
    current_day = now.day

    due_schedules = WorkflowSchedule.objects.select_related(
        'workflow', 'workflow__owner',
    ).filter(is_active=True, workflow__is_active=True)

    for schedule in due_schedules:
        matched = False

        if schedule.schedule_type == 'daily':
            matched = True
        elif schedule.schedule_type == 'weekly':
            if schedule.day_of_week is not None and schedule.day_of_week == current_weekday:
                matched = True
        elif schedule.schedule_type == 'monthly':
            if schedule.day_of_month is not None and schedule.day_of_month == current_day:
                matched = True

        if not matched:
            continue

        schedule_time = schedule.time

        if current_time.hour == schedule_time.hour and current_time.minute == schedule_time.minute:
            trigger_type = SCHEDULE_MAP.get(schedule.schedule_type)
            if not trigger_type:
                continue
            try:
                context = _build_context(trigger_type, schedule.workflow)
                fire_trigger_for_user(trigger_type, schedule.workflow, schedule.workflow.owner)
                schedule.last_run = timezone.now()
                schedule.save(update_fields=['last_run'])
                logger.info(
                    'Scheduler fired workflow=%s type=%s',
                    schedule.workflow_id, trigger_type,
                )
            except Exception:
                logger.exception(
                    'Scheduler failed workflow=%s', schedule.workflow_id,
                )
