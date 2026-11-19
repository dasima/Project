"""Same-origin JSON endpoints using Django auth, CSRF and database sessions."""
import json
import os
import re
import uuid
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from .models import CustomerUser, Package, Shipment, TrackingEvent
from .serialization import serialize_event, serialize_shipment
from .services import EventConflict, record_manual_event


class InputError(Exception):
    pass


def json_response(data, status=200):
    response = JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


def error_response(message, status, fields=None):
    value = {"error": message}
    if fields is not None:
        value["fields"] = fields
    return json_response(value, status=status)


def api_endpoint(*methods):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                response = error_response("此接口不支持该请求方法。", 405)
                response["Allow"] = ", ".join(methods)
                return response
            try:
                return view(request, *args, **kwargs)
            except InputError as error:
                return error_response(str(error), 400)
            except ValidationError as error:
                fields = error.message_dict if hasattr(error, "message_dict") else {"__all__": error.messages}
                return error_response("提交内容未通过校验。", 400, fields)
            except PermissionDenied:
                return error_response("无权执行此操作。", 403)
            except (Http404, Shipment.DoesNotExist):
                return error_response("记录不存在。", 404)
            except EventConflict as error:
                return error_response(str(error), 409)
            except IntegrityError:
                return error_response("记录已存在或与当前数据冲突，请刷新后重试。", 409)

        return wrapped
    return decorate


def reject_nonfinite_json(value):
    raise ValueError("Non-finite JSON numbers are not valid.")


def parse_json(request, allowed_fields):
    if request.content_type != "application/json":
        raise InputError("请使用 application/json 提交内容。")
    try:
        value = json.loads(request.body, parse_constant=reject_nonfinite_json)
    except (ValueError, UnicodeDecodeError):
        raise InputError("请求内容必须是有效的 JSON。") from None
    if not isinstance(value, dict):
        raise InputError("请求内容必须是 JSON 对象。")
    if set(value) - set(allowed_fields):
        raise InputError("请求包含不支持的字段。")
    return value


def text_field(values, field, max_length, *, required=True, default="", trim=True):
    value = values.get(field, default)
    if not isinstance(value, str):
        raise InputError(f"{field} 必须是文本。")
    if trim:
        value = value.strip()
    if (required and not value) or len(value) > max_length:
        raise InputError(f"{field} 必须为 1–{max_length} 个字符。" if required else f"{field} 超过最大长度。")
    return value


def integer_field(values, field, *, default=1, minimum=1, maximum=2147483647):
    value = values.get(field, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise InputError(f"{field} 必须是 {minimum}–{maximum} 之间的整数。")
    return value


def decimal_field(values, field):
    value = values.get(field)
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise InputError(f"{field} 必须是非负数字。")
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        raise InputError(f"{field} 必须是非负数字。") from None
    if not value.is_finite() or value < 0:
        raise InputError(f"{field} 必须是非负数字。")
    return value


def portal_identity(user):
    if not user.is_authenticated or not user.is_active:
        return None
    membership = CustomerUser.objects.select_related("customer").filter(user=user).first()
    if user.has_perm("logistics.view_shipment"):
        role = "admin"
    elif membership is not None and membership.customer.is_active:
        role = "customer"
    else:
        raise PermissionDenied
    return {
        "id": user.pk,
        "username": user.get_username(),
        "name": user.get_full_name() or (membership.customer.name if role == "customer" else user.get_username()),
        "role": role,
        "customerCode": membership.customer.code if membership and membership.customer.is_active else None,
    }


def require_identity(request):
    identity = portal_identity(request.user)
    if identity is None:
        return None, error_response("请先登录。", 401)
    return identity, None


def visible_shipments(request, identity):
    queryset = Shipment.objects.select_related("customer", "carrier").prefetch_related(
        Prefetch("tracking_events", queryset=TrackingEvent.objects.order_by("-occurred_at", "-id"))
    )
    if identity["role"] == "customer":
        queryset = queryset.filter(customer__accounts__user=request.user, customer__is_active=True)
    return queryset


@api_endpoint("GET")
def public_config(request):
    defaults = {"name": "项目名称待定", "phone": "000-00000000", "email": "support@example.com"}
    company = {
        "name": os.environ.get("COMPANY_NAME", "").strip() or defaults["name"],
        "phone": os.environ.get("PHONE", "").strip() or defaults["phone"],
        "email": os.environ.get("EMAIL", "").strip() or defaults["email"],
    }
    company["isPlaceholder"] = any(company[field] == default for field, default in defaults.items())
    return json_response({
        "company": company,
        "access": {
            "primaryDomain": os.environ.get("PRIMARY_DOMAIN", "").strip(),
            "backupDomains": [value.strip() for value in os.environ.get("BACKUP_DOMAINS", "").split(",") if value.strip()],
        },
        "demoMode": False,
    })


@api_endpoint("GET")
@ensure_csrf_cookie
def csrf_token(request):
    return json_response({"csrfToken": get_token(request)})


@api_endpoint("POST")
@csrf_protect
def login_view(request):
    values = parse_json(request, ["username", "password", "remember", "role"])
    username = text_field(values, "username", 150)
    password = text_field(values, "password", 1024, trim=False)
    role = text_field(values, "role", 16, required=False)
    remember = values.get("remember", False)
    if not isinstance(remember, bool) or role not in ("", "customer", "admin"):
        raise InputError("登录选项无效。")
    user = authenticate(request, username=username, password=password)
    identity = None
    if user is not None:
        try:
            identity = portal_identity(user)
        except PermissionDenied:
            pass
    if identity is None or (role and identity["role"] != role):
        return error_response("账号或密码不正确，或账户无权访问。", 401)
    login(request, user)
    request.session.set_expiry(settings.SESSION_COOKIE_AGE if remember else 0)
    return json_response({"user": identity})


@api_endpoint("GET")
def current_user(request):
    identity, failure = require_identity(request)
    return failure if failure is not None else json_response({"user": identity})


@api_endpoint("POST")
@csrf_protect
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)


@api_endpoint("GET")
def shipment_list(request):
    identity, failure = require_identity(request)
    if failure is not None:
        return failure
    queryset = visible_shipments(request, identity)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    if len(query) > 200:
        raise InputError("搜索内容不能超过 200 个字符。")
    if query:
        queryset = queryset.filter(
            Q(number__icontains=query) | Q(tracking_number__icontains=query)
            | Q(goods_summary__icontains=query) | Q(destination_city__icontains=query)
            | Q(destination_country__icontains=query)
        )
    if status == "moving":
        queryset = queryset.filter(status__in=["shipped", "transit", "customs", "delivery"])
    elif status in Shipment.Status.values:
        queryset = queryset.filter(status=status)
    elif status not in ("", "all"):
        raise InputError("运单状态无效。")
    try:
        limit = int(request.GET.get("limit", "50"))
        offset = int(request.GET.get("offset", "0"))
    except (ValueError, TypeError):
        raise InputError("分页参数必须是整数。") from None
    if not 1 <= limit <= 100 or not 0 <= offset <= 2147483647:
        raise InputError("limit 必须为 1–100，offset 必须为非负整数。")
    count = queryset.count()
    shipments = queryset.order_by("-updated_at", "-id")[offset:offset + limit]
    next_url = None
    if offset + limit < count:
        parameters = request.GET.copy()
        parameters["limit"] = str(limit)
        parameters["offset"] = str(offset + limit)
        next_url = "/api/shipments/?" + parameters.urlencode()
    return json_response({"results": [serialize_shipment(item) for item in shipments], "count": count, "next": next_url})


@api_endpoint("GET")
def shipment_detail(request, number):
    identity, failure = require_identity(request)
    if failure is not None:
        return failure
    shipment = get_object_or_404(visible_shipments(request, identity), number=number)
    return json_response({"shipment": serialize_shipment(shipment)})


@api_endpoint("GET", "POST")
def shipment_events(request, number):
    identity, failure = require_identity(request)
    if failure is not None:
        return failure
    if request.method == "GET":
        shipment = get_object_or_404(visible_shipments(request, identity), number=number)
        return json_response({"results": [serialize_event(event) for event in shipment.tracking_events.all()]})
    if identity["role"] != "admin" or not request.user.has_perms(
        ["logistics.add_trackingevent", "logistics.change_shipment"]
    ):
        raise PermissionDenied
    values = parse_json(request, ["status", "location", "note", "sourceKey", "occurredAt"])
    status = text_field(values, "status", 16)
    location = text_field(values, "location", 200)
    note = text_field(values, "note", 4000)
    source_key = text_field(values, "sourceKey", 128)
    occurred_at = None
    if "occurredAt" in values:
        raw_time = text_field(values, "occurredAt", 64)
        try:
            occurred_at = parse_datetime(raw_time)
        except ValueError:
            occurred_at = None
        if occurred_at is None or timezone.is_naive(occurred_at):
            raise InputError("occurredAt 必须是包含时区的 ISO 8601 时间。")
    result = record_manual_event(
        actor=request.user, shipment_number=number, status=status, location=location,
        note=note, source_key=source_key, occurred_at=occurred_at,
    )
    return json_response({
        "event": serialize_event(result.event),
        "shipment": serialize_shipment(result.shipment),
        "created": result.created,
        "applied": result.applied,
    }, status=201 if result.created else 200)


@api_endpoint("POST")
def package_prealert(request):
    identity, failure = require_identity(request)
    if failure is not None:
        return failure
    if identity["role"] != "customer":
        raise PermissionDenied
    values = parse_json(request, ["trackingNumber", "goods", "pieces", "weight", "method", "destination", "submissionKey"])
    raw_submission_key = text_field(values, "submissionKey", 64)
    try:
        submission_key = str(uuid.UUID(raw_submission_key))
    except ValueError:
        raise InputError("submissionKey 必须是有效的 UUID。") from None
    tracking_number = text_field(values, "trackingNumber", 80)
    if re.fullmatch(r"[A-Za-z0-9-]{6,80}", tracking_number) is None:
        raise InputError("快递单号必须由 6–80 位字母、数字或横线组成。")
    goods = text_field(values, "goods", 200)
    method = text_field(values, "method", 32)
    destination = text_field(values, "destination", 80)
    description = f"{goods} | 运输方式：{method} | 目的地：{destination}"
    pieces = integer_field(values, "pieces")
    weight_kg = decimal_field(values, "weight")
    created = False
    with transaction.atomic():
        membership = (
            CustomerUser.objects.select_related("customer")
            .select_for_update(of=("self", "customer"))
            .filter(user=request.user, customer__is_active=True)
            .first()
        )
        if membership is None:
            raise PermissionDenied
        package = Package.objects.filter(customer=membership.customer, submission_key=submission_key).first()
        if package is None:
            package = Package(
                customer=membership.customer,
                submission_key=submission_key,
                prealert_number="PRE" + timezone.now().strftime("%Y%m%d") + uuid.uuid4().hex[:12].upper(),
                domestic_tracking_number=tracking_number,
                description=description,
                pieces=pieces,
                weight_kg=weight_kg,
                status=Package.Status.PREALERT,
            )
            package.full_clean()
            try:
                with transaction.atomic():
                    package.save()
                created = True
            except IntegrityError as error:
                if error.__cause__.diag.constraint_name != "package_customer_submission_unique":
                    raise
                package = Package.objects.get(customer=membership.customer, submission_key=submission_key)
        if (
            package.domestic_tracking_number != tracking_number
            or package.description != description
            or package.pieces != pieces
            or package.weight_kg != weight_kg
        ):
            return error_response("该提交标识已用于不同的预报内容，请使用新的预报表单。", 409)
    return json_response({"prealert": {"number": package.prealert_number, "status": package.status}}, status=201 if created else 200)


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/"):
        return error_response("安全校验已失效，请刷新页面后重试。", 403)
    return HttpResponse("CSRF verification failed.", status=403)


@api_endpoint("GET")
def healthz(request):
    return json_response({"status": "ok"})


@api_endpoint("GET")
def readyz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return json_response({"status": "unavailable"}, status=503)
    return json_response({"status": "ready"})


FRONTEND_FILES = frozenset({
    "index.html", "app.js", "data.js", "site-config.js", "api.js", "styles.css",
    "map.js", "map.css", "shipment-view.js",
})


def development_frontend(request, asset="index.html"):
    if not settings.DEBUG or asset not in FRONTEND_FILES:
        raise Http404
    path = settings.BASE_DIR.parent / asset
    if not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"))
