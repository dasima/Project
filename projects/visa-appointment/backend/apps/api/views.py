from django.db import connection
from django.db.utils import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.core.models import ApplicationCase, BookingAttempt, Channel, CrawlRun, SlotObservation

from .auth import staff_or_token


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


COLLECTIONS = {
    "channels": (Channel, ["id", "code", "name", "country", "visa_category", "center", "adapter", "enabled", "auto_book", "poll_interval_seconds", "last_status", "last_error", "last_polled_at"]),
    "cases": (ApplicationCase, ["id", "reference", "display_name", "channel_id", "status", "earliest_date", "latest_date", "authorization_expires_at", "auto_submit", "priority"]),
    "observations": (SlotObservation, ["id", "channel_id", "slot_id", "starts_at", "observed_at", "available"]),
    "attempts": (BookingAttempt, ["id", "operation_id", "case_id", "observation_id", "status", "confirmation_reference", "detail", "created_at", "submitted_at", "confirmed_at"]),
    "crawl-runs": (CrawlRun, ["id", "channel_id", "status", "started_at", "finished_at", "slot_count", "detail", "duration_ms"]),
}


@staff_or_token
@require_GET
def collection(request, resource):
    try:
        model, fields = COLLECTIONS[resource]
    except KeyError:
        return JsonResponse({"error": "not_found"}, status=404)
    try:
        limit = max(1, min(int(request.GET.get("limit", 50)), 100))
        offset = max(0, int(request.GET.get("offset", 0)))
    except (ValueError, TypeError):
        return JsonResponse({"error": "invalid_pagination"}, status=400)
    records = model.objects.order_by("-pk")
    return JsonResponse({"count": records.count(), "results": list(records.values(*fields)[offset:offset + limit])})
