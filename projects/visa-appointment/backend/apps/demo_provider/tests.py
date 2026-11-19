from datetime import timedelta
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone


class DemoGateTests(TestCase):
    def test_provider_hidden_when_disabled(self):
        with override_settings(ENABLE_DEMO_PROVIDER=False):
            self.assertEqual(self.client.get("/demo-provider/availability/").status_code, 404)

    @override_settings(ENABLE_DEMO_PROVIDER=True, DEMO_PROVIDER_TOKEN="test-provider-token")
    def test_provider_requires_its_own_token(self):
        response = self.client.get("/demo-provider/availability/")
        self.assertEqual(response.status_code, 401)


@override_settings(ENABLE_DEMO_PROVIDER=True, DEMO_PROVIDER_TOKEN="test-provider-token")
class DemoInventoryTests(TestCase):
    def setUp(self):
        from .models import DemoSlot

        self.slot = DemoSlot.objects.create(
            slot_id="demo-beijing-student-1",
            starts_at=timezone.now() + timedelta(days=14),
            opens_at=timezone.now() - timedelta(seconds=1),
            closes_at=timezone.now() + timedelta(minutes=5),
            remaining=1,
        )
        self.headers = {"HTTP_AUTHORIZATION": "Bearer test-provider-token"}

    def book(self, *, operation_id=None, reference="DEMO-001"):
        return self.client.post(
            "/demo-provider/bookings/",
            {"operation_id": str(operation_id or uuid4()), "case_reference": reference,
             "slot_id": self.slot.slot_id},
            content_type="application/json", **self.headers,
        )

    def test_html_crawler_can_find_open_slot(self):
        response = self.client.get("/demo-provider/availability/", **self.headers)
        self.assertContains(response, 'data-state="available"')
        self.assertContains(response, 'data-slot-id="demo-beijing-student-1"')

    def test_repeat_operation_returns_one_confirmation_and_consumes_once(self):
        operation_id = uuid4()
        first = self.book(operation_id=operation_id)
        repeat = self.book(operation_id=operation_id)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["status"], "confirmed")
        self.assertEqual(repeat.json(), first.json())
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.remaining, 0)
        result = self.client.get(f"/demo-provider/bookings/{operation_id}/", **self.headers)
        self.assertEqual(result.json(), first.json())

    def test_sold_out_slot_does_not_allocate_a_second_seat(self):
        self.assertEqual(self.book().json()["status"], "confirmed")
        self.assertEqual(self.book(reference="DEMO-002").json()["status"], "rejected")

    def test_operation_id_cannot_be_reused_for_a_different_customer(self):
        operation_id = uuid4()
        self.book(operation_id=operation_id)
        response = self.book(operation_id=operation_id, reference="DEMO-002")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["status"], "rejected")

    def test_expired_or_not_yet_released_slot_is_unavailable(self):
        self.slot.opens_at = timezone.now() + timedelta(minutes=1)
        self.slot.save()
        self.assertContains(self.client.get("/demo-provider/availability/", **self.headers), 'data-state="no_slots"')
        self.assertEqual(self.book().json()["status"], "rejected")

    def test_missing_operation_is_explicitly_not_found(self):
        response = self.client.get(f"/demo-provider/bookings/{uuid4()}/", **self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "rejected")
