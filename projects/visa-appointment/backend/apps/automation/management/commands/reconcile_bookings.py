import time

from django.core.management.base import BaseCommand, CommandError

from apps.automation.services import due_reconciliation_attempt_ids, reconcile_attempt


class Command(BaseCommand):
    help = 'Query uncertain bookings by operation ID; never create or resubmit an operation.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--interval', type=float, default=5.0)

    def handle(self, *args, **options):
        interval = options['interval']
        if not 0.1 <= interval <= 60:
            raise CommandError('--interval must be between 0.1 and 60 seconds.')
        try:
            while True:
                for attempt_id in due_reconciliation_attempt_ids():
                    reconcile_attempt(attempt_id, respect_cooldown=True)
                if options['once']:
                    return
                time.sleep(interval)
        except KeyboardInterrupt:
            return
