from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from logistics.models import Customer, Shipment
from logistics.services import record_manual_event


class ShipmentAdminConcurrencyTests(TestCase):
    def test_stale_admin_edit_cannot_overwrite_new_tracking_projection(self):
        customer = Customer.objects.create(code="ADMIN-RACE", name="后台编辑客户")
        operator = get_user_model().objects.create_superuser(username="admin-race", password=None)
        shipment = Shipment.objects.create(
            number="ADMIN-RACE-SHIP", customer=customer, goods_summary="原始摘要",
            transport_method="海运", origin_country="中国", origin_city="深圳",
            destination_country="马来西亚", destination_city="吉隆坡",
            recipient_name="测试收件人", recipient_phone="测试电话", recipient_address="测试地址",
        )
        model_admin = admin.site._registry[Shipment]
        request = RequestFactory().post("/admin/logistics/shipment/")
        request.user = operator
        old_object = Shipment.objects.get(pk=shipment.pk)
        form_type = model_admin.get_form(request, old_object)
        initial = {field: getattr(old_object, field) for field in form_type.base_fields}
        initial.update(customer=customer.pk, carrier="", weight_kg="", volume_cbm="", estimated_delivery_date="", goods_summary="后台新摘要")
        form = form_type(initial, instance=old_object)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        stale_edited_object = form.save(commit=False)
        newest = record_manual_event(
            actor=operator, shipment_number=shipment.number, status="delivered",
            location="最新签收地点", note="收件确认", source_key="manual:admin-race",
        )
        model_admin.save_model(request, stale_edited_object, form, change=True)
        shipment.refresh_from_db()
        self.assertEqual(shipment.goods_summary, "后台新摘要")
        self.assertEqual(shipment.status, "delivered")
        self.assertEqual(shipment.current_location, "最新签收地点")
        self.assertEqual(shipment.latest_event_at, newest.event.occurred_at)
        self.assertEqual(shipment.delivered_at, newest.event.occurred_at)
