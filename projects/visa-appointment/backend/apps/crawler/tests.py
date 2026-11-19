import gzip
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

from .http import HttpDemoAdapter
from .types import BookingRequest


class DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.respond()

    def do_POST(self):
        self.respond()

    def respond(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.server.requests.append((self.command, self.path, self.headers.get("Authorization"), body))
        if self.server.delay:
            time.sleep(self.server.delay)
        self.send_response(self.server.status)
        for name, value in self.server.headers.items():
            self.send_header(name, value)
        self.end_headers()
        try:
            if self.server.drip:
                for _ in range(20):
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.025)
                return
            self.wfile.write(self.server.body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class HttpDemoAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), DemoHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/demo"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.adapter_class = HttpDemoAdapter
        self.request_class = BookingRequest
        self.server.status = 200
        self.server.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.server.body = b'<main data-state="no_slots"></main>'
        self.server.delay = 0
        self.server.drip = False
        self.server.requests = []
        self.adapter = self.adapter_class(self.base, "demo-secret-token", ("127.0.0.1",), timeout=0.2)

    def response(self, data, status=200):
        self.server.status = status
        self.server.headers = {"Content-Type": "application/json"}
        self.server.body = json.dumps(data).encode()

    def request(self):
        return self.request_class(str(uuid4()), "case-demo", "slot-1")

    def test_available_html_returns_aware_slots_and_sends_bearer(self):
        self.server.body = b'<html><main data-state="available"><article data-slot-id="s1" data-starts-at="2027-02-01T10:00:00+08:00"></article></main></html>'
        result = self.adapter.observe()
        self.assertEqual(result.status, "available")
        self.assertEqual(len(result.slots), 1)
        self.assertEqual(result.slots[0].slot_id, "s1")
        self.assertEqual(result.slots[0].starts_at.isoformat(), "2027-02-01T10:00:00+08:00")
        self.assertEqual(self.server.requests[0][:3], ("GET", "/demo/availability/", "Bearer demo-secret-token"))

    def test_explicit_nonavailable_states_are_preserved(self):
        for state in ("no_slots", "auth_required", "challenge"):
            with self.subTest(state=state):
                self.server.body = f'<main data-state="{state}"></main>'.encode()
                result = self.adapter.observe()
                self.assertEqual(result.status, state)
                self.assertEqual(result.slots, ())

    def test_401_and_429_are_distinct_and_do_not_copy_sensitive_body(self):
        self.server.body = b"private page demo-secret-token"
        self.server.status = 401
        result = self.adapter.observe()
        self.assertEqual(result.status, "auth_required")
        self.assertNotIn("demo-secret-token", result.detail)
        self.assertNotIn("private", result.detail)
        self.server.status = 429
        self.server.headers["Retry-After"] = "17"
        result = self.adapter.observe()
        self.assertEqual((result.status, result.retry_after), ("rate_limited", 17))

    def test_changed_or_ambiguous_html_never_looks_available(self):
        documents = [
            b'<h1>Login to continue</h1>',
            b'<main data-state="available"></main>',
            b'<main data-state="available"><article data-slot-id="s1" data-starts-at="2027-02-01T10:00:00"></article></main>',
            b'<main data-state="available"><article data-slot-id="s1" data-starts-at="bad"></article></main>',
            b'<main data-state="available"><article data-slot-id="s1" data-starts-at="2027-02-01T10:00:00Z"></article>',
            b'<main data-state="no_slots"></main><main data-state="available"></main>',
            b'<main data-state="available"><article data-slot-id="s1" data-starts-at="2027-02-01T10:00:00Z"></article><article data-slot-id="s1" data-starts-at="2027-02-02T10:00:00Z"></article></main>',
        ]
        for body in documents:
            with self.subTest(body=body):
                self.server.body = body
                self.assertEqual(self.adapter.observe().status, "parser_changed")

    def test_unexpected_content_type_is_parser_change(self):
        self.response({"status": "available"})
        self.assertEqual(self.adapter.observe().status, "parser_changed")

    def test_slot_identifier_respects_persistence_boundary(self):
        self.server.body = ('<main data-state="available"><article data-slot-id="' + "s" * 200 + '" data-starts-at="2027-02-01T10:00:00Z"></article></main>').encode()
        self.assertEqual(self.adapter.observe().status, "available")
        self.server.body = ('<main data-state="available"><article data-slot-id="' + "s" * 201 + '" data-starts-at="2027-02-01T10:00:00Z"></article></main>').encode()
        self.assertEqual(self.adapter.observe().status, "parser_changed")

    def test_oversized_response_is_bounded_and_never_returns_a_slot(self):
        self.server.body = b'<main data-state="available">' + b'x' * (300 * 1024) + b'</main>'
        self.assertEqual(self.adapter.observe().status, "parser_changed")

    def test_redirect_is_not_followed_or_treated_as_confirmation(self):
        self.server.status = 307
        self.server.headers["Location"] = self.base + "/destination/"
        self.assertEqual(self.adapter.observe().status, "transient_error")
        self.assertEqual(self.adapter.submit(self.request()).status, "unknown")
        self.assertEqual(len(self.server.requests), 2)

    def test_submit_and_reconcile_use_exact_protocol(self):
        self.response({"status": "confirmed", "confirmation_reference": "DEMO-123", "detail": "private demo-secret-token"})
        request = self.request()
        result = self.adapter.submit(request)
        self.assertEqual((result.status, result.confirmation_reference), ("confirmed", "DEMO-123"))
        self.assertNotIn("demo-secret-token", result.detail)
        self.assertNotIn("private", result.detail)
        sent = self.server.requests[0]
        self.assertEqual(sent[:3], ("POST", "/demo/bookings/", "Bearer demo-secret-token"))
        self.assertEqual(json.loads(sent[3]), {"operation_id": request.operation_id, "case_reference": "case-demo", "slot_id": "slot-1"})
        self.assertEqual(self.adapter.reconcile(request.operation_id).status, "confirmed")
        self.assertEqual(self.server.requests[-1][1], f"/demo/bookings/{request.operation_id}/")

    def test_confirmation_requires_a_nonempty_string_reference(self):
        for reference in ("", " ", None, 123):
            with self.subTest(reference=reference):
                self.response({"status": "confirmed", "confirmation_reference": reference})
                self.assertEqual(self.adapter.submit(self.request()).status, "unknown")

    def test_confirmation_reference_respects_persistence_boundary(self):
        self.response({"status": "confirmed", "confirmation_reference": "R" * 200})
        self.assertEqual(self.adapter.submit(self.request()).status, "confirmed")
        self.response({"status": "confirmed", "confirmation_reference": "R" * 201})
        self.assertEqual(self.adapter.submit(self.request()).status, "unknown")

    def test_submission_only_accepts_documented_result_statuses(self):
        for state in ("rejected", "unknown", "human_required"):
            with self.subTest(state=state):
                self.response({"status": state, "detail": "private demo-secret-token"})
                result = self.adapter.submit(self.request())
                self.assertEqual(result.status, state)
                self.assertEqual(result.confirmation_reference, "")
                self.assertNotIn("demo-secret-token", result.detail)
        for data in ({"status": "success"}, [], {"status": []}, {"status": {}}, {"status": "available"}, {"status": "confirmed"}):
            with self.subTest(data=data):
                self.response(data)
                self.assertEqual(self.adapter.submit(self.request()).status, "unknown")

    def test_timeout_is_unknown_and_never_reposts(self):
        self.server.delay = 0.4
        result = self.adapter.submit(self.request())
        self.assertEqual(result.status, "unknown")
        self.assertEqual(len(self.server.requests), 1)

    def test_observation_timeout_is_transient(self):
        self.server.delay = 0.4
        self.assertEqual(self.adapter.observe().status, "transient_error")

    def test_slow_trickle_cannot_extend_request_until_body_buffer_fills(self):
        self.server.drip = True
        adapter = self.adapter_class(self.base, "demo-secret-token", ("127.0.0.1",), timeout=0.1)
        started = time.monotonic()
        self.assertEqual(adapter.observe().status, "transient_error")
        self.assertLess(time.monotonic() - started, 0.35)

    def test_compressed_body_is_rejected_instead_of_decompressed_without_bound(self):
        self.server.headers["Content-Encoding"] = "gzip"
        self.server.body = gzip.compress(b'<main data-state="no_slots"></main>')
        self.assertEqual(self.adapter.observe().status, "parser_changed")

    def test_reconciliation_404_is_definitively_rejected_only_for_query(self):
        self.server.status = 404
        self.assertEqual(self.adapter.reconcile(str(uuid4())).status, "rejected")
        self.assertEqual(self.adapter.submit(self.request()).status, "unknown")

    def test_auth_failure_on_submission_needs_human_and_429_is_uncertain(self):
        self.server.status = 401
        self.assertEqual(self.adapter.submit(self.request()).status, "human_required")
        self.server.status = 429
        self.assertEqual(self.adapter.submit(self.request()).status, "unknown")

    def test_host_allowlist_and_base_url_validation_happen_before_network(self):
        for base in ("https://127.0.0.1.evil.test", "http://user:pass@127.0.0.1", self.base + "?secret=x", self.base + "#fragment", "file:///etc/passwd"):
            with self.subTest(base=base):
                with self.assertRaises(ValueError):
                    self.adapter_class(base, "demo-secret-token", ("127.0.0.1",))
        self.assertEqual(self.server.requests, [])

    def test_invalid_timeout_and_token_are_rejected(self):
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    self.adapter_class(self.base, "demo-secret-token", ("127.0.0.1",), timeout=timeout)
        for token in ("", "bad\r\nInjected: header"):
            with self.subTest(token=token):
                with self.assertRaises(ValueError):
                    self.adapter_class(self.base, token, ("127.0.0.1",))

    def test_path_injected_operation_id_is_not_sent(self):
        with self.assertRaises(ValueError):
            self.adapter.reconcile("../availability?secret=x")
        self.assertEqual(self.server.requests, [])
