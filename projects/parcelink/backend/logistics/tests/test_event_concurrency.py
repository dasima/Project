from concurrent.futures import ThreadPoolExecutor
import json
import uuid

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TransactionTestCase

from logistics.models import AuditLog, Customer, CustomerUser, Package, Shipment, TrackingEvent


class ManualEventConcurrencyTests(TransactionTestCase):
    def test_two_connections_with_same_source_key_commit_only_one_event(self):
        from logistics.services import record_manual_event

        customer = Customer.objects.create(code="CONCURRENT", name="并发客户")
        user = get_user_model().objects.create_superuser(username="concurrent-operator", password=None)
        shipment = Shipment.objects.create(
            number="CONCURRENT-SHIP", customer=customer, goods_summary="测试货物",
            transport_method="海运", origin_country="中国", origin_city="深圳",
            destination_country="马来西亚", destination_city="吉隆坡",
            recipient_name="测试收件人", recipient_phone="测试电话", recipient_address="测试地址",
        )

        def submit():
            try:
                actor = get_user_model().objects.get(pk=user.pk)
                return record_manual_event(
                    actor=actor, shipment_number=shipment.number, status="transit",
                    location="并发中转站", note="并发提交说明", source_key="manual:concurrent",
                ).created
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            created = list(pool.map(lambda _: submit(), range(2)))
        self.assertCountEqual(created, [True, False])
        self.assertEqual(TrackingEvent.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), 1)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, "transit")


class PrealertConcurrencyTests(TransactionTestCase):
    def test_two_connections_with_same_submission_key_create_only_one_package(self):
        customer = Customer.objects.create(code="PRE-RACE", name="并发预报客户")
        user = get_user_model().objects.create_user(username="prealert-race")
        CustomerUser.objects.create(customer=customer, user=user)
        clients = [Client(), Client()]
        for browser in clients:
            browser.force_login(user)
        payload = {
            "submissionKey": str(uuid.uuid4()), "trackingNumber": "SF-123456", "goods": "书籍",
            "pieces": 2, "weight": "1.250", "method": "海运", "destination": "新加坡",
        }

        def submit(browser):
            try:
                response = browser.post("/api/package-prealerts/", json.dumps(payload), content_type="application/json")
                return response.status_code, response.json()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(submit, clients))
        self.assertCountEqual([response[0] for response in responses], [200, 201])
        self.assertEqual(responses[0][1], responses[1][1])
        self.assertEqual(Package.objects.count(), 1)
