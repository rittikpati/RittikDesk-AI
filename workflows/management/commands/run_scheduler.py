"""Management command to run the workflow scheduler periodically.

Intended to be called every minute via cron / Task Scheduler:
    python manage.py run_scheduler
"""

import logging

from django.core.management.base import BaseCommand

from workflows.services.scheduler import run_scheduler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check and execute due scheduled workflows.'

    def handle(self, *args, **options):
        self.stdout.write('Running workflow scheduler...')
        try:
            run_scheduler()
            self.stdout.write(self.style.SUCCESS('Scheduler completed.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Scheduler failed: {e}'))
            logger.exception('Scheduler command failed')
