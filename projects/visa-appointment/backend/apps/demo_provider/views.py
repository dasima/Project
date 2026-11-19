"""A token-protected, explicitly enabled fake provider, never an official site."""

import json
from functools import wraps
from uuid import UUID, uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.api.auth import valid_bearer

from .models import DemoBooking, DemoSlot


def demo_access(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.ENABLE_DEMO_PROVIDER:
            raise Http404
        if not valid_bearer(request, settings.DEMO_PROVIDER_TOKEN):
            return JsonResponse({"error": "authentication_required"}, status=401)
        response = view(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    return wrapped


def result(status, reference="", detail="", http_status=200):
    return JsonResponse({"status": status, "confirmation_reference": reference, "detail": detail}, status=http_status)


def booking_result(booking):
    return result("confirmed", booking.confirmation_reference)


@demo_access
@require_GET
def availability(request):
    now = timezone.now()
    slots = list(DemoSlot.objects.filter(opens_at__lte=now, closes_at__gt=now, remaining__gt=0).order_by("starts_at"))
    articles = format_html_join("\n", '<article data-slot-id="{}" data-starts-at="{}"></article>',
                                ((s.slot_id, s.starts_at.isoformat()) for s in slots))
    page = format_html('<!doctype html><html lang="zh"><title>模拟签证放号站点</title><main data-state="{}">{}</main></html>',
                       "available" if slots else "no_slots", articles)
    return HttpResponse(page, content_type="text/html; charset=utf-8")


@csrf_exempt
@demo_access
@require_POST
def submit(request):
    if len(request.body) > 10_000:
        return result("rejected", detail="request_too_large", http_status=413)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
        operation_id = UUID(str(data["operation_id"]))
        reference, slot_id = data["case_reference"], data["slot_id"]
        if not all(isinstance(v, str) and 0 < len(v.strip()) <= 100 for v in (reference, slot_id)):
            raise ValueError
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return result("rejected", detail="invalid_booking_request", http_status=400)

    existing = DemoBooking.objects.filter(operation_id=operation_id).select_related("slot").first()
    if existing:
        if existing.case_reference != reference or existing.slot.slot_id != slot_id:
            return result("rejected", detail="operation_conflict", http_status=409)
        return booking_result(existing)
    try:
        with transaction.atomic():
            now = timezone.now()
            claimed = DemoSlot.objects.filter(slot_id=slot_id, opens_at__lte=now, closes_at__gt=now, remaining__gt=0).update(remaining=F("remaining") - 1)
            if not claimed:
                return result("rejected", detail="slot_unavailable")
            slot = DemoSlot.objects.get(slot_id=slot_id)
            booking = DemoBooking.objects.create(operation_id=operation_id, case_reference=reference,
                                                 slot=slot, confirmation_reference=f"DEMO-{uuid4().hex[:16]}")
    except IntegrityError:
        # A concurrent retry must not decrement capacity twice: the losing
        # transaction rolls back its decrement before querying the winner.
        existing = DemoBooking.objects.filter(operation_id=operation_id).select_related("slot").first()
        if existing and existing.case_reference == reference and existing.slot.slot_id == slot_id:
            return booking_result(existing)
        return result("rejected", detail="booking_conflict", http_status=409)
    return booking_result(booking)


@demo_access
@require_GET
def reconcile(request, operation_id):
    booking = DemoBooking.objects.filter(operation_id=operation_id).first()
    if not booking:
        return result("rejected", detail="operation_not_found", http_status=404)
    return booking_result(booking)
