"""Independent polling and booking processes backed by persisted due state."""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from apps.automation.services import (
    due_reconciliation_attempt_ids, execute_attempt, pending_prepared_attempt_ids,
    poll_channel, reconcile_attempt,
)
from apps.core.models import Channel


class Command(BaseCommand):
    help = 'Run persisted monitor/booking workers. SQLite supports one local worker only.'

    def add_arguments(self, parser):
        parser.add_argument('--role', choices=('monitor', 'booking', 'all'), default='all')
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--interval', type=float, default=1.0)

    def handle(self, *args, **options):
        interval = options['interval']
        if not 0.1 <= interval <= 60:
            raise CommandError('--interval must be between 0.1 and 60 seconds.')
        if connection.vendor == 'sqlite' and options['verbosity']:
            self.stderr.write('SQLite local mode: run one worker with --role all; use PostgreSQL for multiple workers.')
        try:
            while True:
                if options['role'] in ('monitor', 'all'):
                    ids = list(Channel.objects.filter(enabled=True, adapter='demo_http').filter(
                        Q(next_poll_at__isnull=True) | Q(next_poll_at__lte=timezone.now())
                    ).order_by('next_poll_at', 'pk').values_list('pk', flat=True)[:100])
                    for channel_id in ids:
                        poll_channel(channel_id)
                if options['role'] in ('booking', 'all'):
                    for attempt_id in pending_prepared_attempt_ids():
                        execute_attempt(attempt_id)
                    for attempt_id in due_reconciliation_attempt_ids():
                        reconcile_attempt(attempt_id, respect_cooldown=True)
                if options['once']:
                    return
                time.sleep(interval)
        except KeyboardInterrupt:
            return
