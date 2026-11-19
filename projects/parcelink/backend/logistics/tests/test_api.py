import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sessions.models import Session
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from logistics.models import AuditLog, Customer, CustomerUser, Package, Shipment, TrackingEvent


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PortalAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(code="API-A", name="甲客户")
        cls.other_customer = Customer.objects.create(code="API-B", name="乙客户")
        cls.user = get_user_model().objects.create_user(username="api-a", password="test-password")
        cls.other_user = get_user_model().objects.create_user(username="api-b", password="test-password")
        CustomerUser.objects.create(customer=cls.customer, user=cls.user)
        CustomerUser.objects.create(customer=cls.other_customer, user=cls.other_user)
        cls.operator = get_user_model().objects.create_user(
            username="api-operator", password="test-password", is_staff=True
        )
        cls.operator.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="logistics",
                codename__in=["view_shipment", "change_shipment", "add_trackingevent"],
            )
        )
        cls.staff_without_permissions = get_user_model().objects.create_user(
            username="api-staff", password="test-password", is_staff=True
        )
        cls.shipment = cls.make_shipment("API-SHIP-A", cls.customer)
        cls.other_shipment = cls.make_shipment("API-SHIP-B", cls.other_customer)

    @staticmethod
    def make_shipment(number, customer):
        return Shipment.objects.create(
            number=number,
            customer=customer,
            goods_summary="测试货物",
            transport_method="空运专线",
            origin_country="中国",
            origin_city="深圳",
            destination_country="马来西亚",
            destination_city="吉隆坡",
            recipient_name="不可进入审计的收件姓名",
            recipient_phone="不可进入审计的收件电话",
            recipient_address="不可进入审计的收件地址",
        )

    def post_json(self, path, values, client=None, **headers):
        return (client or self.client).post(path, json.dumps(values), content_type="application/json", **headers)

    def event_payload(self, **changes):
        values = {"status": "transit", "location": "中转站", "note": "测试运输更新", "sourceKey": "manual:api-001"}
        values.update(changes)
        return values

    def test_anonymous_requests_are_denied_without_redirect(self):
        for path in ("/api/auth/me/", "/api/shipments/", "/api/shipments/API-SHIP-A/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_customer_can_only_read_own_shipments_and_foreign_detail_is_404(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/shipments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["results"]], ["API-SHIP-A"])
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(self.client.get("/api/shipments/API-SHIP-B/").status_code, 404)
        detail = self.client.get("/api/shipments/API-SHIP-A/").json()
        self.assertEqual(detail["shipment"]["recipient"]["name"], self.shipment.recipient_name)

    def test_inactive_customer_loses_portal_access(self):
        self.client.force_login(self.user)
        self.customer.is_active = False
        self.customer.save()
        self.assertEqual(self.client.get("/api/shipments/").status_code, 403)

    def test_staff_flag_does_not_grant_global_shipment_access(self):
        self.client.force_login(self.staff_without_permissions)
        self.assertEqual(self.client.get("/api/shipments/").status_code, 403)
        self.client.force_login(self.operator)
        response = self.client.get("/api/shipments/?limit=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertTrue(response.json()["next"].startswith("/api/shipments/?"))
        self.assertEqual(len(self.client.get(response.json()["next"]).json()["results"]), 1)

    def test_login_requires_csrf_and_rotates_token(self):
        browser = Client(enforce_csrf_checks=True)
        credentials = {"username": "api-a", "password": "test-password", "remember": False, "role": "customer"}
        self.assertEqual(self.post_json("/api/auth/login/", credentials, browser).status_code, 403)
        token = browser.get("/api/auth/csrf/").json()["csrfToken"]
        previous_cookie = browser.cookies["csrftoken"].value
        response = self.post_json("/api/auth/login/", credentials, browser, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["customerCode"], "API-A")
        self.assertNotEqual(browser.cookies["csrftoken"].value, previous_cookie)
        self.assertEqual(browser.cookies["sessionid"]["max-age"], "")

    def test_role_spoof_and_bad_credentials_share_generic_failure(self):
        bodies = [
            {"username": "api-a", "password": "test-password", "role": "admin"},
            {"username": "api-a", "password": "wrong", "role": "customer"},
            {"username": "does-not-exist", "password": "wrong", "role": "customer"},
        ]
        responses = [self.post_json("/api/auth/login/", body) for body in bodies]
        self.assertEqual([response.status_code for response in responses], [401, 401, 401])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(responses[1].json(), responses[2].json())

    def test_database_session_can_be_read_by_second_client_and_logout_is_shared(self):
        response = self.post_json("/api/auth/login/", {
            "username": "api-a", "password": "test-password", "remember": True, "role": "customer"
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Session.objects.filter(session_key=self.client.cookies["sessionid"].value).exists())
        second_instance = Client()
        second_instance.cookies = self.client.cookies.copy()
        self.assertEqual(second_instance.get("/api/auth/me/").json()["user"]["username"], "api-a")
        self.assertEqual(self.post_json("/api/auth/logout/", {}).status_code, 204)
        self.assertEqual(second_instance.get("/api/auth/me/").status_code, 401)

    def test_customer_cannot_append_tracking_events(self):
        self.client.force_login(self.user)
        response = self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TrackingEvent.objects.exists())

    def test_both_permissions_are_required_to_append_events(self):
        self.staff_without_permissions.user_permissions.add(
            Permission.objects.get(content_type__app_label="logistics", codename="add_trackingevent")
        )
        self.client.force_login(self.staff_without_permissions)
        self.assertEqual(
            self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload()).status_code, 403
        )

    def test_event_writes_are_idempotent_and_keep_audit_free_of_recipient_pii(self):
        self.client.force_login(self.operator)
        response = self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload()).status_code, 200)
        self.assertEqual(TrackingEvent.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), 1)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, "transit")
        audit_text = json.dumps(AuditLog.objects.get().changes)
        for pii in (self.shipment.recipient_name, self.shipment.recipient_phone, self.shipment.recipient_address):
            self.assertNotIn(pii, audit_text)

    def test_older_events_are_recorded_without_reverting_latest_projection(self):
        self.client.force_login(self.operator)
        current_time = timezone.now() - timedelta(minutes=5)
        response = self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload(
            status="delivered", occurredAt=current_time.isoformat()
        ))
        self.assertEqual(response.status_code, 201)
        response = self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload(
            status="warehouse", sourceKey="manual:older", occurredAt=(current_time - timedelta(days=1)).isoformat()
        ))
        self.assertEqual(response.status_code, 201)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, "delivered")
        self.assertEqual(self.shipment.delivered_at, current_time)
        self.assertEqual(TrackingEvent.objects.count(), 2)

    def test_reusing_source_key_with_different_event_is_conflict(self):
        self.client.force_login(self.operator)
        self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload())
        response = self.post_json("/api/shipments/API-SHIP-A/events/", self.event_payload(status="customs"))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(TrackingEvent.objects.count(), 1)

    def test_prealert_uses_session_customer_and_does_not_create_a_shipment(self):
        self.client.force_login(self.user)
        values = {"trackingNumber": "SF-123456", "goods": "书籍", "pieces": 2, "weight": "1.250", "method": "海运", "destination": "新加坡", "submissionKey": str(uuid.uuid4())}
        response = self.post_json("/api/package-prealerts/", values)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["prealert"]["status"], "prealert")
        package = Package.objects.get()
        self.assertEqual(package.customer_id, self.customer.pk)
        self.assertIsNone(package.shipment_id)
        self.assertIn("新加坡", package.description)
        self.assertIn("海运", package.description)
        self.assertEqual(Shipment.objects.count(), 2)
        values["customerId"] = self.other_customer.pk
        self.assertEqual(self.post_json("/api/package-prealerts/", values).status_code, 400)

    def test_prealert_retry_returns_original_package_and_conflicting_content_is_rejected(self):
        self.client.force_login(self.user)
        values = {"trackingNumber": "SF-123456", "goods": "书籍", "pieces": 2, "weight": "1.250", "method": "海运", "destination": "新加坡", "submissionKey": str(uuid.uuid4())}
        first = self.post_json("/api/package-prealerts/", values)
        self.assertEqual(first.status_code, 201)
        retry = self.post_json("/api/package-prealerts/", {**values, "weight": 1.25})
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json(), first.json())
        conflict = self.post_json("/api/package-prealerts/", {**values, "goods": "不同货物"})
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Package.objects.count(), 1)

    def test_prealert_submission_key_is_customer_scoped_and_required(self):
        values = {"trackingNumber": "SF-123456", "goods": "书籍", "pieces": 2, "weight": "1.250", "method": "海运", "destination": "新加坡", "submissionKey": str(uuid.uuid4())}
        self.client.force_login(self.user)
        self.assertEqual(self.post_json("/api/package-prealerts/", values).status_code, 201)
        self.client.force_login(self.other_user)
        self.assertEqual(self.post_json("/api/package-prealerts/", values).status_code, 201)
        self.assertEqual(Package.objects.count(), 2)
        for invalid in (None, "", "not-a-uuid", "a" * 65):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.post_json("/api/package-prealerts/", {**values, "submissionKey": invalid}).status_code, 400)

    def test_invalid_json_types_and_limits_return_errors_without_writes(self):
        self.client.force_login(self.user)
        path = "/api/package-prealerts/"
        self.assertEqual(self.client.post(path, "{", content_type="application/json").status_code, 400)
        valid = {"trackingNumber": "SF-123456", "goods": "书籍", "pieces": 1, "weight": 1.2, "method": "海运", "destination": "新加坡", "submissionKey": str(uuid.uuid4())}
        for invalid in ({"pieces": True}, {"pieces": 0}, {"weight": "NaN"}, {"weight": float("nan")}, {"weight": "文字"}, {"goods": "x" * 201}, {"trackingNumber": []}):
            with self.subTest(invalid=invalid):
                self.assertEqual(self.post_json(path, {**valid, **invalid}).status_code, 400)
        self.assertFalse(Package.objects.exists())
        self.assertEqual(self.client.get("/api/auth/login/").status_code, 405)
        self.assertEqual(self.client.get("/api/shipments/?limit=101").status_code, 400)

    def test_customer_write_endpoints_require_csrf_with_real_browser_checks(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(self.post_json("/api/package-prealerts/", {}, browser).status_code, 403)

    def test_public_configuration_exposes_placeholders_without_secrets(self):
        response = self.client.get("/api/public/config/")
        self.assertEqual(response.status_code, 200)
        values = response.json()
        self.assertFalse(values["demoMode"])
        self.assertIn("isPlaceholder", values["company"])
        self.assertNotIn("SECRET", json.dumps(values))

    def test_health_and_readiness_are_public_and_database_errors_are_redacted(self):
        health = self.client.get("/healthz/")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"status": "ok"})
        self.assertEqual(self.client.get("/readyz/").json(), {"status": "ready"})
        with patch("logistics.views.connection.cursor", side_effect=DatabaseError("secret database credentials")):
            response = self.client.get("/readyz/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_admin_appends_manual_event_via_same_projection_service(self):
        self.client.force_login(self.operator)
        now = timezone.now()
        response = self.client.post("/admin/logistics/trackingevent/add/", {
            "shipment": self.shipment.pk,
            "status": "transit",
            "description": "人工运输更新原因",
            "location": "人工中转站",
            "occurred_at_0": now.strftime("%Y-%m-%d"),
            "occurred_at_1": now.strftime("%H:%M:%S"),
            "latitude": "",
            "longitude": "",
            "_save": "保存",
        })
        self.assertEqual(response.status_code, 302)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.status, "transit")
        self.assertEqual(TrackingEvent.objects.get().source, "manual")
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_debug_static_routes_use_a_file_whitelist(self):
        with override_settings(DEBUG=True):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/app.js").status_code, 200)
            with self.assertLogs("django.request", level="WARNING"):
                self.assertEqual(self.client.get("/backend/config/settings.py").status_code, 404)
                self.assertEqual(self.client.get("/db/schema.sql").status_code, 404)
        with override_settings(DEBUG=False):
            self.assertEqual(self.client.get("/").status_code, 404)
