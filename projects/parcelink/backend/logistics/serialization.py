"""Public response shapes compatible with the existing customer interface."""
from zoneinfo import ZoneInfo

from django.utils import timezone

DISPLAY_TIME_ZONE = ZoneInfo("Asia/Shanghai")
PROGRESS = {"warehouse": 12, "shipped": 32, "transit": 62, "customs": 78, "delivery": 92, "delivered": 100}
CITY_CODES = {"深圳": "SZX", "广州": "CAN", "义乌": "YIW", "吉隆坡": "KUL", "新加坡": "SIN", "曼谷": "BKK"}


def display_datetime(value):
    return timezone.localtime(value, DISPLAY_TIME_ZONE).strftime("%Y-%m-%d %H:%M") if value else ""


def serialize_event(event):
    return {
        "id": event.pk,
        "sourceKey": event.source_key,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "status": event.status,
        "time": display_datetime(event.occurred_at),
        "occurredAt": event.occurred_at.isoformat(),
        "latitude": float(event.latitude) if event.latitude is not None else None,
        "longitude": float(event.longitude) if event.longitude is not None else None,
    }


def serialize_shipment(shipment):
    events = shipment.tracking_events.all()
    # Prefetching ordered events avoids one query per shipment in list views.
    if "tracking_events" not in getattr(shipment, "_prefetched_objects_cache", {}):
        events = events.order_by("-occurred_at", "-id")
    return {
        "id": shipment.number,
        "trackingNumber": shipment.tracking_number,
        "customerCode": shipment.customer.code,
        "status": shipment.status,
        "goods": shipment.goods_summary,
        "pieces": shipment.pieces,
        "weight": float(shipment.weight_kg) if shipment.weight_kg is not None else None,
        "volume": float(shipment.volume_cbm) if shipment.volume_cbm is not None else None,
        "method": shipment.transport_method,
        "location": shipment.current_location,
        "eta": shipment.estimated_delivery_date.isoformat() if shipment.estimated_delivery_date else "",
        "createdAt": display_datetime(shipment.created_at)[:10],
        "updatedAt": display_datetime(shipment.updated_at),
        "deliveredAt": shipment.delivered_at.isoformat() if shipment.delivered_at else None,
        "progress": PROGRESS[shipment.status],
        "origin": {
            "country": shipment.origin_country,
            "city": shipment.origin_city,
            "code": CITY_CODES.get(shipment.origin_city, ""),
        },
        "destination": {
            "country": shipment.destination_country,
            "city": shipment.destination_city,
            "code": CITY_CODES.get(shipment.destination_city, ""),
        },
        "recipient": {
            "name": shipment.recipient_name,
            "phone": shipment.recipient_phone,
            "address": shipment.recipient_address,
        },
        "timeline": [serialize_event(event) for event in events],
    }
