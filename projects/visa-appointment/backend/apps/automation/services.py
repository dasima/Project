"""Persisted polling and booking state machines.

HTTP submission happens only after the SUBMITTING claim commits. A crashed or
uncertain submission is queried by its operation ID and is never sent again.
PostgreSQL supports multiple workers; SQLite is for one local worker only.
"""

import time
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import (
    ApplicationCase, AuditEvent, BookingAttempt, Channel, CrawlRun, SlotObservation,
)
from apps.crawler.http import HttpDemoAdapter
from apps.crawler.types import BookingRequest, ObservationResult, SubmissionResult

UNRESOLVED_STATUSES = ('PREPARED', 'SUBMITTING', 'RECONCILING', 'HUMAN_REQUIRED')
ACTIVE_STATUSES = (*UNRESOLVED_STATUSES, 'CONFIRMED')
POLL_LEASE_SECONDS = 60
# Must exceed the bounded HTTP submit timeout. Fresh submissions are never queried.
SUBMISSION_GRACE_SECONDS = 60
RECONCILIATION_COOLDOWN_SECONDS = 5
WORKER_BATCH_SIZE = 100
OBSERVATION_STATUSES = {
    'available', 'no_slots', 'auth_required', 'challenge', 'rate_limited',
    'parser_changed', 'transient_error', 'manual_required',
}


def _network_enabled(channel):
    return channel.enabled and channel.adapter == 'demo_http'


def _adapter(channel):
    return HttpDemoAdapter(base_url=channel.base_url, token=settings.DEMO_PROVIDER_TOKEN,
                           allowed_hosts=settings.CRAWLER_ALLOWED_HOSTS, timeout=5.0)


def _audit(event_type, *, case=None, attempt=None, detail=''):
    AuditEvent.objects.create(event_type=event_type, case=case, attempt=attempt, detail=detail[:1000])


def _eligible(case, channel, observation, now):
    if not (_network_enabled(channel) and channel.auto_book and case.auto_submit):
        return False
    if case.status not in ('READY', 'WAITING'):
        return False
    if not case.authorization_expires_at or case.authorization_expires_at <= now:
        return False
    if not observation or not observation.available or observation.channel_id != channel.pk:
        return False
    if channel.last_status != 'available' or observation.starts_at <= now:
        return False
    freshness_seconds = max(30, min(channel.poll_interval_seconds, 3600) * 2)
    if observation.observed_at < now - timedelta(seconds=freshness_seconds):
        return False
    day = timezone.localtime(observation.starts_at).date()
    return case.earliest_date <= day <= case.latest_date


def _prepare_matches(channel, observations):
    attempt_ids = []
    # Slot capacity is unspecified: reserve one unresolved customer per observed slot.
    reserved = set(BookingAttempt.objects.filter(
        observation__channel=channel, status__in=UNRESOLVED_STATUSES,
    ).values_list('observation_id', flat=True))
    cases = ApplicationCase.objects.select_for_update().filter(
        channel=channel, status__in=('READY', 'WAITING'), auto_submit=True,
        authorization_expires_at__gt=timezone.now(),
    ).order_by('priority', 'pk')
    for case in cases:
        if BookingAttempt.objects.filter(case=case, status__in=ACTIVE_STATUSES).exists():
            continue
        observation = next((item for item in observations
                            if item.pk not in reserved and _eligible(case, channel, item, timezone.now())), None)
        if observation is None:
            continue
        attempt = BookingAttempt.objects.create(case=case, observation=observation, status='PREPARED')
        _audit('booking_prepared', case=case, attempt=attempt, detail='Persisted booking intent before submission.')
        attempt_ids.append(attempt.pk)
        reserved.add(observation.pk)
    return attempt_ids


def poll_channel(channel_id: int, *, execute: bool = False):
    """Claim one due channel, persist its observation, and optionally execute intents."""
    now = timezone.now()
    token = str(uuid4())
    claimed = Channel.objects.filter(pk=channel_id, enabled=True, adapter='demo_http').filter(
        Q(next_poll_at__isnull=True) | Q(next_poll_at__lte=now),
    ).filter(Q(lease_expires_at__isnull=True) | Q(lease_expires_at__lte=now)).update(
        lease_token=token, lease_expires_at=now + timedelta(seconds=POLL_LEASE_SECONDS), updated_at=now,
    )
    if not claimed:
        return None
    channel = Channel.objects.get(pk=channel_id)
    run = CrawlRun.objects.create(channel=channel, status='running', started_at=now)
    started = time.monotonic()
    try:
        if not _network_enabled(channel):
            result = ObservationResult('manual_required', detail='Channel is disabled or requires manual handling.')
        else:
            result = _adapter(channel).observe()
        if result.status not in OBSERVATION_STATUSES:
            result = ObservationResult('parser_changed', detail='Unrecognized observation status.')
    except Exception:
        # Never persist raw exception strings, HTML, headers, or credentials.
        result = ObservationResult('transient_error', detail='Observation failed; inspect worker diagnostics.')
    finished = timezone.now()
    attempt_ids = []
    with transaction.atomic():
        current = Channel.objects.select_for_update().get(pk=channel_id)
        owns_lease = (current.lease_token == token and current.lease_expires_at and
                      current.lease_expires_at > finished)
        route_changed = (current.base_url, current.adapter) != (channel.base_url, channel.adapter)
        if not owns_lease or not _network_enabled(current) or route_changed:
            run.status = 'superseded'
            run.detail = 'Lease lost, channel disabled, or route changed; discarded observation.'
            if current.lease_token == token and route_changed:
                # Existing intents must not carry availability from the old route.
                SlotObservation.objects.filter(channel=current).update(available=False)
                Channel.objects.filter(pk=channel_id).update(last_status='route_changed', updated_at=finished)
            if current.lease_token == token:
                Channel.objects.filter(pk=channel_id, lease_token=token).update(
                    lease_token='', lease_expires_at=None, updated_at=finished)
        else:
            run.status = result.status
            run.detail = result.detail[:1000]
            observations = []
            # A previous snapshot cannot authorize a later send after a failed/empty fetch.
            SlotObservation.objects.filter(channel=current).update(available=False)
            if result.status == 'available':
                for slot in result.slots:
                    observation, _ = SlotObservation.objects.update_or_create(
                        channel=current, slot_id=slot.slot_id,
                        defaults={'starts_at': slot.starts_at, 'observed_at': finished, 'available': True},
                    )
                    observations.append(observation)
            run.slot_count = len(observations)
            interval = max(1, min(int(current.poll_interval_seconds), 3600))
            if result.retry_after is not None:
                interval = max(interval, min(max(1, result.retry_after), 86400))
            current.last_status = result.status
            current.last_error = '' if result.status in ('available', 'no_slots') else run.detail
            current.last_polled_at = finished
            current.next_poll_at = finished + timedelta(seconds=interval)
            current.lease_token = ''
            current.lease_expires_at = None
            current.save(update_fields=('last_status', 'last_error', 'last_polled_at',
                'next_poll_at', 'lease_token', 'lease_expires_at', 'updated_at'))
            if current.auto_book:
                attempt_ids = _prepare_matches(current, observations)
        run.finished_at = finished
        run.duration_ms = max(0, round((time.monotonic() - started) * 1000))
        run.save(update_fields=('status', 'detail', 'slot_count', 'finished_at', 'duration_ms'))
    if execute:
        for attempt_id in attempt_ids:
            execute_attempt(attempt_id)
    return run


def _locked_context(attempt_id):
    # Every state-changing transaction locks in this same order: channel, case, attempt.
    identity = BookingAttempt.objects.values('case_id', 'case__channel_id').get(pk=attempt_id)
    channel = Channel.objects.select_for_update().get(pk=identity['case__channel_id'])
    case = ApplicationCase.objects.select_for_update().get(pk=identity['case_id'])
    attempt = BookingAttempt.objects.select_for_update().get(pk=attempt_id)
    return channel, case, attempt


def _normalized_result(result):
    if result.status not in ('confirmed', 'rejected', 'unknown', 'human_required'):
        return SubmissionResult('unknown', detail='Unrecognized booking result; reconcile before continuing.')
    if result.status == 'confirmed' and not result.confirmation_reference.strip():
        return SubmissionResult('unknown', detail='Confirmation reference missing; reconcile before continuing.')
    return result


def _apply_result(case, attempt, result):
    result = _normalized_result(result)
    attempt.status = {'confirmed': 'CONFIRMED', 'rejected': 'REJECTED',
                      'unknown': 'RECONCILING', 'human_required': 'HUMAN_REQUIRED'}[result.status]
    attempt.detail = result.detail[:1000]
    attempt.confirmation_reference = result.confirmation_reference[:200] if result.status == 'confirmed' else ''
    if result.status == 'confirmed':
        attempt.confirmed_at = timezone.now()
        case.status = 'BOOKED'
    elif result.status == 'human_required':
        case.status = 'NEEDS_REVIEW'
    elif result.status == 'rejected' and case.status in ('READY', 'WAITING'):
        case.status = 'WAITING'
    attempt.save(update_fields=('status', 'detail', 'confirmation_reference', 'confirmed_at', 'updated_at'))
    case.save(update_fields=('status', 'updated_at'))
    _audit('booking_' + result.status, case=case, attempt=attempt, detail=attempt.detail)
    return attempt


def _stale_submission(attempt):
    since = attempt.submitted_at or attempt.updated_at
    return since <= timezone.now() - timedelta(seconds=SUBMISSION_GRACE_SECONDS)


def execute_attempt(attempt_id: int):
    """Commit one PREPARED claim before issuing POST, and never POST it again."""
    needs_reconcile = False
    request = None
    with transaction.atomic(durable=True):
        channel, case, attempt = _locked_context(attempt_id)
        if attempt.status in ('RECONCILING', 'SUBMITTING'):
            needs_reconcile = attempt.status == 'RECONCILING' or _stale_submission(attempt)
        elif attempt.status != 'PREPARED':
            return attempt
        else:
            observation = (SlotObservation.objects.filter(pk=attempt.observation_id).first()
                           if attempt.observation_id else None)
            if not _eligible(case, channel, observation, timezone.now()):
                return _apply_result(case, attempt, SubmissionResult('rejected', detail='Eligibility changed before submission.'))
            attempt.status = 'SUBMITTING'
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=('status', 'submitted_at', 'updated_at'))
            _audit('booking_submitting', case=case, attempt=attempt, detail='Committed submission claim.')
            request = BookingRequest(operation_id=str(attempt.operation_id),
                                     case_reference=case.reference, slot_id=observation.slot_id)
    if needs_reconcile:
        return reconcile_attempt(attempt_id)
    if request is None:
        return attempt
    try:
        result = _adapter(channel).submit(request)
    except Exception:
        result = SubmissionResult('unknown', detail='Submission interrupted; operation must be reconciled.')
    with transaction.atomic():
        _, case, attempt = _locked_context(attempt_id)
        if attempt.status == 'SUBMITTING':
            return _apply_result(case, attempt, result)
        return attempt


def reconcile_attempt(attempt_id: int, *, respect_cooldown: bool = False):
    """Query uncertain operations only. This path can never send a booking POST."""
    with transaction.atomic():
        channel, case, attempt = _locked_context(attempt_id)
        if not _network_enabled(channel):
            return attempt
        if (respect_cooldown and attempt.status == 'RECONCILING' and
                attempt.updated_at > timezone.now()-timedelta(seconds=RECONCILIATION_COOLDOWN_SECONDS)):
            return attempt
        if attempt.status == 'SUBMITTING' and not _stale_submission(attempt):
            return attempt
        if attempt.status not in ('SUBMITTING', 'RECONCILING'):
            return attempt
        attempt.status = 'RECONCILING'
        attempt.save(update_fields=('status', 'updated_at'))
        # A bounded GET while holding the row lock prevents concurrent reconciliation
        # from racing a terminal result. POST never runs in this transaction.
        try:
            result = _adapter(channel).reconcile(str(attempt.operation_id))
        except Exception:
            result = SubmissionResult('unknown', detail='Reconciliation unavailable; retain operation for later query.')
        return _apply_result(case, attempt, result)



def pending_prepared_attempt_ids():
    """Bounded submission queue; recovery work cannot hide fresh prepared intents."""
    return list(BookingAttempt.objects.filter(
        status='PREPARED', case__channel__enabled=True, case__channel__adapter='demo_http',
    ).order_by('case__priority', 'created_at', 'pk').values_list('pk', flat=True)[:WORKER_BATCH_SIZE])


def due_reconciliation_attempt_ids():
    """Fair persistent recovery queue with grace and cooldown before any query."""
    now = timezone.now()
    stale = now - timedelta(seconds=SUBMISSION_GRACE_SECONDS)
    ready = now - timedelta(seconds=RECONCILIATION_COOLDOWN_SECONDS)
    return list(BookingAttempt.objects.filter(
        case__channel__enabled=True, case__channel__adapter='demo_http',
    ).filter(
        Q(status='RECONCILING', updated_at__lte=ready) |
        Q(status='SUBMITTING', submitted_at__lte=stale) |
        Q(status='SUBMITTING', submitted_at__isnull=True, updated_at__lte=stale)
    ).order_by('updated_at', 'pk').values_list('pk', flat=True)[:WORKER_BATCH_SIZE])
