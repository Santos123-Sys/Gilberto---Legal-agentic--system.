"""Independent audit/DevOps governance primitives (not self-executing agents).

All records are explicitly human/system-provided facts; nothing fabricates
agent conversations, test evidence, or approval. A hash-chain detects incidental
or partial tampering; separate storage access controls/anchors are required to
resist an attacker with database write privileges.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from uuid import UUID


ENGINEERING_DIRECTOR = "engineering_director"
AUDIT_MANAGER = "engineering_audit_manager"
DEVOPS_MANAGER = "devops_sre_manager"

SPECIALISTS = {
    AUDIT_MANAGER: (
        "architecture", "code_testing", "security_authorization",
        "brazilian_legal_reliability", "repository_licensing",
        "performance_economics",
    ),
    DEVOPS_MANAGER: (
        "cicd", "railway_infrastructure", "observability", "site_reliability",
        "release_engineering", "finops",
    ),
}
REQUIRED_GATES = frozenset("ABCDEFG")
_VALID_SEVERITIES = frozenset({"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"})
_VALID_STATUSES = frozenset({"OPEN", "ACKNOWLEDGED", "BLOCKED", "RESOLVED"})
_GENESIS = "0" * 64


@dataclass(frozen=True)
class ManagerEvent:
    event_id: str
    timestamp: str
    sender: str
    recipient: str
    task_or_pr: str
    commit_sha: str
    finding: str
    evidence_reference: str
    severity: str
    required_action: str
    owner: str
    escalation_condition: str
    status: str

    def as_payload(self):
        from dataclasses import asdict
        return asdict(self)


def validate_event(event):
    """Check event contract; *not* an authentication or evidence-truth check."""
    if not isinstance(event, ManagerEvent):
        raise ValueError("Governance message requires explicit typed event")
    try:
        parsed = UUID(event.event_id)
        stamp = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ValueError("Invalid governance event identifier or timestamp") from None
    if parsed.version not in (4, 7) or stamp.tzinfo is None:
        raise ValueError("Event ID must be a random/time-sortable UUID and time offset-aware")
    if stamp.astimezone(timezone.utc).utcoffset() is None:
        raise ValueError("Timestamp must specify UTC offset")
    roles = {ENGINEERING_DIRECTOR, AUDIT_MANAGER, DEVOPS_MANAGER}
    if event.sender not in roles or event.recipient not in roles or event.sender == event.recipient:
        raise ValueError("Unknown or self-addressed manager handoff")
    if event.severity not in _VALID_SEVERITIES or event.status not in _VALID_STATUSES:
        raise ValueError("Invalid event severity or status")
    for field in ("task_or_pr", "finding", "evidence_reference",
                  "required_action", "owner", "escalation_condition"):
        val = getattr(event, field)
        if not isinstance(val, str) or not val.strip() or len(val) > 2000:
            raise ValueError("Governance event missing bounded " + field)
    if (not isinstance(event.commit_sha, str)
            or len(event.commit_sha) != 40
            or any(c not in "0123456789abcdef" for c in event.commit_sha)):
        raise ValueError("Governance event needs immutable lower-case 40-digit SHA")
    return True


class ManagerEventLedger:
    """SQLite append-only API for explicitly evidenced handoff messages.

    No event-writing HTTP endpoint: the caller must authenticate/authorize the
    actual sender before using this internal helper.
    """

    def __init__(self, path):
        self.path = str(path)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS manager_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL)""")

    def _db(self):
        db = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        db.execute("PRAGMA busy_timeout=5000")
        return db

    @staticmethod
    def _digest(previous, payload):
        return sha256((previous + "\n" + payload).encode("utf-8")).hexdigest()

    @classmethod
    def _assert_chain(cls, rows):
        previous = _GENESIS
        for seq, payload, prev, digest in rows:
            if prev != previous or cls._digest(previous, payload) != digest:
                raise ValueError("Tampered governance ledger; refuse new handoffs")
            previous = digest
        return previous

    def append(self, event):
        validate_event(event)
        payload = json.dumps(event.as_payload(), sort_keys=True, separators=(",", ":"))
        db = self._db()
        try:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute(
                "SELECT seq,payload,previous_hash,event_hash FROM manager_events ORDER BY seq"
            ).fetchall()
            previous = self._assert_chain(rows)
            digest = self._digest(previous, payload)
            db.execute("INSERT INTO manager_events (event_id,payload,previous_hash,event_hash)"
                       " VALUES (?,?,?,?)", (event.event_id, payload, previous, digest))
            db.execute("COMMIT")
            return {"sequence": len(rows) + 1, "event_hash": digest}
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def verify(self):
        with self._db() as db:
            rows = db.execute(
                "SELECT seq,payload,previous_hash,event_hash FROM manager_events ORDER BY seq"
            ).fetchall()
        return {"events": len(rows), "chain_head": self._assert_chain(rows)}


def assess_release(gates, attestations, implementing_actor, proposed_sha):
    """Never mistake recorded opinions for independently tested evidence.

    A READY recommendation requires positive A–G gate data and independent
    attestations from both managers. Production deployment still needs human
    approval and separate post-deployment Gate I validation.
    """
    if not isinstance(gates, dict) or not isinstance(attestations, dict):
        return {"status": "BLOCKED", "reason": "missing_release_evidence"}
    if (len(proposed_sha) != 40 or any(c not in "0123456789abcdef" for c in proposed_sha)):
        return {"status": "BLOCKED", "reason": "invalid_release_sha"}
    if set(gates) != REQUIRED_GATES or not all(gates.values()) or not all(
            gates.get(k) is True for k in REQUIRED_GATES):
        return {"status": "BLOCKED", "reason": "mandatory_release_gate_unverified"}
    reviewers = []
    for manager in (AUDIT_MANAGER, DEVOPS_MANAGER):
        assessment = attestations.get(manager)
        if not isinstance(assessment, dict) or assessment.get("sha") != proposed_sha:
            return {"status": "BLOCKED", "reason": "manager_assessment_missing_or_stale"}
        if assessment.get("passed") is not True:
            return {"status": "BLOCKED", "reason": "manager_assessment_not_approved"}
        reviewer = assessment.get("reviewer_id")
        if not isinstance(reviewer, str) or not reviewer.strip():
            return {"status": "BLOCKED", "reason": "reviewer_identity_missing"}
        reviewers.append(reviewer)
    if implementing_actor in reviewers or len(set(reviewers)) != 2:
        return {"status": "BLOCKED", "reason": "review_independence_conflict"}
    return {
        "status": "READY_WITH_CONDITIONS",
        "reason": "requires_explicit_human_approval_and_post_deployment_gate_I",
        "proposed_sha": proposed_sha,
    }
