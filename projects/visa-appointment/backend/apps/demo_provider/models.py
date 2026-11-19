from django.db import models


class DemoSlot(models.Model):
    slot_id = models.CharField(max_length=100, unique=True)
    starts_at = models.DateTimeField()
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    remaining = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(closes_at__gt=models.F("opens_at")), name="demo_valid_release_window"),
        ]


class DemoBooking(models.Model):
    operation_id = models.UUIDField(unique=True)
    case_reference = models.CharField(max_length=100, unique=True)
    slot = models.ForeignKey(DemoSlot, on_delete=models.PROTECT)
    confirmation_reference = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
