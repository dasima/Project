"""Case references and durable workflow history; no passport or account secrets."""

import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Channel(TimestampedModel):
    class Adapter(models.TextChoices):
        MANUAL = "manual", "Manual only"
        DEMO_HTTP = "demo_http", "Local HTTP demo"

    name = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    country = models.CharField(max_length=64)
    visa_category = models.CharField(max_length=100)
    center = models.CharField(max_length=200)
    adapter = models.CharField(max_length=32, choices=Adapter.choices, default=Adapter.MANUAL)
    base_url = models.URLField(max_length=500, blank=True)
    enabled = models.BooleanField(default=False)
    auto_book = models.BooleanField(default=False)
    poll_interval_seconds = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    next_poll_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_status = models.CharField(max_length=40, blank=True)
    last_error = models.TextField(blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=64, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(poll_interval_seconds__gte=1),
                name="channel_positive_poll_interval",
            ),
            models.CheckConstraint(
                condition=models.Q(auto_book=False) | models.Q(adapter="demo_http"),
                name="channel_demo_only_auto_book",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.auto_book and self.adapter != self.Adapter.DEMO_HTTP:
            errors["auto_book"] = "Automatic booking is supported only by the local demo adapter."
        if self.adapter == self.Adapter.DEMO_HTTP and not self.base_url:
            errors["base_url"] = "The local demo adapter requires a base URL."
        previous = type(self).objects.filter(pk=self.pk).values("adapter", "base_url").first() if self.pk else None
        route_changed = previous and (
            previous["adapter"] != self.adapter or previous["base_url"] != self.base_url
        )
        if route_changed and BookingAttempt.objects.filter(case__channel_id=self.pk).exists():
            for field in ("adapter", "base_url"):
                if previous[field] != getattr(self, field):
                    errors[field] = "Provider routing cannot change after a booking attempt exists; create a new channel."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.code})"


class ApplicationCase(TimestampedModel):
    class Status(models.TextChoices):
        READY = "READY", "Ready"
        WAITING = "WAITING", "Waiting"
        BOOKED = "BOOKED", "Booked"
        PAUSED = "PAUSED", "Paused"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"

    reference = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.READY)
    earliest_date = models.DateField()
    latest_date = models.DateField()
    authorization_expires_at = models.DateTimeField()
    auto_submit = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["priority", "created_at", "pk"]
        indexes = [models.Index(fields=["channel", "status", "priority"], name="case_matching_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(earliest_date__lte=models.F("latest_date")),
                name="case_valid_date_range",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.earliest_date and self.latest_date and self.earliest_date > self.latest_date:
            errors["latest_date"] = "The latest date must be on or after the earliest date."
        if self.auto_submit and (
            not self.authorization_expires_at or self.authorization_expires_at <= timezone.now()
        ):
            errors["authorization_expires_at"] = "Automatic submission requires a current authorization."
        previous = type(self).objects.filter(pk=self.pk).values("reference", "channel_id").first() if self.pk else None
        if previous and self.bookingattempt_set.exists():
            if previous["reference"] != self.reference:
                errors["reference"] = "The case reference cannot change after a booking attempt exists."
            if previous["channel_id"] != self.channel_id:
                errors["channel"] = "The channel cannot change after a booking attempt exists."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.reference


class SlotObservation(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT)
    slot_id = models.CharField(max_length=200)
    starts_at = models.DateTimeField(db_index=True)
    observed_at = models.DateTimeField(default=timezone.now)
    available = models.BooleanField(default=True)

    class Meta:
        ordering = ["-observed_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["channel", "slot_id"], name="unique_channel_slot"),
        ]

    def __str__(self):
        return f"{self.channel.code}: {self.slot_id}"


class BookingAttempt(TimestampedModel):
    class Status(models.TextChoices):
        PREPARED = "PREPARED", "Prepared"
        SUBMITTING = "SUBMITTING", "Submitting"
        RECONCILING = "RECONCILING", "Reconciling"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        HUMAN_REQUIRED = "HUMAN_REQUIRED", "Human required"

    operation_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    case = models.ForeignKey(ApplicationCase, on_delete=models.PROTECT)
    observation = models.ForeignKey(SlotObservation, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREPARED, db_index=True)
    confirmation_reference = models.CharField(max_length=200, blank=True)
    detail = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["case"],
                condition=models.Q(status__in=[
                    "PREPARED", "SUBMITTING", "RECONCILING", "HUMAN_REQUIRED", "CONFIRMED",
                ]),
                name="unique_effective_attempt_per_case",
            ),
        ]

    def __str__(self):
        return f"{self.operation_id}: {self.status}"


class CrawlRun(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT)
    status = models.CharField(max_length=40)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    slot_count = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at", "pk"]

    def __str__(self):
        return f"{self.channel.code}: {self.status}"


class AuditEvent(models.Model):
    event_type = models.CharField(max_length=100, db_index=True)
    case = models.ForeignKey(ApplicationCase, on_delete=models.PROTECT, null=True, blank=True)
    attempt = models.ForeignKey(BookingAttempt, on_delete=models.PROTECT, null=True, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "pk"]

    def __str__(self):
        return self.event_type
