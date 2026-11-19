from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from logistics import models


class ModelValidationTests(SimpleTestCase):
    def test_shipment_rejects_unknown_status_during_field_validation(self):
        shipment_model = getattr(models, "Shipment", None)
        self.assertIsNotNone(shipment_model, "Shipment must provide status validation")
        shipment = shipment_model(status="unknown")
        with self.assertRaises(ValidationError) as caught:
            shipment.full_clean(validate_unique=False, validate_constraints=False)
        self.assertIn("status", caught.exception.message_dict)


class LogisticsConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = models.Customer.objects.create(code="CLIENT-A", name="客户甲")
        cls.other_customer = models.Customer.objects.create(code="CLIENT-B", name="客户乙")
        cls.carrier = models.Carrier.objects.create(code="CARRIER-A", name="承运商甲")
        cls.shipment = cls.create_shipment("SHP-001", cls.customer)
        cls.other_shipment = cls.create_shipment("SHP-002", cls.other_customer)

    @staticmethod
    def create_shipment(number, customer, **overrides):
        values = {
            "number": number,
            "customer": customer,
            "goods_summary": "测试货物",
            "transport_method": "air",
            "origin_country": "中国",
            "origin_city": "深圳",
            "destination_country": "德国",
            "destination_city": "柏林",
            "recipient_name": "测试收件人",
            "recipient_phone": "+49-000000",
            "recipient_address": "测试地址",
        }
        values.update(overrides)
        return models.Shipment.objects.create(**values)

    def create_event(self, **overrides):
        values = {
            "shipment": self.shipment,
            "source": "poll",
            "source_key": "carrier:event-001",
            "status": "transit",
            "title": "运输中",
            "description": "已抵达中转站",
            "location": "法兰克福",
            "occurred_at": timezone.now(),
        }
        values.update(overrides)
        return models.TrackingEvent.objects.create(**values)

    def assert_database_rejects(self, operation, constraint_name=None):
        # Each failing SQL statement rolls back to a savepoint, so the test's
        # outer transaction remains usable after an expected IntegrityError.
        with self.assertRaises(IntegrityError) as caught, transaction.atomic():
            operation()
        if constraint_name is not None:
            self.assertEqual(caught.exception.__cause__.diag.constraint_name, constraint_name)

    def test_poll_and_webhook_share_one_deduplication_key(self):
        self.create_event(source="poll")
        self.assert_database_rejects(lambda: self.create_event(source="webhook"))
        self.assertEqual(models.TrackingEvent.objects.count(), 1)

    def test_same_event_key_can_belong_to_different_shipments(self):
        self.create_event()
        self.create_event(shipment=self.other_shipment)
        self.assertEqual(models.TrackingEvent.objects.count(), 2)

    def test_package_cannot_reference_another_customers_shipment(self):
        self.assert_database_rejects(
            lambda: models.Package.objects.create(
                customer=self.customer,
                shipment=self.other_shipment,
                prealert_number="PRE-001",
                description="测试包裹",
                status="packed",
            ),
            constraint_name="package_shipment_customer_fk",
        )

    def test_package_model_validation_rejects_cross_customer_binding(self):
        package = models.Package(
            customer=self.customer,
            shipment=self.other_shipment,
            prealert_number="PRE-001",
            description="测试包裹",
            status="packed",
        )
        with self.assertRaises(ValidationError) as caught:
            package.full_clean()
        self.assertIn("shipment", caught.exception.message_dict)

    def test_same_customer_package_and_unassigned_prealert_are_valid(self):
        models.Package.objects.create(
            customer=self.customer,
            shipment=self.shipment,
            prealert_number="PRE-001",
            description="已装箱包裹",
            status="packed",
        )
        models.Package.objects.create(
            customer=self.other_customer,
            prealert_number="PRE-002",
            description="客户预报包裹",
        )
        self.assertEqual(models.Package.objects.count(), 2)

    def test_package_customer_update_cannot_break_existing_binding(self):
        package = models.Package.objects.create(
            customer=self.customer,
            shipment=self.shipment,
            prealert_number="PRE-001",
            description="已装箱包裹",
            status="packed",
        )
        self.assert_database_rejects(
            lambda: models.Package.objects.filter(pk=package.pk).update(
                customer=self.other_customer
            ),
            constraint_name="package_shipment_customer_fk",
        )

    def test_prealert_submission_key_is_unique_per_customer_in_database(self):
        models.Package.objects.create(
            customer=self.customer, prealert_number="PRE-IDEMPOTENT-1",
            submission_key="b5f70d7b-bc68-4ef0-92de-0795565d1abc", description="测试预报",
        )
        self.assert_database_rejects(
            lambda: models.Package.objects.create(
                customer=self.customer, prealert_number="PRE-IDEMPOTENT-2",
                submission_key="b5f70d7b-bc68-4ef0-92de-0795565d1abc", description="重复预报",
            ),
            constraint_name="package_customer_submission_unique",
        )
        models.Package.objects.create(
            customer=self.other_customer, prealert_number="PRE-IDEMPOTENT-3",
            submission_key="b5f70d7b-bc68-4ef0-92de-0795565d1abc", description="其他客户预报",
        )

    def test_manual_and_legacy_prealerts_may_omit_submission_key(self):
        for number, key in (("PRE-LEGACY-1", None), ("PRE-LEGACY-2", None), ("PRE-MANUAL-1", ""), ("PRE-MANUAL-2", "")):
            models.Package.objects.create(
                customer=self.customer, prealert_number=number, submission_key=key, description="历史预报",
            )
        self.assertEqual(models.Package.objects.count(), 4)

    def test_shipment_customer_update_cannot_reassign_another_customers_package(self):
        models.Package.objects.create(
            customer=self.customer,
            shipment=self.shipment,
            prealert_number="PRE-001",
            description="已装箱包裹",
            status="packed",
        )
        self.assert_database_rejects(
            lambda: models.Shipment.objects.filter(pk=self.shipment.pk).update(
                customer=self.other_customer
            ),
            constraint_name="package_shipment_customer_fk",
        )

    def test_packed_package_requires_shipment(self):
        self.assert_database_rejects(
            lambda: models.Package.objects.create(
                customer=self.customer,
                prealert_number="PRE-001",
                description="测试包裹",
                status="packed",
            )
        )

    def test_status_enumerations_are_checked_by_database(self):
        operations = [
            lambda: models.Shipment.objects.filter(pk=self.shipment.pk).update(status="bad"),
            lambda: self.create_event(status="bad"),
            lambda: self.create_event(source="bad"),
            lambda: models.Package.objects.create(
                customer=self.customer,
                prealert_number="PRE-001",
                description="测试包裹",
                status="bad",
            ),
            lambda: models.WebhookReceipt.objects.create(
                carrier=self.carrier, event_key="EVT-001", status="bad"
            ),
            lambda: models.SyncJob.objects.create(shipment=self.shipment, status="bad"),
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                self.assert_database_rejects(operation)

    def test_delivered_status_requires_delivery_time(self):
        self.assert_database_rejects(
            lambda: models.Shipment.objects.filter(pk=self.shipment.pk).update(status="delivered")
        )
        models.Shipment.objects.filter(pk=self.shipment.pk).update(
            status="delivered", delivered_at=timezone.now()
        )

    def test_non_delivered_status_forbids_delivery_time(self):
        self.assert_database_rejects(
            lambda: models.Shipment.objects.filter(pk=self.shipment.pk).update(
                status="transit", delivered_at=timezone.now()
            )
        )

    def test_shipment_measurements_reject_zero_pieces_and_negative_values(self):
        for invalid in ({"pieces": 0}, {"weight_kg": Decimal("-0.001")}, {"volume_cbm": Decimal("-0.0001")}):
            with self.subTest(invalid=invalid):
                self.assert_database_rejects(
                    lambda: models.Shipment.objects.filter(pk=self.shipment.pk).update(**invalid)
                )

    def test_package_measurements_reject_zero_pieces_and_negative_weight(self):
        for invalid in ({"pieces": 0}, {"weight_kg": Decimal("-0.001")}):
            with self.subTest(invalid=invalid):
                self.assert_database_rejects(
                    lambda: models.Package.objects.create(
                        customer=self.customer,
                        prealert_number="PRE-001",
                        description="测试包裹",
                        **invalid,
                    )
                )

    def test_tracking_coordinates_require_a_valid_pair(self):
        invalid_pairs = [
            {"latitude": "31.2304"},
            {"longitude": "121.4737"},
            {"latitude": "90.000001", "longitude": "0"},
            {"latitude": "-90.000001", "longitude": "0"},
            {"latitude": "0", "longitude": "180.000001"},
            {"latitude": "0", "longitude": "-180.000001"},
        ]
        for coordinates in invalid_pairs:
            with self.subTest(coordinates=coordinates):
                self.assert_database_rejects(lambda: self.create_event(**coordinates))
        self.create_event(latitude="90", longitude="-180")

    def test_carrier_tracking_number_is_unique_inside_carrier_account(self):
        self.shipment.carrier = self.carrier
        self.shipment.carrier_account = "ACCOUNT-A"
        self.shipment.tracking_number = "TRACK-001"
        self.shipment.save()
        self.assert_database_rejects(
            lambda: models.Shipment.objects.filter(pk=self.other_shipment.pk).update(
                carrier=self.carrier,
                carrier_account="ACCOUNT-A",
                tracking_number="TRACK-001",
            )
        )
        models.Shipment.objects.filter(pk=self.other_shipment.pk).update(
            carrier=self.carrier,
            carrier_account="ACCOUNT-B",
            tracking_number="TRACK-001",
        )

    def test_tracking_number_requires_carrier(self):
        self.assert_database_rejects(
            lambda: models.Shipment.objects.filter(pk=self.shipment.pk).update(
                tracking_number="TRACK-001"
            )
        )

    def test_sync_job_lock_only_exists_while_running(self):
        job = models.SyncJob.objects.create(shipment=self.shipment)
        self.assert_database_rejects(
            lambda: models.SyncJob.objects.filter(pk=job.pk).update(status="running")
        )
        self.assert_database_rejects(
            lambda: models.SyncJob.objects.filter(pk=job.pk).update(locked_until=timezone.now())
        )
        models.SyncJob.objects.filter(pk=job.pk).update(
            status="running", locked_until=timezone.now()
        )

    def test_webhook_receipt_deduplicates_carrier_event(self):
        models.WebhookReceipt.objects.create(carrier=self.carrier, event_key="EVT-001")
        self.assert_database_rejects(
            lambda: models.WebhookReceipt.objects.create(carrier=self.carrier, event_key="EVT-001")
        )

    def test_retry_attempt_counts_cannot_be_negative(self):
        self.assert_database_rejects(
            lambda: models.WebhookReceipt.objects.create(
                carrier=self.carrier, event_key="EVT-001", attempt_count=-1
            )
        )
        self.assert_database_rejects(
            lambda: models.SyncJob.objects.create(shipment=self.shipment, attempt_count=-1)
        )

    def test_one_account_belongs_to_one_customer(self):
        user = get_user_model().objects.create_user(username="client-a")
        models.CustomerUser.objects.create(customer=self.customer, user=user)
        self.assert_database_rejects(
            lambda: models.CustomerUser.objects.create(customer=self.other_customer, user=user)
        )

    def test_customer_with_business_records_cannot_be_deleted(self):
        with self.assertRaises(ProtectedError):
            self.customer.delete()

    def test_audit_log_survives_actor_deletion(self):
        user = get_user_model().objects.create_user(username="operator-a")
        log = models.AuditLog.objects.create(
            actor=user, shipment=self.shipment, action="shipment.status_changed"
        )
        user.delete()
        log.refresh_from_db()
        self.assertIsNone(log.actor_id)
        self.assertEqual(log.shipment_id, self.shipment.pk)
