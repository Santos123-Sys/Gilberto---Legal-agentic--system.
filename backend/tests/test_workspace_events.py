import unittest
from workspace_events import project_event, state_snapshot, stream_end


class WorkspaceEventTests(unittest.TestCase):
    def event(self, number=1, **changes):
        return {"event_id": number, "session_id": "owner-session",
                "type": "AGENT_ANALYSIS_COMPLETE", "round": 2,
                "agent_id": "foundation.document", "cluster": "foundation",
                "timestamp": "2026-10-29T12:00:00+00:00",
                "parsed": {"findings": ["unverified"]}, **changes}

    def test_projection_preserves_cursor_round_identity_and_domain_payload(self):
        event = self.event()
        projected = project_event(event)
        self.assertEqual(projected["type"], "CUSTOM")
        self.assertEqual(projected["name"], "gilberto.AGENT_ANALYSIS_COMPLETE")
        self.assertEqual(projected["metadata"]["gilbertoEventId"], 1)
        self.assertEqual(projected["metadata"]["round"], 2)
        self.assertEqual(projected["metadata"]["agentId"], "foundation.document")
        self.assertEqual(projected["timestamp"], 1793275200000)
        self.assertEqual(projected["value"], event)
        projected["value"]["parsed"]["findings"].append("changed")
        self.assertEqual(event["parsed"]["findings"], ["unverified"])

    def test_replay_is_deterministic_and_uses_same_stable_event_identity(self):
        records = [self.event(n) for n in range(1, 6)]
        first = [project_event(e) for e in records]
        replay = [project_event(e) for e in records[2:]]
        self.assertEqual(first[2:], replay)
        self.assertEqual([e["metadata"]["gilbertoEventId"] for e in first], [1, 2, 3, 4, 5])

    def test_feedback_and_stop_are_not_successful_legal_acceptance(self):
        for kind in ("DEBATE_COMPLETE", "CANCELLED", "GATE_TRIGGERED"):
            self.assertEqual(project_event(self.event(type=kind))["type"], "CUSTOM")

    def test_invalid_events_are_rejected_without_invented_identity(self):
        for changes in ({"event_id": 0}, {"event_id": True}, {"session_id": ""}, {"type": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                project_event(self.event(**changes))

    def test_invalid_timestamp_is_omitted_not_replaced_with_now(self):
        self.assertNotIn("timestamp", project_event(self.event(timestamp="invalid")))

    def test_snapshot_has_watermark_and_no_document_or_owner(self):
        session = {"id": "owner-session", "status": "awaiting_gate",
                   "document_text": "PRIVATE", "owner": "private@example.test",
                   "pending_gates": ["gate1"], "events": [self.event()]}
        projected = state_snapshot(session)
        self.assertEqual(projected["metadata"]["journalWatermark"], 1)
        self.assertEqual(projected["snapshot"]["pending_gates"], ["gate1"])
        self.assertNotIn("PRIVATE", str(projected))
        self.assertNotIn("private@example", str(projected))
        projected["snapshot"]["pending_gates"].clear()
        self.assertEqual(session["pending_gates"], ["gate1"])
        self.assertEqual(stream_end(session)["name"], "gilberto.STREAM_END")
