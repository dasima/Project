import uuid

from django import forms
from django.contrib import admin

from .services import record_manual_event

from .models import (
    AuditLog,
    Carrier,
    Customer,
    CustomerUser,
    Package,
    Shipment,
    SyncJob,
    TrackingEvent,
    WebhookReceipt,
)

admin.site.site_header = "集运系统后台"
admin.site.site_title = "集运系统管理"
admin.site.index_title = "运营管理"


FIELD_LABELS = {
    "code": "编号", "name": "名称", "email": "邮箱", "phone": "联系电话",
    "is_active": "启用", "customer": "客户", "user": "登录账号", "carrier": "承运商",
    "api_base_url": "接口基础地址", "number": "运单号", "carrier_account": "承运商账号标识",
    "tracking_number": "承运商单号", "goods_summary": "货物摘要", "transport_method": "运输方式",
    "origin_country": "始发国家", "origin_city": "始发城市",
    "destination_country": "目的国家", "destination_city": "目的城市",
    "recipient_name": "收件人", "recipient_phone": "收件电话", "recipient_address": "收件地址",
    "status": "状态", "pieces": "件数", "weight_kg": "重量（kg）", "volume_cbm": "体积（m³）",
    "estimated_delivery_date": "预计送达日期", "delivered_at": "签收时间",
    "current_location": "当前位置", "latest_event_at": "最新轨迹时间",
    "shipment": "运单", "prealert_number": "预报编号", "domestic_tracking_number": "国内快递单号",
    "submission_key": "预报提交标识",
    "description": "说明", "received_at": "接收时间", "source": "事件来源",
    "source_key": "事件去重标识", "title": "轨迹标题", "location": "事件位置",
    "occurred_at": "事件发生时间", "raw_status": "承运商原始状态",
    "latitude": "纬度", "longitude": "经度", "event_key": "回调事件标识",
    "payload": "回调内容", "processed_at": "处理时间", "attempt_count": "尝试次数",
    "last_error": "最近错误", "next_retry_at": "下次重试时间", "locked_until": "锁定截止时间",
    "last_success_at": "最近成功时间", "actor": "操作账号", "action": "操作类型",
    "reason": "操作原因", "changes": "变更内容", "created_at": "创建时间", "updated_at": "更新时间",
}


class ChineseLabelsAdmin(admin.ModelAdmin):
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in FIELD_LABELS:
            kwargs.setdefault("label", FIELD_LABELS[db_field.name])
        if db_field.name == "status" and self.model in (Shipment, TrackingEvent):
            kwargs["label"] = "运输状态"
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(Customer)
class CustomerAdmin(ChineseLabelsAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(CustomerUser)
class CustomerUserAdmin(ChineseLabelsAdmin):
    list_display = ("customer", "user", "created_at")
    raw_id_fields = ("customer", "user")


@admin.register(Carrier)
class CarrierAdmin(ChineseLabelsAdmin):
    list_display = ("code", "name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Shipment)
class ShipmentAdmin(ChineseLabelsAdmin):
    list_display = ("number", "customer", "carrier", "tracking_number", "status", "updated_at")
    list_filter = ("status", "carrier")
    search_fields = ("number", "tracking_number", "customer__code")
    raw_id_fields = ("customer", "carrier")
    readonly_fields = ("status", "current_location", "latest_event_at", "delivered_at", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)
        # A tracking event may have committed after this form read the row.
        # Update only edited form fields so that a stale instance cannot write
        # the read-only tracking projection back over the newer event.
        editable = {
            field.name for field in obj._meta.concrete_fields
            if field.editable and not field.primary_key
            and field.name not in self.get_readonly_fields(request, obj)
        }
        changed_fields = set(form.changed_data) & editable
        if changed_fields:
            obj.save(update_fields=changed_fields | {"updated_at"})


@admin.register(Package)
class PackageAdmin(ChineseLabelsAdmin):
    list_display = ("prealert_number", "customer", "shipment", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("prealert_number", "domestic_tracking_number", "customer__code")
    raw_id_fields = ("customer", "shipment")
    readonly_fields = ("submission_key",)


class ManualTrackingEventForm(forms.ModelForm):
    description = forms.CharField(label="更新说明 / 更正原因", max_length=4000, widget=forms.Textarea)

    class Meta:
        model = TrackingEvent
        fields = ("shipment", "status", "description", "location", "occurred_at", "latitude", "longitude")


@admin.register(TrackingEvent)
class TrackingEventAdmin(ChineseLabelsAdmin):
    form = ManualTrackingEventForm
    list_display = ("shipment", "source", "status", "title", "occurred_at")
    list_filter = ("source", "status")
    search_fields = ("shipment__number", "source_key", "title")
    raw_id_fields = ("shipment",)

    def has_add_permission(self, request):
        return super().has_add_permission(request) and request.user.has_perm("logistics.change_shipment")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields) if obj is not None else ()

    def save_model(self, request, obj, form, change):
        result = record_manual_event(
            actor=request.user,
            shipment_number=obj.shipment.number,
            status=obj.status,
            location=obj.location,
            note=obj.description,
            source_key="manual:" + uuid.uuid4().hex,
            occurred_at=obj.occurred_at,
            latitude=obj.latitude,
            longitude=obj.longitude,
        )
        # ModelAdmin uses this same instance when logging the addition and
        # saving related form data after the shared service has committed it.
        obj.__dict__.update(result.event.__dict__)


class ReadOnlyOperationsAdmin(ChineseLabelsAdmin):
    """Operational evidence is inspected here; workers remain its only writers."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebhookReceipt)
class WebhookReceiptAdmin(ReadOnlyOperationsAdmin):
    list_display = ("carrier", "event_key", "status", "attempt_count", "received_at")
    list_filter = ("status", "carrier")
    search_fields = ("event_key",)


@admin.register(SyncJob)
class SyncJobAdmin(ReadOnlyOperationsAdmin):
    list_display = ("shipment", "status", "attempt_count", "next_retry_at", "locked_until")
    list_filter = ("status",)
    search_fields = ("shipment__number",)


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyOperationsAdmin):
    list_display = ("actor", "shipment", "action", "created_at")
    search_fields = ("shipment__number", "action")
