"""AG-UI 1.0 read-only lifecycle projection and authorization regression checks."""
import unittest
from workspace_events import project_event


class AguiLifecycleContractTests(unittest.TestCase):
    def event(self, kind, eid=1, **extra):
        return {"event_id": eid, "session_id": "synthetic-id", "run_id": "synthetic-id",
                "type": kind, "timestamp": "2026-10-30T08:00:00Z", **extra}

    def test_confirmed_start_and_final_human_acceptance_are_native(self):
        started = project_event(self.event("RUN_STARTED"))
        self.assertEqual(started["type"], "RUN_STARTED")
        self.assertEqual(started["protocolVersion"], "1.0")
        self.assertEqual(started["threadId"], "synthetic-id")
        self.assertEqual(started["runId"], "synthetic-id")
        accepted = project_event(self.event("FINAL_ACCEPTED", eid=2))
        self.assertEqual(accepted["type"], "RUN_FINISHED")
        self.assertEqual(accepted["metadata"]["gilbertoEventId"], 2)
        self.assertNotIn("result", accepted)

    def test_intermediate_analysis_and_stopped_run_never_finish_as_success(self):
        for kind in ("DEBATE_COMPLETE", "ROUND_COMPLETE", "CANCELLED", "GATE_TRIGGERED"):
            self.assertEqual(project_event(self.event(kind))["type"], "CUSTOM")
        failure = project_event(self.event("ERROR", error="PRIVATE LEGAL FILE"))
        self.assertEqual(failure["type"], "RUN_ERROR")
        self.assertNotIn("PRIVATE LEGAL FILE", str(failure))

    def test_cluster_step_boundaries_and_cursor_determinism(self):
        start = project_event(self.event("CLUSTER_START", cluster="foundation"))
        finish = project_event(self.event("CLUSTER_COMPLETE", eid=2, cluster="foundation"))
        self.assertEqual(start["type"], "STEP_STARTED")
        self.assertEqual(finish["type"], "STEP_FINISHED")
        self.assertEqual(start["stepName"], finish["stepName"])
        self.assertEqual(project_event(self.event("CLUSTER_START", cluster="foundation")), start)
