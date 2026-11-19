from django.contrib.auth import get_user_model
from django.test import TestCase


class AdminChineseLabelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = get_user_model().objects.create_superuser(username="labels-admin", password=None)

    def setUp(self):
        self.client.force_login(self.operator)

    def test_admin_home_names_business_models_in_chinese(self):
        response = self.client.get("/admin/")
        for label in (
            "集运系统后台", "运营管理", "客户", "客户账号", "承运商", "运单",
            "包裹预报", "物流轨迹", "回调接收记录", "同步任务", "操作审计",
        ):
            with self.subTest(label=label):
                self.assertContains(response, label)

    def test_customer_membership_form_uses_chinese_labels(self):
        response = self.client.get("/admin/logistics/customeruser/add/")
        form = response.context["adminform"].form
        self.assertEqual(form.fields["customer"].label, "客户")
        self.assertEqual(form.fields["user"].label, "登录账号")

    def test_manual_tracking_form_uses_chinese_labels(self):
        response = self.client.get("/admin/logistics/trackingevent/add/")
        form = response.context["adminform"].form
        for field, label in {
            "shipment": "运单", "status": "运输状态", "location": "事件位置",
            "occurred_at": "事件发生时间", "description": "更新说明 / 更正原因",
        }.items():
            with self.subTest(field=field):
                self.assertEqual(form.fields[field].label, label)
