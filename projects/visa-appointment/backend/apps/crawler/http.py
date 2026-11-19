"""The documented demo-provider protocol, not an official visa-site adapter.

Every request is made once, without redirects or environment proxies. Unknown
submission outcomes must be reconciled by the caller using its operation UUID.
Only fixed diagnostic messages leave this module; remote error bodies, exception
messages and provider-supplied free text are never copied into stored details.
"""

import json
import math
import time
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from .types import BookingRequest, ObservationResult, Slot, SubmissionResult


MAX_BODY_BYTES = 256 * 1024
MAX_IDENTIFIER_LENGTH = 200


class _ProtocolChanged(ValueError):
    pass


def _identifier(value):
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= MAX_IDENTIFIER_LENGTH
        and not any(ord(char) < 32 or ord(char) == 127 for char in value)
    )


def _operation_id(value):
    if not isinstance(value, str):
        raise ValueError("Operation ID must be a UUID")
    try:
        operation = UUID(value)
    except (ValueError, AttributeError):
        raise ValueError("Operation ID must be a UUID") from None
    if str(operation) != value.lower():
        raise ValueError("Operation ID must use canonical UUID format")
    return str(operation)


class _AvailabilityParser(HTMLParser):
    """Require one closed main element and complete, unique, aware slots."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.state = None
        self.in_main = False
        self.closed_main = False
        self.slots = []
        self.slot_ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if len(attributes) != len(attrs):
            raise _ProtocolChanged()
        if tag == "main":
            if self.state is not None or self.closed_main:
                raise _ProtocolChanged()
            self.state = attributes.get("data-state")
            if self.state not in {"available", "no_slots", "auth_required", "challenge"}:
                raise _ProtocolChanged()
            self.in_main = True
        elif tag == "article":
            if not self.in_main or self.state != "available":
                raise _ProtocolChanged()
            slot_id = attributes.get("data-slot-id")
            starts_at = attributes.get("data-starts-at")
            if not _identifier(slot_id) or slot_id in self.slot_ids or not isinstance(starts_at, str):
                raise _ProtocolChanged()
            try:
                starts = datetime.fromisoformat(starts_at)
                if starts.utcoffset() is None:
                    raise ValueError()
            except ValueError:
                raise _ProtocolChanged() from None
            self.slot_ids.add(slot_id)
            self.slots.append(Slot(slot_id, starts))

    def handle_endtag(self, tag):
        if tag == "main":
            if not self.in_main:
                raise _ProtocolChanged()
            self.in_main = False
            self.closed_main = True

    def result(self):
        if not self.closed_main or self.in_main:
            raise _ProtocolChanged()
        if self.state == "available" and not self.slots:
            raise _ProtocolChanged()
        return ObservationResult(self.state, tuple(self.slots))


class HttpDemoAdapter:
    def __init__(self, base_url: str, token: str, allowed_hosts: tuple[str, ...], timeout: float = 5.0):
        if not isinstance(base_url, str) or any(ord(c) <= 32 for c in base_url):
            raise ValueError("Invalid demo provider base URL")
        try:
            parsed = urlsplit(base_url)
            port = parsed.port
        except ValueError:
            raise ValueError("Invalid demo provider base URL") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.hostname.lower() not in {host.lower() for host in allowed_hosts}
            or parsed.username is not None
            or parsed.password is not None
            or "?" in base_url
            or "#" in base_url
            or "\\" in base_url
            or (port is not None and port <= 0)
        ):
            raise ValueError("Demo provider URL is not permitted")
        if not isinstance(token, str) or not token or any(ord(c) <= 32 or ord(c) >= 127 for c in token):
            raise ValueError("A valid demo provider token is required")
        if not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be a finite positive number")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout = float(timeout)

    def _request(self, method, suffix, payload=None):
        deadline = time.monotonic() + self.timeout
        with httpx.Client(timeout=self.timeout, follow_redirects=False, trust_env=False) as client:
            with client.stream(
                method,
                self.base_url + suffix,
                headers={"Authorization": f"Bearer {self._token}", "Accept-Encoding": "identity"},
                json=payload,
            ) as response:
                # Error and redirect bodies are intentionally not read.
                if not 200 <= response.status_code < 300:
                    return response.status_code, response.headers, b""
                # Identity encoding makes the byte cap also a memory bound.
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise _ProtocolChanged()
                length = response.headers.get("Content-Length")
                if length and (not length.isdecimal() or int(length) > MAX_BODY_BYTES):
                    raise _ProtocolChanged()
                body = bytearray()
                # Do not buffer to a fixed chunk size: a trickle could otherwise
                # reset the socket timeout without reaching the deadline check.
                for chunk in response.iter_raw():
                    if time.monotonic() > deadline:
                        raise httpx.ReadTimeout("Demo provider request deadline exceeded")
                    if len(body) + len(chunk) > MAX_BODY_BYTES:
                        raise _ProtocolChanged()
                    body.extend(chunk)
                return response.status_code, response.headers, bytes(body)

    @staticmethod
    def _retry_after(headers):
        value = headers.get("Retry-After", "").strip()
        if value.isdecimal() and len(value) <= 8:
            return min(int(value), 86400)
        try:
            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                return None
            return max(0, min(math.ceil((when - datetime.now(timezone.utc)).total_seconds()), 86400))
        except (ValueError, TypeError, OverflowError):
            return None

    def observe(self) -> ObservationResult:
        try:
            status, headers, body = self._request("GET", "/availability/")
            if status in {401, 403}:
                return ObservationResult("auth_required", detail="Provider authentication required")
            if status == 429:
                return ObservationResult("rate_limited", detail="Provider rate limit", retry_after=self._retry_after(headers))
            if not 200 <= status < 300:
                return ObservationResult("transient_error", detail="Provider HTTP request failed")
            if headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "text/html":
                raise _ProtocolChanged()
            parser = _AvailabilityParser()
            parser.feed(body.decode("utf-8"))
            parser.close()
            result = parser.result()
            if any(self._token in slot.slot_id for slot in result.slots):
                raise _ProtocolChanged()
            return result
        except (httpx.HTTPError, OSError):
            return ObservationResult("transient_error", detail="Provider connection failed or timed out")
        except (ValueError, UnicodeError):
            return ObservationResult("parser_changed", detail="Provider availability format changed")

    def submit(self, request: BookingRequest) -> SubmissionResult:
        _operation_id(request.operation_id)
        if not _identifier(request.case_reference) or not _identifier(request.slot_id):
            raise ValueError("Booking requires a case reference and slot ID")
        return self._booking_result("POST", "/bookings/", payload=asdict(request))

    def reconcile(self, operation_id: str) -> SubmissionResult:
        operation = _operation_id(operation_id)
        return self._booking_result("GET", f"/bookings/{operation}/", reconciliation=True)

    def _booking_result(self, method, suffix, payload=None, reconciliation=False):
        try:
            status, headers, body = self._request(method, suffix, payload)
            # This adapter's documented lookup protocol defines 404 as absent.
            if reconciliation and status == 404:
                return SubmissionResult("rejected", detail="Demo operation not found")
            if status in {401, 403}:
                return SubmissionResult("human_required", detail="Provider authentication required")
            if not 200 <= status < 300:
                return SubmissionResult("unknown", detail="Provider outcome requires reconciliation")
            if headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise _ProtocolChanged()
            data = json.loads(body)
            if not isinstance(data, dict) or not isinstance(data.get("status"), str) or data["status"] not in {"confirmed", "rejected", "unknown", "human_required"}:
                raise _ProtocolChanged()
            result_status = data["status"]
            if result_status == "confirmed":
                reference = data.get("confirmation_reference")
                if not _identifier(reference) or self._token in reference:
                    raise _ProtocolChanged()
                return SubmissionResult("confirmed", reference.strip(), "Demo provider confirmed booking")
            return SubmissionResult(result_status, detail="Demo provider returned " + result_status)
        except (httpx.HTTPError, OSError, ValueError, UnicodeError):
            return SubmissionResult("unknown", detail="Provider outcome requires reconciliation")
