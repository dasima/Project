"""Transactional business writes shared by the JSON API and Django Admin."""
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditLog, Shipment, TrackingEvent

EVENT_TITLES = {
    "warehouse": "包裹已入库",
    "shipped": "包裹已出库",
    "transit": "干线运输中",
    "customs": "目的地清关中",
    "delivery": "当地派送中",
    "delivered": "已签收",
}


class EventConflict(Exception):
    """A stable source key was reused for different event content."""


@dataclass(frozen=True)
class EventWriteResult:
    event: TrackingEvent
    shipment: Shipment
    created: bool
    applied: bool


@transaction.atomic
def record_manual_event(
    *, actor, shipment_number, status, location, note, source_key,
    occurred_at=None, latitude=None, longitude=None,
):
    if not actor.is_active or not actor.has_perms(
        ["logistics.add_trackingevent", "logistics.change_shipment"]
    ):
        raise PermissionDenied("无权更新运输轨迹。")
    # Only the projection row is locked. Carrier is nullable, and PostgreSQL
    # cannot apply FOR UPDATE to the nullable side of that outer join.
    shipment = Shipment.objects.select_for_update(of=("self",)).select_related("customer", "carrier").get(
        number=shipment_number
    )
    previous = TrackingEvent.objects.filter(shipment=shipment, source_key=source_key).first()
    if previous is not None:
        if (
            previous.source != TrackingEvent.Source.MANUAL
            or previous.status != status
            or previous.location != location
            or previous.description != note
            or previous.latitude != latitude
            or previous.longitude != longitude
            or (occurred_at is not None and previous.occurred_at != occurred_at)
        ):
            raise EventConflict("该更新标识已用于不同的轨迹内容，请使用新的标识。")
        return EventWriteResult(previous, shipment, False, False)

    event_time = occurred_at or timezone.now()
    if timezone.is_naive(event_time):
        raise ValidationError({"occurredAt": "轨迹时间必须包含时区。"})
    event = TrackingEvent(
        shipment=shipment,
        source=TrackingEvent.Source.MANUAL,
        source_key=source_key,
        status=status,
        title=EVENT_TITLES.get(status, ""),
        description=note,
        location=location,
        occurred_at=event_time,
        latitude=latitude,
        longitude=longitude,
    )
    event.full_clean()
    event.save()

    old_status = shipment.status
    applied = shipment.latest_event_at is None or event.occurred_at >= shipment.latest_event_at
    if applied:
        shipment.status = event.status
        shipment.current_location = event.location
        shipment.latest_event_at = event.occurred_at
        shipment.delivered_at = event.occurred_at if event.status == Shipment.Status.DELIVERED else None
        shipment.full_clean()
        shipment.save(update_fields=[
            "status", "current_location", "latest_event_at", "delivered_at", "updated_at"
        ])
    # Recipient data, event descriptions, locations and source keys are not
    # duplicated in the audit trail. The linked event contains the explanation.
    AuditLog.objects.create(
        actor=actor, shipment=shipment, action="shipment.tracking_event_added",
        reason="人工追加轨迹；说明保留于关联轨迹事件。",
        changes={
            "eventId": event.pk,
            "previousStatus": old_status,
            "eventStatus": event.status,
            "projectionUpdated": applied,
        },
    )
    return EventWriteResult(event, shipment, True, applied)
