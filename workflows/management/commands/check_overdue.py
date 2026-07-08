"""Management command to check for overdue tasks and fire task_overdue triggers."""

import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from workflows.services.engine import fire_trigger_for_user

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Find overdue tasks and fire workflow triggers.'

    def handle(self, *args, **options):
        self.stdout.write('Checking for overdue tasks...')
        today = date.today()

        try:
            from tasks.models import Task
            overdue_tasks = Task.objects.filter(
                due_date__lt=today, status__in=['pending', 'in_progress'],
            ).select_related('owner')

            count = 0
            for task in overdue_tasks:
                if task.owner:
                    fire_trigger_for_user('task_overdue', task, task.owner)
                    count += 1

            self.stdout.write(self.style.SUCCESS(f'Fired overdue trigger for {count} tasks.'))
        except ImportError:
            self.stdout.write('Tasks app not available, skipping overdue check.')
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Overdue check failed: {e}'))
            logger.exception('Overdue check command failed')
