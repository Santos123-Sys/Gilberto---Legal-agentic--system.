import json
import threading
import unittest
from observability import MetadataTelemetry, correlation_id, from_environment, metadata_span

KEY = "synthetic-test-only-correlation-secret-123456789"


class WorkspaceObservabilityTests(unittest.TestCase):
    def event(self, **changes):
        return {"type": "AGENT_ANALYSIS_COMPLETE", "event_id": 2, "round": 1,
                "session_id": "confidential-client", "agent_id": "private-role",
                "cluster": "clusterA", "document_text": "CONFIDENTIAL CONTRACT",
                "prompt": "SECRET PROMPT", "parsed": {"secret": "PRIVATE OUTPUT"},
                "error": "Authorization: token-123", "prompt_tokens": 123,
                "estimated_input_tokens": 456, **changes}

    def test_allowlist_excludes_every_content_field_and_pseudonymizes_identifiers(self):
        span = metadata_span("confidential-client", self.event(), KEY, 100)
        encoded = json.dumps(span)
        for private in ("confidential-client", "private-role", "clusterA", "CONFIDENTIAL",
                        "SECRET", "PRIVATE", "Authorization", "token-123"):
            self.assertNotIn(private, encoded)
        attrs = {a["key"]: a["value"] for a in span["attributes"]}
        self.assertEqual(attrs["gilberto.prompt_tokens"], {"intValue": "123"})
        self.assertEqual(attrs["gilberto.estimated_input_tokens"], {"intValue": "456"})
        self.assertEqual(span["traceId"], correlation_id(KEY, "session:confidential-client"))
        self.assertEqual(len(span["spanId"]), 16)
        self.assertEqual(span["startTimeUnixNano"], span["endTimeUnixNano"])

    def test_unknown_enum_and_invalid_measurements_do_not_export_raw_values(self):
        span = metadata_span("s", self.event(type="SECRET", prompt_tokens=True,
                             estimated_input_tokens=float("nan")), KEY)
        self.assertEqual(span["name"], "gilberto.OTHER")
        self.assertNotIn("gilberto.prompt_tokens", str(span))
        self.assertNotIn("gilberto.estimated_input_tokens", str(span))

    def test_stable_ids_and_cross_session_isolation(self):
        a = metadata_span("a", self.event(), KEY, 100)
        b = metadata_span("a", self.event(), KEY, 200)
        c = metadata_span("b", self.event(), KEY, 100)
        self.assertEqual(a["traceId"], b["traceId"])
        self.assertEqual(a["spanId"], b["spanId"])
        self.assertNotEqual(a["traceId"], c["traceId"])

    def test_disabled_never_starts_worker_or_exports(self):
        telemetry = MetadataTelemetry(exporter=lambda _: self.fail("unexpected export"))
        self.assertFalse(telemetry.submit("s", self.event()))
        self.assertIsNone(telemetry._thread)
        self.assertFalse(from_environment({}).enabled)

    def test_failure_isolated_without_retry_and_success_retains_exact_safe_payload(self):
        called = threading.Event()
        payloads = []
        def exporter(payload):
            payloads.append(payload)
            called.set()
            raise RuntimeError("secret provider details")
        telemetry = MetadataTelemetry(enabled=True, secret=KEY, exporter=exporter)
        try:
            self.assertTrue(telemetry.submit("s", self.event()))
            self.assertTrue(called.wait(1))
            telemetry.pending.join()
            self.assertEqual(telemetry.failed, 1)
            self.assertEqual(len(payloads), 1)
            self.assertNotIn("CONFIDENTIAL", json.dumps(payloads))
            self.assertNotIn("secret provider", str(telemetry.status()))
        finally:
            telemetry.close()

    def test_slow_export_is_bounded_and_submit_does_not_wait_for_network(self):
        entered, release = threading.Event(), threading.Event()
        def exporter(_):
            entered.set()
            release.wait(2)
        telemetry = MetadataTelemetry(enabled=True, secret=KEY, capacity=1, exporter=exporter)
        try:
            self.assertTrue(telemetry.submit("s", self.event()))
            self.assertTrue(entered.wait(1))
            self.assertTrue(telemetry.submit("s", self.event(event_id=3)))
            self.assertFalse(telemetry.submit("s", self.event(event_id=4)))
            self.assertEqual(telemetry.dropped, 1)
            self.assertEqual(telemetry.pending.qsize(), 1)
        finally:
            telemetry.close()
            release.set()

    def test_sampling_zero_never_dispatches_and_invalid_event_is_dropped(self):
        zero = MetadataTelemetry(enabled=True, secret=KEY, sample_rate=0, exporter=lambda _: None)
        self.assertFalse(zero.submit("s", self.event()))
        self.assertIsNone(zero._thread)
        telemetry = MetadataTelemetry(enabled=True, secret=KEY, exporter=lambda _: None)
        self.assertFalse(telemetry.submit("s", self.event(event_id=-1)))
        self.assertEqual(telemetry.dropped, 1)

    def test_environment_requires_approved_host_tls_keys_and_valid_rate(self):
        env = {"GILBERTO_LANGFUSE_ENABLED": "true",
               "GILBERTO_LANGFUSE_OTLP_ENDPOINT": "https://example.test/api/public/otel/v1/traces",
               "GILBERTO_LANGFUSE_APPROVED_HOST": "example.test",
               "GILBERTO_TELEMETRY_CORRELATION_KEY": KEY,
               "LANGFUSE_PUBLIC_KEY": "test-public", "LANGFUSE_SECRET_KEY": "test-secret"}
        self.assertTrue(from_environment(env).enabled)
        for changes in ({"GILBERTO_LANGFUSE_APPROVED_HOST": "other.test"},
                        {"GILBERTO_LANGFUSE_OTLP_ENDPOINT": "http://example.test/api/public/otel/v1/traces"},
                        {"GILBERTO_LANGFUSE_OTLP_ENDPOINT": "https://example.test:invalid/api/public/otel/v1/traces"},
                        {"GILBERTO_TELEMETRY_SAMPLE_RATE": "nan"},
                        {"LANGFUSE_SECRET_KEY": ""}):
            self.assertFalse(from_environment({**env, **changes}).enabled)
