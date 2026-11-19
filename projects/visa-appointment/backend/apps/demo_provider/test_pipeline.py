from io import StringIO

from django.core.management import call_command
from django.test import LiveServerTestCase, TestCase, override_settings

from apps.core.models import ApplicationCase, BookingAttempt, Channel
from apps.demo_provider.models import DemoBooking, DemoSlot


@override_settings(ENABLE_DEMO_PROVIDER=True, DEMO_PROVIDER_TOKEN="pipeline-demo-token")
class DemoSeedTests(TestCase):
    def test_seeding_again_preserves_existing_capacity_and_customer_state(self):
        call_command("seed_demo", stdout=StringIO())
        DemoSlot.objects.update(remaining=0)
        ApplicationCase.objects.filter(reference="DEMO-001").update(status="BOOKED")
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(DemoSlot.objects.get().remaining, 0)
        self.assertEqual(ApplicationCase.objects.get(reference="DEMO-001").status, "BOOKED")
        self.assertEqual(Channel.objects.filter(enabled=True).count(), 1)


@override_settings(ENABLE_DEMO_PROVIDER=True, DEMO_PROVIDER_TOKEN="pipeline-demo-token",
                   CRAWLER_ALLOWED_HOSTS=("localhost", "127.0.0.1"))
class HttpPipelineTests(LiveServerTestCase):
    def test_real_http_crawl_allocates_once_and_records_confirmation(self):
        from apps.automation.services import poll_channel

        call_command("seed_demo", base_url=self.live_server_url + "/demo-provider", stdout=StringIO())
        channel = Channel.objects.get(code="demo-beijing-student")
        run = poll_channel(channel.pk, execute=True)
        self.assertEqual(run.status, "available")
        self.assertEqual(DemoBooking.objects.count(), 1)
        attempt = BookingAttempt.objects.get(status="CONFIRMED")
        self.assertTrue(attempt.confirmation_reference.startswith("DEMO-"))
        self.assertEqual(attempt.case.status, "BOOKED")
        # Make a second crawl due; an exhausted remote inventory must not be
        # refilled by retrying initialization or by a duplicate worker cycle.
        Channel.objects.filter(pk=channel.pk).update(next_poll_at=None)
        second = poll_channel(channel.pk, execute=True)
        self.assertEqual(second.status, "no_slots")
        self.assertEqual(DemoBooking.objects.count(), 1)
        self.assertEqual(BookingAttempt.objects.filter(status="CONFIRMED").count(), 1)
