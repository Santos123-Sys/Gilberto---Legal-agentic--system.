"""Read-only AG-UI projection of the authorized Gilberto event journal.

This is an event-wire subset, not a RunAgent HTTP implementation. The journal
remains authoritative and every projected record keeps its original cursor.
"""
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict


class CustomEvent(TypedDict):
    type: Literal["CUSTOM"]
    name: str
    value: dict[str, Any]
    metadata: dict[str, Any]


def _timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Existing engine timestamps were UTC-naive before this adapter.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    except (ValueError, OverflowError):
        return None


def project_event(event: dict, run_id: str | None = None) -> dict:
    """Project one persisted event without inventing missing state or evidence.

    Domain events are CUSTOM, including DEBATE_COMPLETE: that event still
    requires human review and must never be mislabeled RUN_FINISHED.
    """
    event_id = event.get("event_id")
    if type(event_id) is not int or event_id < 1:
        raise ValueError("A positive journal event_id is required")
    if not isinstance(event.get("session_id"), str) or not event["session_id"]:
        raise ValueError("A session_id is required")
    if not isinstance(event.get("type"), str) or not event["type"]:
        raise ValueError("An event type is required")
    metadata = {"gilbertoEventId": event_id, "threadId": event["session_id"],
                "runId": run_id or event.get("run_id") or event["session_id"]}
    for source, target in (("round", "round"), ("agent_id", "agentId"),
                           ("cluster", "clusterId"), ("revision", "revision")):
        if event.get(source) is not None:
            metadata[target] = deepcopy(event[source])
    result: dict = {"type": "CUSTOM", "name": "gilberto." + event["type"],
                    "value": deepcopy(event), "metadata": metadata}
    timestamp = _timestamp(event.get("timestamp"))
    if timestamp is not None:
        result["timestamp"] = timestamp
    # Project only backend-confirmed run lifecycle into native AG-UI 1.0 events.
    # Intermediate synthesis, gates and cancellation remain CUSTOM: none are
    # successful final legal acceptance. The existing journal is still canonical.
    if event["type"] == "RUN_STARTED":
        result = {"type": "RUN_STARTED", "threadId": event["session_id"],
                  "runId": metadata["runId"], "protocolVersion": "1.0",
                  "metadata": metadata}
    elif event["type"] == "FINAL_ACCEPTED":
        result = {"type": "RUN_FINISHED", "threadId": event["session_id"],
                  "runId": metadata["runId"], "metadata": metadata}
    elif event["type"] == "ERROR":
        # Never expose provider payloads, legal content or exception strings.
        result = {"type": "RUN_ERROR", "message": "Legal analysis failed; inspect authorized session status.",
                  "code": "GILBERTO_EXECUTION_ERROR", "metadata": metadata}
    elif event["type"] in ("CLUSTER_START", "CLUSTER_COMPLETE") and event.get("cluster"):
        result = {"type": "STEP_STARTED" if event["type"] == "CLUSTER_START" else "STEP_FINISHED",
                  "stepName": "cluster:" + str(event["cluster"]), "metadata": metadata}
    if timestamp is not None:
        result["timestamp"] = timestamp
    return result


def state_snapshot(session: dict) -> dict:
    """A snapshot watermark allows a client to ignore older state replay.

    Findings still come from the same journal, never from fabricated snapshot
    events. No owner identity, source document, credential or raw error is read.
    Send without an SSE id: the snapshot does not advance the journal cursor.
    """
    fields = ("id", "status", "execution_state", "control_version", "run_control",
              "current_round", "pending_gates", "created_at", "started_at", "last_checkpoint_at")
    state = {key: deepcopy(session[key]) for key in fields if key in session}
    state["event_cursor"] = len(session.get("events", []))
    return {"type": "STATE_SNAPSHOT", "snapshot": state,
            "metadata": {"threadId": session["id"],
                         "runId": session.get("run_id", session["id"]),
                         "journalWatermark": state["event_cursor"]}}


def stream_end(session: dict) -> dict:
    """End the transport, not a fictitious successful legal execution."""
    return {"type": "CUSTOM", "name": "gilberto.STREAM_END",
            "value": {"status": session["status"]},
            "metadata": {"threadId": session["id"],
                         "journalWatermark": len(session.get("events", []))}}
