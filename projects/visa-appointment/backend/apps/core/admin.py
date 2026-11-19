from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.core.exceptions import ValidationError
from django.db import router, transaction
from django.http import HttpResponseRedirect

from .models import ApplicationCase, AuditEvent, BookingAttempt, Channel, CrawlRun, SlotObservation


class SerializedOperationsAdmin(admin.ModelAdmin):
    """Serialize operator edits with workers and save only explicit field changes."""

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        # Preserve the values shown on GET. POST may load newer worker state;
        # comparing against that state would mistake an untouched field for an edit.
        for field in form_class.base_fields.values():
            field.show_hidden_initial = True
        return form_class

    def _lock_for_edit(self, object_id, target_channel_id=None):
        if self.model is Channel:
            return Channel.objects.select_for_update().filter(pk=object_id).first() if object_id else None
        previous = ApplicationCase.objects.filter(pk=object_id).values("channel_id").first() if object_id else None
        channel_ids = {previous["channel_id"]} if previous else set()
        if target_channel_id:
            try:
                channel_ids.add(Channel._meta.pk.to_python(target_channel_id))
            except (ValidationError, TypeError, ValueError):
                pass  # The bound form reports an invalid channel selection.
        # The worker uses this same order: channel, case, then attempt.
        list(Channel.objects.select_for_update().filter(pk__in=channel_ids).order_by("pk"))
        current = ApplicationCase.objects.select_for_update().filter(pk=object_id).first() if object_id else None
        if current and current.channel_id not in channel_ids:
            raise ValidationError("The case channel changed concurrently; reload before editing.")
        return current

    def _changeform_view(self, request, object_id, form_url, extra_context):
        if request.method != "POST":
            return super()._changeform_view(request, object_id, form_url, extra_context)
        try:
            with transaction.atomic(using=router.db_for_write(self.model)):
                self._lock_for_edit(unquote(object_id) if object_id else None, request.POST.get("channel"))
                return super()._changeform_view(request, object_id, form_url, extra_context)
        except ValidationError:
            self.message_user(
                request, "The record changed during this edit. Reload and review it before saving again.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

    def save_model(self, request, obj, form, change):
        with transaction.atomic(using=router.db_for_write(self.model)):
            current = self._lock_for_edit(obj.pk if change else None, getattr(obj, "channel_id", None))
            if not change:
                obj.full_clean()
                return super().save_model(request, obj, form, change)
            if current is None:
                raise ValidationError("The record no longer exists.")
            readonly = set(self.get_readonly_fields(request, obj))
            changed = {
                field.name for field in obj._meta.concrete_fields
                if field.editable and not field.primary_key
                and field.name in form.changed_data and field.name not in readonly
            }
            for field in obj._meta.concrete_fields:
                if field.name not in changed:
                    setattr(obj, field.attname, getattr(current, field.attname))
            # Recheck frozen identity/routing after acquiring the worker locks.
            obj.full_clean()
            if changed:
                obj.save(update_fields=sorted(changed | {"updated_at"}))


@admin.register(Channel)
class ChannelAdmin(SerializedOperationsAdmin):
    list_display = ("name", "code", "country", "adapter", "enabled", "auto_book", "last_status", "last_polled_at")
    list_filter = ("country", "adapter", "enabled", "auto_book")
    search_fields = ("name", "code", "center")
    readonly_fields = (
        "last_status", "last_error", "last_polled_at", "next_poll_at",
        "lease_token", "lease_expires_at", "created_at", "updated_at",
    )


@admin.register(ApplicationCase)
class ApplicationCaseAdmin(SerializedOperationsAdmin):
    list_display = ("reference", "display_name", "channel", "status", "auto_submit", "priority", "authorization_expires_at")
    list_filter = ("status", "auto_submit", "channel")
    search_fields = ("reference", "display_name")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("channel",)


class ReadOnlyHistoryAdmin(admin.ModelAdmin):
    """History is inspectable, never editable or deletable through operations UI."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


@admin.register(BookingAttempt)
class BookingAttemptAdmin(ReadOnlyHistoryAdmin):
    list_display = ("operation_id", "case", "status", "confirmation_reference", "created_at", "confirmed_at")
    list_filter = ("status",)
    search_fields = ("operation_id", "case__reference", "confirmation_reference")
    list_select_related = ("case",)


@admin.register(SlotObservation)
class SlotObservationAdmin(ReadOnlyHistoryAdmin):
    list_display = ("channel", "slot_id", "starts_at", "available", "observed_at")
    list_filter = ("channel", "available")
    search_fields = ("slot_id",)
    list_select_related = ("channel",)


@admin.register(CrawlRun)
class CrawlRunAdmin(ReadOnlyHistoryAdmin):
    list_display = ("channel", "status", "started_at", "finished_at", "slot_count", "duration_ms")
    list_filter = ("channel", "status")
    list_select_related = ("channel",)


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyHistoryAdmin):
    list_display = ("event_type", "case", "attempt", "created_at")
    list_filter = ("event_type",)
    search_fields = ("case__reference", "attempt__operation_id")
    list_select_related = ("case", "attempt")
