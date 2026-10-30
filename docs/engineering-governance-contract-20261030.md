# Engineering organization — governance contracts v1 (Brazilian law)

**Status:** proposed, isolated staging branch. There are **no live engineering-management autonomous agents** created by this change. Roles below are a verifiable responsibility model; they require authenticated job orchestration and actual named reviewers before operational use.

## Reporting and decision topology

Engineering Director (accountable owner of architecture and non-security managerial disputes)
- Engineering Audit Manager (independent assurance): Architecture Auditor; Code Quality & Testing Auditor; Security & Agent Authorization Auditor; Brazilian Legal Reliability Auditor; Repository & Licensing Auditor; Performance & Economics Auditor.
- DevOps & SRE Manager (independent operational readiness): CI/CD Engineer; Railway Infrastructure Engineer; Observability Engineer; Site Reliability Engineer; Release Engineering Specialist; FinOps Engineer.

An actual person/system identity must be authenticated before performing a decision. A supplied `sender` string is **not** proof of agent identity or authority; the library does not expose an HTTP endpoint.

## Manager-to-manager interface

`backend/governance/contracts.py` validates the typed event schema:
`event_id, timestamp, sender, recipient, task_or_pr, commit_sha, finding, evidence_reference, severity, required_action, owner, escalation_condition, status`.

The library stores only events actively passed to the ledger. An empty ledger means no manager exchange occurred. Append-only application semantics and an SHA-256 hash-chain detect partial modification; database administrators can rewrite a whole chain without external anchors, therefore this is **not cryptographic immutability**. Never put client documents, personal information, API keys, model prompts or legal case excerpts in these metadata records.

Mandatory handoff triggers, once orchestration is integrated: baseline and material architecture changes; security and legal findings; provider/infrastructure changes; database migrations; PR completion or failed CI; staging and production deployment; incidents and post-release review.

## Independent release-assessment gate

The `assess_release` helper requires A–G evidence flags for one exact SHA, two separate named reviewers for audit and DevOps attestations, and reviewers distinct from the implementation actor. It returns **READY_WITH_CONDITIONS**, never `READY`: external human authorization and post-release production Gate I remain separate. It does **not** validate the truth of attestation evidence: a production release controller must independently bind test artifacts and formal reviews to each record.

A legal-evidence audit does not certify operational readiness; a successful deployment does not certify legal accuracy. Neither manager may waive identity, confidentiality, licensing, source validity or legal-review blockers.

## Remaining integration / verification

- Authenticate machine/human review identities with server-managed roles and scoped audit logs before exposing events to users.
- Add a real event producer and independently verify that every handoff corresponds to an actual runtime, PR, check or incident.
- Store outside client-document retention paths, enforce tenant isolation, and anchor periodic hashes into separately permissioned storage.
- Map CI and Railway deployment evidence to gate records by immutable SHA, require explicit authorized human release.
- Test real staging replay, tamper detection, audit/operator independence, expiry/revocation, database recovery and rollback.
- Keep this proposed governance separate from production until an external reviewer verifies it.

## First action

Review this proposed foundational PR on staging. No claim is made that an Engineering Director, Audit Manager or DevOps Manager has run, communicated autonomously or approved the other PRs. Release gate evidence for the actual production release remains **incomplete**.
