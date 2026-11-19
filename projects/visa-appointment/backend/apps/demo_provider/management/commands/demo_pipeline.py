from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.automation.services import poll_channel
from apps.core.models import BookingAttempt, Channel
from apps.demo_provider.models import DemoBooking


class Command(BaseCommand):
    help = "Run one local demo HTTP crawl/match/booking cycle. Start the web service first."

    def handle(self, *args, **options):
        if not settings.ENABLE_DEMO_PROVIDER:
            raise CommandError("This command only runs against the explicitly enabled local demo.")
        channel = Channel.objects.filter(code="demo-beijing-student", enabled=True, adapter="demo_http").first()
        if not channel:
            raise CommandError("Run seed_demo first.")
        run = poll_channel(channel.pk, execute=True)
        if run and run.status not in {"available", "no_slots"}:
            raise CommandError(f"Demo crawl returned {run.status}; check that the web service is running and token matches.")
        statuses = dict(BookingAttempt.objects.filter(case__channel=channel).values_list("case__reference", "status"))
        self.stdout.write(f"Crawl: {run.status if run else 'not_due'}")
        self.stdout.write(f"Cases: {statuses}")
        self.stdout.write(f"Confirmed local provider bookings: {DemoBooking.objects.count()}")
