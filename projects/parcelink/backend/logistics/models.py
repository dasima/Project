"""Authoritative logistics schema. Use migrations to change database structure."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ShipmentStatus(models.TextChoices):
    WAREHOUSE = "warehouse", "待出库"
    SHIPPED = "shipped", "已发货"
    TRANSIT = "transit", "运输中"
    CUSTOMS = "customs", "清关中"
    DELIVERY = "delivery", "派送中"
    DELIVERED = "delivered", "已签收"


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Customer(TimestampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    email = models.EmailField(max_length=254, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "logistics_customer"
        verbose_name = "客户"
        verbose_name_plural = "客户"

    def __str__(self):
        return f"{self.code} · {self.name}"


class CustomerUser(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="accounts")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_membership",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "logistics_customer_user"
        verbose_name = "客户账号"
        verbose_name_plural = "客户账号"

    def __str__(self):
        return f"{self.customer_id} · {self.user_id}"


class Carrier(TimestampedModel):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    api_base_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "logistics_carrier"
        verbose_name = "承运商"
        verbose_name_plural = "承运商"

    def __str__(self):
        return f"{self.code} · {self.name}"


class Shipment(TimestampedModel):
    Status = ShipmentStatus

    number = models.CharField(max_length=32, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="shipments")
    carrier = models.ForeignKey(
        Carrier, on_delete=models.PROTECT, related_name="shipments", null=True, blank=True
    )
    carrier_account = models.CharField(max_length=64, blank=True)
    tracking_number = models.CharField(max_length=80, blank=True)
    goods_summary = models.CharField(max_length=200)
    transport_method = models.CharField(max_length=32)
    origin_country = models.CharField(max_length=80)
    origin_city = models.CharField(max_length=80)
    destination_country = models.CharField(max_length=80)
    destination_city = models.CharField(max_length=80)
    recipient_name = models.CharField(max_length=80)
    recipient_phone = models.CharField(max_length=40)
    recipient_address = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAREHOUSE)
    pieces = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    volume_cbm = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    estimated_delivery_date = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    current_location = models.CharField(max_length=200, blank=True)
    latest_event_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "logistics_shipment"
        verbose_name = "运单"
        verbose_name_plural = "运单"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=ShipmentStatus.values), name="shipment_status_valid"
            ),
            models.CheckConstraint(condition=Q(pieces__gt=0), name="shipment_pieces_positive"),
            models.CheckConstraint(
                condition=Q(weight_kg__isnull=True) | Q(weight_kg__gte=0),
                name="shipment_weight_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(volume_cbm__isnull=True) | Q(volume_cbm__gte=0),
                name="shipment_volume_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="delivered", delivered_at__isnull=False)
                    | (~Q(status="delivered") & Q(delivered_at__isnull=True))
                ),
                name="shipment_delivery_time_matches",
            ),
            models.CheckConstraint(
                condition=Q(tracking_number="") | Q(carrier__isnull=False),
                name="shipment_tracking_requires_carrier",
            ),
            models.UniqueConstraint(
                fields=["carrier", "carrier_account", "tracking_number"],
                condition=~Q(tracking_number="") & Q(carrier__isnull=False),
                name="shipment_carrier_tracking_unique",
            ),
            # PostgreSQL requires this composite candidate key for the
            # customer-consistent package FK in migration 0002.
            models.UniqueConstraint(fields=["id", "customer"], name="shipment_id_customer_unique"),
        ]
        indexes = [
            models.Index(fields=["customer", "status", "-updated_at"], name="ship_cust_status_updated_idx"),
            models.Index(fields=["customer", "-updated_at"], name="ship_customer_updated_idx"),
        ]

    def __str__(self):
        return self.number


class Package(TimestampedModel):
    class Status(models.TextChoices):
        PREALERT = "prealert", "已预报"
        RECEIVED = "received", "已入库"
        PACKED = "packed", "已装箱"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="packages")
    shipment = models.ForeignKey(
        Shipment, on_delete=models.PROTECT, related_name="packages", null=True, blank=True
    )
    prealert_number = models.CharField(max_length=32, unique=True)
    submission_key = models.CharField(max_length=64, null=True, blank=True)
    domestic_tracking_number = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=200)
    pieces = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    weight_kg = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PREALERT)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "logistics_package"
        verbose_name = "包裹预报"
        verbose_name_plural = "包裹预报"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "submission_key"],
                condition=Q(submission_key__isnull=False) & ~Q(submission_key=""),
                name="package_customer_submission_unique",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["prealert", "received", "packed"]),
                name="package_status_valid",
            ),
            models.CheckConstraint(condition=Q(pieces__gt=0), name="package_pieces_positive"),
            models.CheckConstraint(
                condition=Q(weight_kg__isnull=True) | Q(weight_kg__gte=0),
                name="package_weight_nonnegative",
            ),
            models.CheckConstraint(
                condition=~Q(status="packed") | Q(shipment__isnull=False),
                name="package_packed_requires_shipment",
            ),
        ]

    def clean(self):
        super().clean()
        if self.shipment_id and self.customer_id:
            shipment_customer_id = (
                Shipment.objects.filter(pk=self.shipment_id)
                .values_list("customer_id", flat=True)
                .first()
            )
            if shipment_customer_id is not None and shipment_customer_id != self.customer_id:
                raise ValidationError({"shipment": "包裹和运单必须属于同一客户。"})

    def __str__(self):
        return self.prealert_number


class TrackingEvent(models.Model):
    class Source(models.TextChoices):
        MANUAL = "manual", "人工录入"
        POLL = "poll", "主动查询"
        WEBHOOK = "webhook", "承运商推送"

    Status = ShipmentStatus

    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="tracking_events")
    source = models.CharField(max_length=16, choices=Source.choices)
    source_key = models.CharField(max_length=128)
    status = models.CharField(max_length=16, choices=Status.choices)
    title = models.CharField(max_length=100)
    description = models.TextField()
    location = models.CharField(max_length=200)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    raw_status = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    class Meta:
        db_table = "logistics_tracking_event"
        verbose_name = "物流轨迹"
        verbose_name_plural = "物流轨迹"
        constraints = [
            models.UniqueConstraint(fields=["shipment", "source_key"], name="tracking_event_dedup_unique"),
            models.CheckConstraint(
                condition=Q(source__in=["manual", "poll", "webhook"]),
                name="tracking_event_source_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=ShipmentStatus.values), name="tracking_event_status_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                    )
                ),
                name="tracking_event_coordinates_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["shipment", "-occurred_at", "-id"], name="event_shipment_timeline_idx")
        ]

    def __str__(self):
        return f"{self.shipment_id} · {self.title}"


class WebhookReceipt(models.Model):
    """Only signature-verified deliveries may be inserted by the future adapter."""

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        PROCESSED = "processed", "已处理"
        FAILED = "failed", "失败"

    carrier = models.ForeignKey(Carrier, on_delete=models.PROTECT, related_name="webhook_receipts")
    event_key = models.CharField(max_length=128)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "logistics_webhook_receipt"
        verbose_name = "回调接收记录"
        verbose_name_plural = "回调接收记录"
        constraints = [
            models.UniqueConstraint(fields=["carrier", "event_key"], name="webhook_carrier_event_unique"),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "processed", "failed"]),
                name="webhook_receipt_status_valid",
            ),
        ]
        indexes = [models.Index(fields=["status", "received_at"], name="webhook_pending_queue_idx")]

    def __str__(self):
        return f"{self.carrier_id} · {self.event_key}"


class SyncJob(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待执行"
        RUNNING = "running", "执行中"
        SUCCEEDED = "succeeded", "已成功"
        FAILED = "failed", "失败"

    shipment = models.OneToOneField(Shipment, on_delete=models.CASCADE, related_name="sync_job")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    next_retry_at = models.DateTimeField(default=timezone.now)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "logistics_sync_job"
        verbose_name = "同步任务"
        verbose_name_plural = "同步任务"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pending", "running", "succeeded", "failed"]),
                name="sync_job_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="running", locked_until__isnull=False)
                    | (~Q(status="running") & Q(locked_until__isnull=True))
                ),
                name="sync_job_lock_matches_status",
            ),
        ]
        indexes = [models.Index(fields=["status", "next_retry_at"], name="sync_job_retry_queue_idx")]

    def __str__(self):
        return f"{self.shipment_id} · {self.status}"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="logistics_audit_logs",
        null=True,
        blank=True,
    )
    shipment = models.ForeignKey(
        Shipment, on_delete=models.PROTECT, related_name="audit_logs", null=True, blank=True
    )
    action = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    changes = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "logistics_audit_log"
        verbose_name = "操作审计"
        verbose_name_plural = "操作审计"
        indexes = [models.Index(fields=["shipment", "-created_at"], name="audit_shipment_created_idx")]

    def __str__(self):
        return f"{self.action} · {self.created_at}"
