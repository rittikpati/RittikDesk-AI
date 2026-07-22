from django.core.management.base import BaseCommand
from emails.services import send_queued_emails


class Command(BaseCommand):
    help = 'Send all queued emails that are due.'

    def handle(self, *args, **options):
        sent, failed = send_queued_emails()
        self.stdout.write(f'Sent: {sent}, Failed: {failed}')
