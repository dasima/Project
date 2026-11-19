from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.forms import modelform_factory
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .models import (
    ApplicationCase,
    AuditEvent,
    BookingAttempt,
    Channel,
    CrawlRun,
    SlotObservation,
)


class DomainModelTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(
            name="Local demo", code="local-demo", country="DE",
            visa_category="student", center="Demo center",
            adapter="demo_http", base_url="http://127.0.0.1:8010/demo-provider",
        )
        today = timezone.localdate()
        self.case = ApplicationCase.objects.create(
            reference="DEMO-001", display_name="Demo applicant", channel=self.channel,
            earliest_date=today, latest_date=today + timedelta(days=30),
            authorization_expires_at=timezone.now() + timedelta(days=1),
        )

    def test_channels_require_explicit_enablement_and_submission(self):
        self.assertFalse(self.channel.enabled)
        self.assertFalse(self.channel.auto_book)
        self.assertFalse(self.case.auto_submit)

    def test_each_active_or_confirmed_attempt_blocks_another_attempt(self):
        for status in ("PREPARED", "SUBMITTING", "RECONCILING", "HUMAN_REQUIRED", "CONFIRMED"):
            with self.subTest(status=status):
                existing = BookingAttempt.objects.create(case=self.case, status=status)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    BookingAttempt.objects.create(case=self.case, status="PREPARED")
                existing.delete()

    def test_definitive_rejection_allows_new_attempt_with_fresh_operation(self):
        rejected = BookingAttempt.objects.create(case=self.case, status="REJECTED")
        retry = BookingAttempt.objects.create(case=self.case, status="PREPARED")
        self.assertNotEqual(rejected.operation_id, retry.operation_id)
        self.assertEqual(self.case.bookingattempt_set.count(), 2)

    def test_invalid_date_range_fails_validation(self):
        self.case.earliest_date = self.case.latest_date + timedelta(days=1)
        with self.assertRaises(ValidationError) as caught:
            self.case.full_clean()
        self.assertIn("latest_date", caught.exception.message_dict)

    def test_invalid_date_range_is_also_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ApplicationCase.objects.filter(pk=self.case.pk).update(
                earliest_date=self.case.latest_date + timedelta(days=1),
            )

    def test_expired_authorization_cannot_enable_automatic_submission(self):
        self.case.auto_submit = True
        self.case.authorization_expires_at = timezone.now() - timedelta(seconds=1)
        with self.assertRaises(ValidationError) as caught:
            self.case.full_clean()
        self.assertIn("authorization_expires_at", caught.exception.message_dict)

    def test_expired_historical_case_can_remain_paused(self):
        self.case.status = "PAUSED"
        self.case.authorization_expires_at = timezone.now() - timedelta(days=1)
        self.case.full_clean()

    def test_automatic_booking_requires_demo_adapter(self):
        self.channel.adapter = "manual"
        self.channel.auto_book = True
        with self.assertRaises(ValidationError) as caught:
            self.channel.full_clean()
        self.assertIn("auto_book", caught.exception.message_dict)

    def test_poll_interval_must_be_positive(self):
        self.channel.poll_interval_seconds = 0
        with self.assertRaises(ValidationError):
            self.channel.full_clean()

    def test_slot_id_is_unique_within_channel(self):
        SlotObservation.objects.create(
            channel=self.channel, slot_id="slot-001", starts_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            SlotObservation.objects.create(
                channel=self.channel, slot_id="slot-001", starts_at=timezone.now(),
            )

    def test_case_reference_cannot_change_after_even_a_rejected_attempt(self):
        BookingAttempt.objects.create(case=self.case, status="REJECTED")
        self.case.reference = "DEMO-RENAMED"
        with self.assertRaises(ValidationError) as caught:
            self.case.full_clean()
        self.assertIn("reference", caught.exception.message_dict)

    def test_case_channel_cannot_change_after_an_attempt(self):
        BookingAttempt.objects.create(case=self.case, status="PREPARED")
        self.case.channel = Channel.objects.create(
            name="Another provider", code="other", country="DEMO",
            visa_category="student", center="Other center",
        )
        with self.assertRaises(ValidationError) as caught:
            self.case.full_clean()
        self.assertIn("channel", caught.exception.message_dict)

    def test_case_identity_can_change_before_an_attempt(self):
        self.case.reference = "DEMO-RENAMED"
        self.case.full_clean()
        self.case.save()
        self.assertEqual(ApplicationCase.objects.get(pk=self.case.pk).reference, "DEMO-RENAMED")

    def test_channel_route_is_frozen_for_unresolved_or_confirmed_attempts(self):
        for status in ("SUBMITTING", "RECONCILING", "HUMAN_REQUIRED", "CONFIRMED"):
            with self.subTest(status=status):
                attempt = BookingAttempt.objects.create(case=self.case, status=status)
                self.channel.adapter = "manual"
                self.channel.base_url = "http://127.0.0.1:8011/other-provider"
                try:
                    with self.assertRaises(ValidationError) as caught:
                        self.channel.full_clean()
                    self.assertIn("adapter", caught.exception.message_dict)
                    self.assertIn("base_url", caught.exception.message_dict)
                finally:
                    attempt.delete()

    def test_channel_route_is_frozen_even_after_submitted_attempt_rejection(self):
        BookingAttempt.objects.create(
            case=self.case, status="REJECTED", submitted_at=timezone.now(),
        )
        self.channel.base_url = "http://127.0.0.1:8011/other-provider"
        with self.assertRaises(ValidationError) as caught:
            self.channel.full_clean()
        self.assertIn("base_url", caught.exception.message_dict)

    def test_channel_route_is_frozen_for_prepared_slot_binding(self):
        BookingAttempt.objects.create(case=self.case, status="PREPARED")
        self.channel.base_url = "http://127.0.0.1:8011/other-provider"
        with self.assertRaises(ValidationError) as caught:
            self.channel.full_clean()
        self.assertIn("base_url", caught.exception.message_dict)

    def test_channel_route_is_frozen_after_rejection_without_submission(self):
        BookingAttempt.objects.create(case=self.case, status="REJECTED")
        self.channel.base_url = "http://127.0.0.1:8011/other-provider"
        with self.assertRaises(ValidationError) as caught:
            self.channel.full_clean()
        self.assertIn("base_url", caught.exception.message_dict)

    def test_channel_route_can_change_before_any_attempt(self):
        self.channel.base_url = "http://127.0.0.1:8011/other-provider"
        self.channel.full_clean()
        self.channel.save()
        self.assertEqual(Channel.objects.get(pk=self.channel.pk).base_url,
                         "http://127.0.0.1:8011/other-provider")

    def test_channel_controls_remain_editable_with_prepared_attempt(self):
        BookingAttempt.objects.create(case=self.case, status="PREPARED")
        self.channel.enabled = True
        self.channel.auto_book = True
        self.channel.poll_interval_seconds = 45
        self.channel.full_clean()
        self.channel.save()
        self.channel.refresh_from_db()
        self.assertTrue(self.channel.enabled)
        self.assertTrue(self.channel.auto_book)
        self.assertEqual(self.channel.poll_interval_seconds, 45)


class AdminSafetyTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = get_user_model().objects.create_superuser(
            username="operator", email="operator@example.invalid", password="test-only",
        )

    def test_side_effect_history_is_read_only_even_for_superusers(self):
        for model in (BookingAttempt, AuditEvent, CrawlRun, SlotObservation):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertTrue(model_admin.has_view_permission(self.request))
                self.assertFalse(model_admin.has_add_permission(self.request))
                self.assertFalse(model_admin.has_change_permission(self.request))
                self.assertFalse(model_admin.has_delete_permission(self.request))
                self.assertNotIn("delete_selected", model_admin.get_actions(self.request))

    def test_channels_and_cases_remain_manageable(self):
        for model in (Channel, ApplicationCase):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertTrue(model_admin.has_add_permission(self.request))
                self.assertTrue(model_admin.has_change_permission(self.request))


class AdminConcurrencyTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.create(
            name="Demo", code="demo", country="DEMO", visa_category="student",
            center="Demo", adapter="demo_http", base_url="http://127.0.0.1:8010/demo-provider",
        )
        self.case = ApplicationCase.objects.create(
            reference="DEMO-ADMIN", display_name="Before", channel=self.channel,
            earliest_date=timezone.localdate(), latest_date=timezone.localdate() + timedelta(days=30),
            authorization_expires_at=timezone.now() + timedelta(days=1),
        )
        self.request = RequestFactory().post("/admin/core/applicationcase/1/change/")
        self.request.user = get_user_model().objects.create_superuser(
            username="race-operator", email="race@example.invalid", password="test-only",
        )

    def test_case_save_revalidates_new_attempt_after_form_validation(self):
        form_class = modelform_factory(ApplicationCase, fields=("reference", "channel"))
        form = form_class(data={"reference": "CHANGED", "channel": self.channel.pk}, instance=self.case)
        self.assertTrue(form.is_valid(), form.errors)
        BookingAttempt.objects.create(case=self.case, status="PREPARED")
        with self.assertRaises(ValidationError):
            admin.site._registry[ApplicationCase].save_model(self.request, form.instance, form, True)
        self.case.refresh_from_db()
        self.assertEqual(self.case.reference, "DEMO-ADMIN")

    def test_channel_save_revalidates_claim_after_form_validation(self):
        form_class = modelform_factory(Channel, fields=("base_url",))
        form = form_class(data={"base_url": "http://127.0.0.1:8011/other"}, instance=self.channel)
        self.assertTrue(form.is_valid(), form.errors)
        BookingAttempt.objects.create(case=self.case, status="SUBMITTING")
        with self.assertRaises(ValidationError):
            admin.site._registry[Channel].save_model(self.request, form.instance, form, True)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.base_url, "http://127.0.0.1:8010/demo-provider")

    def test_untouched_case_status_preserves_worker_confirmation(self):
        form_class = modelform_factory(ApplicationCase, fields=("display_name", "status"))
        form = form_class(data={"display_name": "After", "status": "READY"}, instance=self.case)
        self.assertTrue(form.is_valid(), form.errors)
        ApplicationCase.objects.filter(pk=self.case.pk).update(status="BOOKED")
        admin.site._registry[ApplicationCase].save_model(self.request, form.instance, form, True)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "BOOKED")
        self.assertEqual(self.case.display_name, "After")

    def test_channel_edit_preserves_worker_lease_and_status(self):
        form_class = modelform_factory(Channel, fields=("name",))
        form = form_class(data={"name": "Renamed"}, instance=self.channel)
        self.assertTrue(form.is_valid(), form.errors)
        Channel.objects.filter(pk=self.channel.pk).update(lease_token="worker", last_status="available")
        admin.site._registry[Channel].save_model(self.request, form.instance, form, True)
        self.channel.refresh_from_db()
        self.assertEqual(self.channel.name, "Renamed")
        self.assertEqual(self.channel.lease_token, "worker")
        self.assertEqual(self.channel.last_status, "available")

    def test_post_uses_rendered_initial_status_to_identify_operator_edits(self):
        ApplicationCase.objects.filter(pk=self.case.pk).update(status="BOOKED")
        self.case.refresh_from_db()
        form_class = admin.site._registry[ApplicationCase].get_form(self.request, self.case)
        form = form_class(data={"status": "READY", "initial-status": "READY"}, instance=self.case)
        self.assertNotIn("status", form.changed_data)

    def test_late_validation_conflict_returns_admin_error_redirect(self):
        model_admin = admin.site._registry[ApplicationCase]
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)
        with patch.object(admin.ModelAdmin, "_changeform_view", side_effect=ValidationError("Changed concurrently")):
            response = model_admin._changeform_view(self.request, str(self.case.pk), None, None)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.request.path)
        self.assertTrue(list(get_messages(self.request)))

    def test_real_admin_post_preserves_status_from_worker_after_page_render(self):
        expiry = timezone.localtime(self.case.authorization_expires_at)
        data = {
            "reference": self.case.reference, "display_name": "After",
            "channel": str(self.channel.pk), "status": "READY",
            "earliest_date": self.case.earliest_date.isoformat(),
            "latest_date": self.case.latest_date.isoformat(),
            "authorization_expires_at_0": expiry.strftime("%Y-%m-%d"),
            "authorization_expires_at_1": expiry.strftime("%H:%M:%S"),
            "priority": "100", "_save": "Save",
        }
        for field, value in list(data.items()):
            if field != "_save":
                data[f"initial-{field}"] = value
        data["initial-display_name"] = "Before"
        data["initial-auto_submit"] = "False"
        ApplicationCase.objects.filter(pk=self.case.pk).update(status="BOOKED")
        BookingAttempt.objects.create(case=self.case, status="CONFIRMED", confirmation_reference="DEMO-OK")
        self.client.force_login(self.request.user)
        response = self.client.post(f"/admin/core/applicationcase/{self.case.pk}/change/", data)
        self.assertEqual(response.status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status, "BOOKED")
        self.assertEqual(self.case.display_name, "After")
