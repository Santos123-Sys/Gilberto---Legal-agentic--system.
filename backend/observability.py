"""Optional metadata-only OTLP/HTTP export to an approved Langfuse instance.

No SDK auto-instrumentation: prompts, documents, outputs, tool arguments, user
identities and errors never enter the export payload. Legal execution never
waits for network I/O. No retries after ambiguous export results; the journal
remains the durable audit record. This adapter is best-effort operational data.
"""
import base64
import hashlib
import hmac
import json
import math
import os
import queue
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

EVENT_TYPES = frozenset((
    "DEBATE_START", "ROUND_START", "CLUSTER_START", "PHASE_START",
    "AGENT_THINKING", "AGENT_ANALYSIS_COMPLETE", "AGENT_VOTE_CAST",
    "CLUSTER_COMPLETE", "CLUSTER_MANAGER_START", "CLUSTER_MANAGER_COMPLETE",
    "DEVILS_ADVOCATE_START", "DEVILS_ADVOCATE_COMPLETE", "MASTER_MANAGER_START",
    "MASTER_MANAGER_COMPLETE", "ROUND_COMPLETE", "DEBATE_COMPLETE",
    "GATE_TRIGGERED", "GATE_RESOLVED", "ALL_GATES_RESOLVED", "PROVIDER_WAIT",
    "FEEDBACK_RECEIVED", "FEEDBACK_ROUTING_START", "ERROR", "CANCELLED",
    "RUN_PAUSE_REQUESTED", "RUN_PAUSED", "RUN_RESUMED", "CANCEL_REQUESTED", "RUN_STOPPING",
    "RUN_PREPARING", "RUN_STARTED", "FINAL_ACCEPTED", "HUMAN_VOTE_RECORDED", "RUN_RESUMING",
))
NUMERIC_FIELDS = frozenset(("event_id", "round", "latency_ms", "wait_seconds",
                            "execution_ms", "queue_wait_ms", "model_calls",
                            "estimated_input_tokens", "prompt_tokens",
                            "completion_tokens", "reported_calls", "unreported_calls"))


def correlation_id(secret: str, value: str, length: int = 32) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()[:length]


def metadata_span(session_id: str, event: dict, secret: str, now_ns=None) -> dict:
    """Allowlist only numeric measurements/enums; pseudonymize all identities."""
    if len(secret) < 32:
        raise ValueError("Telemetry correlation secret must contain at least 32 characters")
    event_id = event.get("event_id")
    if type(event_id) is not int or event_id < 1:
        raise ValueError("Telemetry requires an authoritative event id")
    kind = event.get("type")
    kind = kind if kind in EVENT_TYPES else "OTHER"
    trace_id = correlation_id(secret, "session:" + session_id)
    attrs = {"langfuse.session.id": trace_id, "gilberto.event_type": kind,
             "gilberto.measurement": "journal_event_not_provider_span"}
    for key in NUMERIC_FIELDS:
        value = event.get(key)
        if type(value) in (int, float) and math.isfinite(value) and 0 <= value < 2**53:
            attrs["gilberto." + key] = value
    for key in ("agent_id", "cluster", "run_id"):
        if isinstance(event.get(key), str):
            attrs["gilberto." + key] = correlation_id(secret, key + ":" + event[key])
    # Use the actual journal timestamp, never the exporter dispatch time, when
    # the event supplies a valid timestamp; measured durations are not inferred.
    if now_ns is None:
        try:
            recorded = datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
            if recorded.tzinfo is None:
                recorded = recorded.replace(tzinfo=timezone.utc)
            now_ns = int(recorded.timestamp() * 1_000_000_000)
        except (KeyError, TypeError, ValueError, OverflowError):
            now_ns = time.time_ns()
    stamp = str(now_ns)
    attributes = []
    for key, value in attrs.items():
        encoded = ({"intValue": str(value)} if type(value) is int else
                   {"doubleValue": value} if type(value) is float else {"stringValue": value})
        attributes.append({"key": key, "value": encoded})
    return {"traceId": trace_id,
            "spanId": correlation_id(secret, f"{session_id}:event:{event_id}", 16),
            "name": "gilberto." + kind, "kind": 1,
            "startTimeUnixNano": stamp, "endTimeUnixNano": stamp,
            "attributes": attributes,
            "status": {"code": 2 if kind == "ERROR" else 0}}


def _otlp_payload(span):
    return {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name",
                                    "value": {"stringValue": "gilberto"}}]},
        "scopeSpans": [{"scope": {"name": "gilberto.metadata", "version": "1"},
                        "spans": [span]}]}]}


class MetadataTelemetry:
    """Bounded one-worker exporter; construction does not send or start threads."""
    def __init__(self, *, enabled=False, secret="", sample_rate=1.0,
                 capacity=128, exporter=None):
        if not 0 <= sample_rate <= 1 or not 1 <= capacity <= 1024:
            raise ValueError("Invalid telemetry sampling or capacity")
        self.enabled = bool(enabled and len(secret) >= 32 and exporter is not None)
        self.secret = secret
        self.sample_rate = sample_rate
        self.exporter = exporter
        self.pending = queue.Queue(maxsize=capacity)
        self.dropped = self.exported = self.failed = 0
        self._stop = threading.Event()
        self._start_lock = threading.Lock()
        self._thread = None

    def submit(self, session_id: str, event: dict) -> bool:
        if not self.enabled or self._stop.is_set():
            return False
        try:
            fraction = int(correlation_id(self.secret, "sample:" + session_id, 8), 16) / 2**32
            if fraction >= self.sample_rate:
                return False
            span = metadata_span(session_id, event, self.secret)
            self.pending.put_nowait(span)
            with self._start_lock:
                if self._thread is None:
                    self._thread = threading.Thread(target=self._work, daemon=True,
                                                    name="gilberto-metadata-export")
                    self._thread.start()
            return True
        except Exception:
            self.dropped += 1
            return False

    def _work(self):
        while not self._stop.is_set():
            try:
                span = self.pending.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.exporter(_otlp_payload(span))
                self.exported += 1
            except Exception:
                # No exception strings, headers or response bodies in logs.
                self.failed += 1
            finally:
                self.pending.task_done()

    def probe(self):
        """Explicit administrator diagnostic: synthetic metadata only.

        A successful OTLP response means ingestion accepted the request;
        it does not verify retention, queryability or production traces.
        """
        if not self.enabled or self._stop.is_set():
            return {"configured": False, "ingestion_accepted": False}
        import secrets
        synthetic = "gilberto-probe:" + secrets.token_hex(16)
        try:
            span = metadata_span(synthetic, {"type": "ROUND_START", "event_id": 1},
                                 self.secret)
            self.exporter(_otlp_payload(span))
            return {"configured": True, "ingestion_accepted": True,
                    "verification_scope": "synthetic_otlp_ingestion_only"}
        except Exception:
            # Suppress all remote error bodies, headers and accidental PII.
            return {"configured": True, "ingestion_accepted": False,
                    "verification_scope": "synthetic_otlp_ingestion_only"}

    def close(self):
        self._stop.set()
        self.enabled = False
        # Never make application shutdown depend on the exporter.
        while True:
            try:
                self.pending.get_nowait()
                self.pending.task_done()
                self.dropped += 1
            except queue.Empty:
                break

    def status(self):
        return {"enabled": self.enabled, "queued": self.pending.qsize(),
                "exported": self.exported, "failed": self.failed, "dropped": self.dropped,
                "content_policy": "metadata_only", "delivery": "best_effort_no_retry"}


def from_environment(env=None):
    """Opt-in requires an exact HTTPS endpoint and approved hostname.

    Retention/deletion policy is enforced at the selected external instance and
    must be verified before activation. This module retains no local exports.
    """
    env = os.environ if env is None else env
    if env.get("GILBERTO_LANGFUSE_ENABLED", "false").lower() != "true":
        return MetadataTelemetry()
    endpoint = env.get("GILBERTO_LANGFUSE_OTLP_ENDPOINT", "")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return MetadataTelemetry()
    allowed = env.get("GILBERTO_LANGFUSE_APPROVED_HOST", "")
    secret = env.get("GILBERTO_TELEMETRY_CORRELATION_KEY", "")
    public = env.get("LANGFUSE_PUBLIC_KEY", "")
    private = env.get("LANGFUSE_SECRET_KEY", "")
    if (parsed.scheme != "https" or not allowed or parsed.hostname != allowed
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/api/public/otel/v1/traces" or port not in (None, 443)
            or len(secret) < 32 or not public or not private):
        return MetadataTelemetry()
    try:
        sample_rate = float(env.get("GILBERTO_TELEMETRY_SAMPLE_RATE", "0.1"))
        if not math.isfinite(sample_rate) or not 0 <= sample_rate <= 1:
            return MetadataTelemetry()
    except ValueError:
        return MetadataTelemetry()
    auth = base64.b64encode(f"{public}:{private}".encode()).decode()

    def export(payload):
        import httpx  # Existing application dependency; imported only on export.
        # Disable redirects and environment proxies: credentials cannot be
        # forwarded to another host by an exporter response or proxy setting.
        with httpx.Client(timeout=2.0, follow_redirects=False, trust_env=False) as client:
            with client.stream("POST", endpoint, json=payload, headers={
                    "Authorization": "Basic " + auth,
                    "Content-Type": "application/json",
                    "x-langfuse-ingestion-version": "4"}) as response:
                response.raise_for_status()
                # Read at most 64 KiB and reject partial-success responses.
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 65536:
                        raise ValueError("Telemetry response exceeds limit")
                reply = json.loads(data or b"{}")
                if reply.get("partialSuccess", {}).get("rejectedSpans", 0) not in (0, "0"):
                    raise ValueError("Telemetry partially rejected")
    return MetadataTelemetry(enabled=True, secret=secret,
                             sample_rate=sample_rate, exporter=export)
