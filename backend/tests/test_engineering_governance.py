"""Governance is a fail-closed review library, not fabricated agent staff."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4

from governance.contracts import (
    AUDIT_MANAGER, DEVOPS_MANAGER, ENGINEERING_DIRECTOR, ManagerEvent,
    ManagerEventLedger, assess_release, validate_event,
)

SHA = "f" * 40
GATES = dict.fromkeys("ABCDEFG", True)


def event():
    return ManagerEvent(
        event_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        sender=AUDIT_MANAGER,
        recipient=DEVOPS_MANAGER,
        task_or_pr="PR-85",
        commit_sha=SHA,
        finding="A denied tool call did not reach the model",
        evidence_reference="CI run and test method reference only",
        severity="HIGH",
        required_action="Inspect and attest exact SHA",
        owner="security_review",
        escalation_condition="Permission bypass or missing evidence",
        status="OPEN",
    )


class GovernanceContractTests(unittest.TestCase):
    def test_required_roles_and_handoff_fields(self):
        self.assertTrue(validate_event(event()))
        with self.assertRaises(ValueError):
            validate_event(replace(event(), recipient=AUDIT_MANAGER))
        with self.assertRaises(ValueError):
            validate_event(replace(event(), evidence_reference=""))
        with self.assertRaises(ValueError):
            validate_event(replace(event(), commit_sha="main"))
        with self.assertRaises(ValueError):
            validate_event(replace(event(), sender="unregistered_agent"))

    def test_append_only_chain_and_detect_content_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.sqlite"
            store = ManagerEventLedger(path)
            first, second = event(), event()
            head1 = store.append(first)
            head2 = store.append(second)
            self.assertNotEqual(head1["event_hash"], head2["event_hash"])
            self.assertEqual(store.verify()["events"], 2)
            with self.assertRaises(sqlite3.IntegrityError):
                store.append(first)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE manager_events SET payload='tampered' WHERE seq=1")
            with self.assertRaisesRegex(ValueError, "Tampered governance ledger"):
                store.verify()
            with self.assertRaisesRegex(ValueError, "Tampered governance ledger"):
                store.append(event())

    def test_no_release_without_two_independent_assessments(self):
        a = {AUDIT_MANAGER: {"sha": SHA, "passed": True, "reviewer_id": "auditor"},
             DEVOPS_MANAGER: {"sha": SHA, "passed": True, "reviewer_id": "operator"}}
        ok = assess_release(GATES, a, "implementer", SHA)
        self.assertEqual(ok["status"], "READY_WITH_CONDITIONS")
        self.assertIn("human_approval", ok["reason"])
        cases = [
            (dict(GATES, C=False), a, "implementer"),
            (dict(GATES, H=True), a, "implementer"),
            (GATES, {AUDIT_MANAGER: a[AUDIT_MANAGER]}, "implementer"),
            (GATES, a, "auditor"),
            (GATES, {**a, DEVOPS_MANAGER: {**a[DEVOPS_MANAGER], "reviewer_id": "auditor"}},
             "implementer"),
            (GATES, {**a, DEVOPS_MANAGER: {**a[DEVOPS_MANAGER], "sha": "a" * 40}},
             "implementer"),
        ]
        for gates, signoffs, author in cases:
            with self.subTest(gates=gates, author=author):
                self.assertEqual(assess_release(gates, signoffs, author, SHA)["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
