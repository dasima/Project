from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import ApplicationCase, BookingAttempt, Channel, CrawlRun, SlotObservation
from apps.crawler.types import ObservationResult, Slot, SubmissionResult
from apps.automation import services


@override_settings(DEMO_PROVIDER_TOKEN='demo-test-token', CRAWLER_ALLOWED_HOSTS=('127.0.0.1',))
class AutomationTests(TestCase):
    def setUp(self):
        self.starts_at = timezone.now() + timedelta(days=5)
        self.channel = Channel.objects.create(name='Demo', code='demo', country='FR',
            visa_category='student', center='demo', adapter='demo_http',
            base_url='http://127.0.0.1:8010/demo-provider', enabled=True, auto_book=True)
        day = timezone.localtime(self.starts_at).date()
        self.case = ApplicationCase.objects.create(reference='TEST-1', display_name='Test',
            channel=self.channel, earliest_date=day, latest_date=day,
            authorization_expires_at=timezone.now() + timedelta(days=1), auto_submit=True)
        self.adapter_patch = patch('apps.automation.services.HttpDemoAdapter')
        self.adapter = self.adapter_patch.start().return_value
        self.addCleanup(self.adapter_patch.stop)
        self.adapter.observe.return_value = ObservationResult('available', (Slot('slot-1', self.starts_at),))
        self.adapter.submit.return_value = SubmissionResult('confirmed', 'DEMO-123')
        self.adapter.reconcile.return_value = SubmissionResult('confirmed', 'DEMO-123')

    def due(self):
        Channel.objects.filter(pk=self.channel.pk).update(next_poll_at=None)

    def prepare(self):
        services.poll_channel(self.channel.pk)
        return BookingAttempt.objects.get(case=self.case)

    def test_default_poll_persists_intent_without_sending(self):
        run = services.poll_channel(self.channel.pk)
        self.assertEqual(run.status, 'available')
        self.assertEqual(run.slot_count, 1)
        self.assertEqual(BookingAttempt.objects.get().status, 'PREPARED')
        self.adapter.submit.assert_not_called()

    def test_repeated_opportunity_and_confirmed_case_do_not_resubmit(self):
        services.poll_channel(self.channel.pk, execute=True)
        self.due()
        services.poll_channel(self.channel.pk, execute=True)
        self.assertEqual(BookingAttempt.objects.count(), 1)
        self.assertEqual(BookingAttempt.objects.get().status, 'CONFIRMED')
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, 'BOOKED')
        self.assertEqual(self.adapter.submit.call_count, 1)

    def test_expired_authorization_or_date_mismatch_does_not_prepare(self):
        for changes in ({'authorization_expires_at': timezone.now()-timedelta(seconds=1)},
                        {'earliest_date': self.case.latest_date+timedelta(days=1),
                         'latest_date': self.case.latest_date+timedelta(days=2)}):
            with self.subTest(changes=changes):
                ApplicationCase.objects.filter(pk=self.case.pk).update(**changes)
                self.due()
                services.poll_channel(self.channel.pk, execute=True)
                self.assertEqual(BookingAttempt.objects.count(), 0)
        self.adapter.submit.assert_not_called()

    def test_flags_and_authorization_are_rechecked_at_submission(self):
        attempt = self.prepare()
        ApplicationCase.objects.filter(pk=self.case.pk).update(auto_submit=False)
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'REJECTED')
        self.adapter.submit.assert_not_called()

    def test_no_longer_available_slot_is_not_submitted(self):
        attempt = self.prepare()
        self.due()
        self.adapter.observe.return_value = ObservationResult('no_slots')
        services.poll_channel(self.channel.pk)
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'REJECTED')
        self.adapter.submit.assert_not_called()

    def test_unknown_result_is_reconciled_without_resubmission(self):
        self.adapter.submit.return_value = SubmissionResult('unknown', detail='Timed out')
        attempt = self.prepare()
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'RECONCILING')
        result = services.reconcile_attempt(attempt.pk)
        self.assertEqual(result.status, 'CONFIRMED')
        services.execute_attempt(attempt.pk)
        self.assertEqual(self.adapter.submit.call_count, 1)

    def test_intent_claim_is_committed_before_submit_and_only_sent_once(self):
        attempt = self.prepare()
        def submit(request):
            stored = BookingAttempt.objects.get(pk=attempt.pk)
            self.assertEqual(stored.status, 'SUBMITTING')
            self.assertIsNotNone(stored.submitted_at)
            self.assertEqual(str(stored.operation_id), request.operation_id)
            services.execute_attempt(stored.pk)
            return SubmissionResult('confirmed', 'DEMO-123')
        self.adapter.submit.side_effect = submit
        services.execute_attempt(attempt.pk)
        self.assertEqual(self.adapter.submit.call_count, 1)

    def test_fresh_submitting_is_not_reconciled_but_abandoned_attempt_is(self):
        attempt = self.prepare()
        BookingAttempt.objects.filter(pk=attempt.pk).update(status='SUBMITTING', submitted_at=timezone.now())
        services.execute_attempt(attempt.pk)
        services.reconcile_attempt(attempt.pk)
        self.adapter.reconcile.assert_not_called()
        BookingAttempt.objects.filter(pk=attempt.pk).update(submitted_at=timezone.now()-timedelta(minutes=5))
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'CONFIRMED')
        self.adapter.submit.assert_not_called()
        self.assertEqual(self.adapter.reconcile.call_count, 1)

    def test_disabled_and_manual_channels_never_access_network(self):
        for changes in ({'enabled': False}, {'enabled': True, 'adapter': 'manual', 'auto_book': False}):
            Channel.objects.filter(pk=self.channel.pk).update(**changes)
            self.assertIsNone(services.poll_channel(self.channel.pk, execute=True))
        self.adapter.observe.assert_not_called()

    def test_disabled_channel_cannot_reconcile_or_submit_existing_intent(self):
        attempt = self.prepare()
        BookingAttempt.objects.filter(pk=attempt.pk).update(status='RECONCILING')
        Channel.objects.filter(pk=self.channel.pk).update(enabled=False)
        services.reconcile_attempt(attempt.pk)
        self.adapter.reconcile.assert_not_called()

    def test_no_slots_and_exceptions_persist_crawl_runs(self):
        self.adapter.observe.return_value = ObservationResult('no_slots')
        self.assertEqual(services.poll_channel(self.channel.pk).status, 'no_slots')
        self.due()
        self.adapter.observe.side_effect = RuntimeError('secret response')
        run = services.poll_channel(self.channel.pk)
        self.assertEqual(run.status, 'transient_error')
        self.assertNotIn('secret', run.detail)
        self.assertEqual(CrawlRun.objects.count(), 2)

    def test_active_poll_lease_and_schedule_prevent_overlapping_fetches(self):
        Channel.objects.filter(pk=self.channel.pk).update(lease_token='other',
            lease_expires_at=timezone.now()+timedelta(seconds=60))
        self.assertIsNone(services.poll_channel(self.channel.pk))
        Channel.objects.filter(pk=self.channel.pk).update(lease_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertIsNotNone(services.poll_channel(self.channel.pk))
        self.assertIsNone(services.poll_channel(self.channel.pk))
        self.assertEqual(self.adapter.observe.call_count, 1)

    def test_poll_result_cannot_overwrite_new_lease_owner(self):
        def observe():
            Channel.objects.filter(pk=self.channel.pk).update(lease_token='new-owner',
                lease_expires_at=timezone.now()+timedelta(seconds=60))
            return ObservationResult('available', (Slot('slot-1', self.starts_at),))
        self.adapter.observe.side_effect = observe
        run = services.poll_channel(self.channel.pk)
        self.assertEqual(run.status, 'superseded')
        self.assertEqual(SlotObservation.objects.count(), 0)
        self.assertEqual(BookingAttempt.objects.count(), 0)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.lease_token, 'new-owner')

    def test_worker_monitor_and_booking_roles(self):
        call_command('runworker', role='monitor', once=True, verbosity=0)
        self.assertEqual(BookingAttempt.objects.get().status, 'PREPARED')
        self.adapter.submit.assert_not_called()
        call_command('runworker', role='booking', once=True, verbosity=0)
        self.assertEqual(BookingAttempt.objects.get().status, 'CONFIRMED')

    def test_reconcile_command_uses_only_query(self):
        attempt = self.prepare()
        BookingAttempt.objects.filter(pk=attempt.pk).update(status='RECONCILING',
            updated_at=timezone.now()-timedelta(seconds=10))
        call_command('reconcile_bookings', once=True, verbosity=0)
        self.assertEqual(BookingAttempt.objects.get().status, 'CONFIRMED')
        self.adapter.submit.assert_not_called()

    def test_confirmed_without_reference_remains_uncertain(self):
        self.adapter.submit.return_value = SubmissionResult('confirmed', '')
        attempt = self.prepare()
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'RECONCILING')
        self.case.refresh_from_db()
        self.assertNotEqual(self.case.status, 'BOOKED')

    def test_human_required_blocks_new_intents(self):
        self.adapter.submit.return_value = SubmissionResult('human_required')
        services.poll_channel(self.channel.pk, execute=True)
        self.due()
        services.poll_channel(self.channel.pk, execute=True)
        self.assertEqual(BookingAttempt.objects.count(), 1)
        self.assertEqual(BookingAttempt.objects.get().status, 'HUMAN_REQUIRED')
        self.assertEqual(self.adapter.submit.call_count, 1)

    def test_submit_exception_retains_operation_for_reconciliation(self):
        self.adapter.submit.side_effect = RuntimeError('secret token')
        attempt = self.prepare()
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'RECONCILING')
        self.assertNotIn('secret', result.detail)
        result = services.reconcile_attempt(attempt.pk)
        self.assertEqual(result.status, 'CONFIRMED')
        self.assertEqual(self.adapter.submit.call_count, 1)

    def test_disabled_channel_rejects_prepared_attempt_without_post(self):
        attempt = self.prepare()
        Channel.objects.filter(pk=self.channel.pk).update(enabled=False)
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'REJECTED')
        self.adapter.submit.assert_not_called()

    def another_case(self, reference='TEST-2'):
        return ApplicationCase.objects.create(reference=reference, display_name='Another test',
            channel=self.channel, earliest_date=self.case.earliest_date, latest_date=self.case.latest_date,
            authorization_expires_at=timezone.now()+timedelta(days=1), auto_submit=True)

    def test_unknown_capacity_slot_is_reserved_for_only_one_unresolved_customer(self):
        other = self.another_case()
        services.poll_channel(self.channel.pk)
        self.assertEqual(BookingAttempt.objects.count(), 1)
        self.due()
        services.poll_channel(self.channel.pk)
        self.assertEqual(BookingAttempt.objects.count(), 1)
        attempt = BookingAttempt.objects.get()
        services.execute_attempt(attempt.pk)
        self.due()
        services.poll_channel(self.channel.pk)
        self.assertEqual(BookingAttempt.objects.count(), 2)
        self.assertEqual(BookingAttempt.objects.get(case=other).status, 'PREPARED')

    def test_distinct_slots_can_prepare_distinct_customers(self):
        self.another_case()
        self.adapter.observe.return_value = ObservationResult('available', (
            Slot('slot-1', self.starts_at), Slot('slot-2', self.starts_at)))
        services.poll_channel(self.channel.pk)
        self.assertEqual(BookingAttempt.objects.count(), 2)
        self.assertEqual(BookingAttempt.objects.values('observation').distinct().count(), 2)

    def test_stale_availability_snapshot_cannot_authorize_submission(self):
        attempt = self.prepare()
        SlotObservation.objects.filter(pk=attempt.observation_id).update(
            observed_at=timezone.now()-timedelta(hours=1))
        Channel.objects.filter(pk=self.channel.pk).update(next_poll_at=None)
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'REJECTED')
        self.adapter.submit.assert_not_called()

    def unresolved_backlog(self, *, status='RECONCILING', disabled=False, count=100):
        channel = self.channel
        if disabled:
            channel = Channel.objects.create(name='Disabled', code='disabled', country='FR',
                visa_category='student', center='demo', adapter='demo_http',
                base_url=self.channel.base_url, enabled=False)
        cases = ApplicationCase.objects.bulk_create([
            ApplicationCase(reference=f'BACKLOG-{index}', display_name='Backlog', channel=channel,
                earliest_date=self.case.earliest_date, latest_date=self.case.latest_date,
                authorization_expires_at=timezone.now()+timedelta(days=1), auto_submit=False)
            for index in range(count)
        ])
        attempts = BookingAttempt.objects.bulk_create([
            BookingAttempt(case=case, status=status,
                submitted_at=timezone.now() if status == 'SUBMITTING' else None)
            for case in cases
        ])
        if status == 'RECONCILING':
            BookingAttempt.objects.filter(pk__in=[item.pk for item in attempts]).update(
                updated_at=timezone.now()-timedelta(seconds=10))
        return attempts

    def test_booking_queue_ignores_disabled_backlog(self):
        self.unresolved_backlog(disabled=True)
        attempt = self.prepare()
        call_command('runworker', role='booking', once=True, verbosity=0)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'CONFIRMED')
        self.adapter.reconcile.assert_not_called()

    def test_booking_queue_prioritizes_prepared_over_fresh_submitting_backlog(self):
        self.unresolved_backlog(status='SUBMITTING')
        attempt = self.prepare()
        call_command('runworker', role='booking', once=True, verbosity=0)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'CONFIRMED')
        self.adapter.reconcile.assert_not_called()

    def test_reconciliation_queue_ignores_disabled_backlog(self):
        self.unresolved_backlog(disabled=True)
        attempt = self.prepare()
        BookingAttempt.objects.filter(pk=attempt.pk).update(status='RECONCILING',
            updated_at=timezone.now()-timedelta(seconds=10))
        call_command('reconcile_bookings', once=True, verbosity=0)
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'CONFIRMED')
        self.assertEqual(self.adapter.reconcile.call_count, 1)

    def test_booking_reconciliation_rotates_backlog_and_applies_cooldown(self):
        self.unresolved_backlog(count=101)
        self.adapter.reconcile.return_value = SubmissionResult('unknown')
        call_command('runworker', role='booking', once=True, verbosity=0)
        self.assertEqual(self.adapter.reconcile.call_count, 100)
        call_command('runworker', role='booking', once=True, verbosity=0)
        self.assertEqual(self.adapter.reconcile.call_count, 101)
        call_command('runworker', role='booking', once=True, verbosity=0)
        self.assertEqual(self.adapter.reconcile.call_count, 101)

    def test_route_change_during_observation_discards_snapshot_and_old_availability(self):
        attempt = self.prepare()
        self.due()
        def observe():
            Channel.objects.filter(pk=self.channel.pk).update(base_url='http://127.0.0.1:8011/other')
            return ObservationResult('available', (Slot('new-slot', self.starts_at),))
        self.adapter.observe.side_effect = observe
        run = services.poll_channel(self.channel.pk, execute=True)
        self.assertEqual(run.status, 'superseded')
        self.assertFalse(SlotObservation.objects.filter(available=True).exists())
        self.assertFalse(SlotObservation.objects.filter(slot_id='new-slot').exists())
        self.assertEqual(BookingAttempt.objects.count(), 1)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.lease_token, '')
        self.assertEqual(services.execute_attempt(attempt.pk).status, 'REJECTED')
        self.adapter.submit.assert_not_called()

    def test_scheduled_reconciliation_checks_cooldown_under_lock(self):
        attempt = self.prepare()
        BookingAttempt.objects.filter(pk=attempt.pk).update(status='RECONCILING',
            updated_at=timezone.now()-timedelta(seconds=10))
        self.adapter.reconcile.return_value = SubmissionResult('unknown')
        services.reconcile_attempt(attempt.pk, respect_cooldown=True)
        services.reconcile_attempt(attempt.pk, respect_cooldown=True)
        self.assertEqual(self.adapter.reconcile.call_count, 1)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection, connections, transaction
from django.test import TransactionTestCase


@override_settings(DEMO_PROVIDER_TOKEN='demo-test-token', CRAWLER_ALLOWED_HOSTS=('127.0.0.1',))
class DurableClaimTests(TransactionTestCase):
    setUp = AutomationTests.setUp
    prepare = AutomationTests.prepare

    def test_cannot_send_from_inside_an_uncommitted_outer_transaction(self):
        attempt = self.prepare()
        with transaction.atomic():
            with self.assertRaises(RuntimeError):
                services.execute_attempt(attempt.pk)
        self.adapter.submit.assert_not_called()
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'PREPARED')

    def test_submit_sees_committed_claim_outside_transaction(self):
        attempt = self.prepare()
        def submit(request):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(BookingAttempt.objects.get(pk=attempt.pk).status, 'SUBMITTING')
            return SubmissionResult('confirmed', 'DEMO-123')
        self.adapter.submit.side_effect = submit
        result = services.execute_attempt(attempt.pk)
        self.assertEqual(result.status, 'CONFIRMED')


@skipUnless(connection.vendor == 'postgresql', 'Concurrent workers require PostgreSQL.')
@override_settings(DEMO_PROVIDER_TOKEN='demo-test-token', CRAWLER_ALLOWED_HOSTS=('127.0.0.1',))
class PostgreSQLWorkerTests(TransactionTestCase):
    setUp = AutomationTests.setUp
    prepare = AutomationTests.prepare

    def concurrently(self, operation):
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(run) for _ in range(2)]
            return [future.result(timeout=15) for future in futures]

    def test_two_monitors_claim_only_one_fetch(self):
        channel_id = self.channel.pk
        results = self.concurrently(lambda: services.poll_channel(channel_id))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(CrawlRun.objects.count(), 1)
        self.assertEqual(BookingAttempt.objects.count(), 1)
        self.assertEqual(self.adapter.observe.call_count, 1)

    def test_two_booking_workers_send_only_one_post(self):
        attempt_id = self.prepare().pk
        self.concurrently(lambda: services.execute_attempt(attempt_id))
        self.assertEqual(self.adapter.submit.call_count, 1)
        self.assertEqual(BookingAttempt.objects.get(pk=attempt_id).status, 'CONFIRMED')

    def test_two_reconcilers_preserve_one_terminal_result(self):
        attempt_id = self.prepare().pk
        BookingAttempt.objects.filter(pk=attempt_id).update(status='RECONCILING')
        self.concurrently(lambda: services.reconcile_attempt(attempt_id))
        self.assertEqual(self.adapter.reconcile.call_count, 1)
        self.assertEqual(BookingAttempt.objects.get(pk=attempt_id).status, 'CONFIRMED')
