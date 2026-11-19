from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.models import ApplicationCase, Channel
from apps.demo_provider.models import DemoSlot


class Command(BaseCommand):
    help = "Create virtual demo customers and a local release window; never resets existing bookings."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://127.0.0.1:8010/demo-provider")
        parser.add_argument("--release-delay-seconds", type=int, default=0)
        parser.add_argument("--window-seconds", type=int, default=3600)
        parser.add_argument("--capacity", type=int, default=1)

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.ENABLE_DEMO_PROVIDER or not settings.DEMO_PROVIDER_TOKEN:
            raise CommandError("Enable the demo provider and configure its token in the private environment.")
        if options["release_delay_seconds"] < 0 or options["window_seconds"] <= 0 or options["capacity"] < 1:
            raise CommandError("Release delay must be nonnegative; window and capacity must be positive.")
        base_url = options["base_url"].rstrip("/")
        parsed = urlsplit(base_url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "web"} or parsed.path != "/demo-provider":
            raise CommandError("The seeded demo must target the local /demo-provider service.")
        from apps.crawler.http import HttpDemoAdapter

        try:
            HttpDemoAdapter(base_url, settings.DEMO_PROVIDER_TOKEN, settings.CRAWLER_ALLOWED_HOSTS)
        except ValueError as error:
            raise CommandError("Invalid local demo URL or token configuration.") from error
        channel, created = Channel.objects.get_or_create(code="demo-beijing-student", defaults={
            "name": "本地模拟：北京学生签证预约", "country": "DEMO", "visa_category": "student",
            "center": "Beijing (simulated)", "adapter": "demo_http", "base_url": base_url,
            "enabled": True, "auto_book": True, "poll_interval_seconds": 2,
        })
        if not created and channel.base_url != base_url:
            raise CommandError("Existing demo uses a different base URL; keep its history and use the existing configuration.")
        now = timezone.now()
        starts_at = now + timedelta(days=14)
        opens_at = now + timedelta(seconds=options["release_delay_seconds"])
        DemoSlot.objects.get_or_create(slot_id="demo-beijing-student-1", defaults={
            "starts_at": starts_at, "opens_at": opens_at,
            "closes_at": opens_at + timedelta(seconds=options["window_seconds"]),
            "remaining": options["capacity"],
        })
        for index in (1, 2):
            ApplicationCase.objects.get_or_create(reference=f"DEMO-{index:03}", defaults={
                "display_name": f"虚拟学生 {index}", "channel": channel,
                "earliest_date": timezone.localdate() + timedelta(days=7),
                "latest_date": timezone.localdate() + timedelta(days=40),
                "authorization_expires_at": now + timedelta(days=7), "auto_submit": True,
                "priority": index * 10,
            })
        for country, name, category, url in [
            ("FR", "法国长期留学（未接入）", "long_stay_student", "https://france-visas.gouv.fr/chine"),
            ("DE", "德国长期留学（未接入）", "national_student", "https://china.diplo.de/cn-zh/service/visa-einreise/nationales-visum-1345434"),
            ("GB", "英国 Student visa（未接入）", "student", "https://visa.vfsglobal.com/chn/en/gbr/your-appointment"),
        ]:
            Channel.objects.get_or_create(code=f"{country.lower()}-student-manual", defaults={
                "name": name, "country": country, "visa_category": category, "center": "待核验",
                "adapter": "manual", "base_url": url, "enabled": False, "auto_book": False,
            })
        self.stdout.write(self.style.SUCCESS("Demo seeded. Existing slots, authorizations and bookings were not reset."))
