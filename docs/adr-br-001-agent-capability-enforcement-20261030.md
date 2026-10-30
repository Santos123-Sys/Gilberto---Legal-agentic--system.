# ADR-BR-001 — Authorize model dispatch by server-defined agent contract

Date: 2026-10-30. Status: **proposed, staging-review only**. Jurisdiction: Brazil.

## Verified baseline and ownership

Baseline staging SHA: `84ff834c3c04d3b1c359d4e5cbba3b2a640919f1`; production SHA: `3e1c85f376635d2b39d5fbd71b61443430ff816a`. Source paths inspected: `backend/engines/debate_engine_v3.py`, `backend/agents/cluster_definitions.py`, `backend/security/authorization.py`, `backend/legal/{claims,authority,evidence,assurance}.py`, and `backend/benchmarks/`.

The existing backend authenticates and scopes sessions, and the API restricts jurisdiction to BR. Contract text verification explicitly does **not** authenticate jurisprudence or confirm legal validity. Before this change, `_run_agent` applied pacing, cost and concurrency limits but no roster-backed per-agent authorization check at the actual model-dispatch boundary. No autonomous external research or filing tool registry was identified in this inspected code path.

The **Engineering Audit Manager** function owns independent security, architecture, legal-evidence and testing review. The **DevOps Manager** function independently owns staging CI, operational readiness, secrets, rollback and deployment-SHA verification. These are review responsibilities; this ADR does not claim that persistent manager agents have been deployed. An implementing engineer must not self-certify the PR.

## Options and trade-offs

| Option | Gain | Sacrifice / risk | Decision |
|---|---|---|---|
| A. Keep prompt-only restrictions | No new code, minimum latency | Not enforceable against unauthorized runtime actions | Rejected |
| B. In-process, explicit roster-derived capability check at model dispatch | Denies unauthorized dispatch before billing, low integration complexity, auditable decisions, reversible | Does not enforce future tools unless each adapter calls the policy; role configurations remain in same trust domain | **Implement for a bounded pilot** |
| C. Dedicated external authorization service | Better cross-service controls and central policy management | Additional network dependency, operational expenditure, latency and migration burden | Defer until evidence justifies |

Mandatory legal, confidentiality and identity controls are hard gates; weighted scoring would be false precision without measured workloads. Change is reversible by reverting the two integration callsites and retaining the policy tests as specifications.

## Capability contract

- Only canonical Brazilian specialist, manager, adversarial, orchestrator, focused and deterministically generated feedback roles can use the existing `model_completion` action in their permitted cluster.
- A model's assertion that it has tools or permissions is ignored.
- Unknown roles, cluster impersonation, unlisted actions and non-Brazilian jurisdiction are denied.
- Official-authority retrieval reports **UNAVAILABLE** until a separately authorized adapter is deployed.
- Certification of authority, legal interpretation and final publication report **ESCALATE**. This *does not* itself implement the full human signoff workflow.
- Explicit consent for a backup model is required at the same dispatch boundary, in addition to existing API checks; consent does not bypass the host allowlist, budget or evidence policy.
- Denied dispatch generates minimal structured telemetry and does not make a provider request.
- This control is **not** a claim of legal accuracy or independently verified statutory/case-law retrieval.

## Acceptance and independent verification

1. Reviewers reproduce policy unit tests and async integration tests.
2. CI backend/frontend suites pass on the actual PR head.
3. Negative tests cover unknown roles, cross-cluster impersonation, forged goals, unlisted actions, missing backup consent, foreign jurisdiction and round-bound feedback identities.
4. Inspect the final `_run_agent` call graph: every model request must pass the policy after the pause barrier and before quota reservation.
5. Validate identity isolation, staging real accounts, provider-host allowlist and encrypted restore separately before releasing PR #72.
6. Human Brazilian-law reviewer validates legal interpretations and ground-truth benchmark cases; no synthetic result can substitute.

## Residual risks / reversal triggers

The legacy engine module, any future retrieval adapter or code path that calls a model client directly can bypass this in-process check. A future PR must implement a centralized model/tool invocation gateway, explicit scope-specific evidence requirements, logged policy version, and coverage tests over all public entrypoints. This change deliberately does not claim complete authorization coverage. Reevaluate centralized policy if the platform acquires multiple services capable of making consequential calls.

**Merge target:** `release/brlaw-security-staging-20261029`, not production `main`. Do not merge or deploy unless required gates are independently verified.
