from django.core.management.base import BaseCommand

from emails.service import retry_pending_emails


class Command(BaseCommand):
    help = 'Повторная отправка email-писем со статусом retry'

    def handle(self, *args, **options):
        sent, failed = retry_pending_emails()
        if sent or failed:
            self.stdout.write(f'Retry emails: {sent} sent, {failed} failed')
        else:
            self.stdout.write('No pending emails to retry')
