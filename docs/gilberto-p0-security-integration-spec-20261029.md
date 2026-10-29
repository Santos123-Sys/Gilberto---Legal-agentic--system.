# Gilberto — P0 integration specification (source-verified)

**Date:** 29 October 2026. **Base:** `18f61dae499c6d07e72e3bbc8084beb91e26b533`. **Tracking:** [issue #38](https://github.com/Santos123-Sys/Gilberto---Legal-agentic--system./issues/38). **Classification:** design specification; not deployed capability.

## Existing architecture and hazards

- `backend/main.py`: `_get_session` uses only the session UUID, with in-process `sessions` dict and `session_store.load` fallback. No server-owned principal. `create_session` serializes client-provided `user_id` into config. Gate API accepts client-provided `human_review_id`.
- `backend/session_store.py`: one `sessions(id, payload JSON)` SQLite table, WAL mode, mounted to Railway persistent volume `/data`, with event and document-text snapshots.
- Browser `useAgenticSession.js`: direct unauthenticated `fetch`; `EventSource` on API's separate domain. Browser localStorage keeps a session ID, not an authenticated authorization context.
- Railway production: backend + frontend share GitHub `main`; one 500 MB volume for backend, no Railway object-storage bucket in this project. Identity provider variables absent as of the audit.
- Engine: `asyncio.create_task` + provider `asyncio.to_thread`. Cancelling the asyncio task **does not necessarily terminate** an already-running blocking provider request.

## Target security boundaries

1. Managed OIDC provider via Authorization Code + PKCE; prefer same-origin BFF so browser holds only `Secure; HttpOnly; SameSite=Lax` opaque session cookie. Server stores encrypted short-lived access/session state; implement logout, revocation, expiry, login transaction `state` and PKCE verifier. Never pass ID tokens, JWTs, or API keys in SSE query strings, web logs or localStorage. If a separate-origin browser token design is approved, use an authenticated fetch streaming client, not native EventSource lacking header support.
2. Resource-server access tokens: verify trusted issuer, API-specific audience, signature+alg allowlist, expiry, key rotation, scope, user `(iss,sub)`; no identity derived from request body or `human_review_id`. `PyJWKClient` and the JWT primitive in PR #39 are only building blocks; they **do not** create a browser login.
3. Authorization: explicit owner `(owner_issuer, owner_subject)` bound at session creation from verified identity. For shared organizations, use a server-backed membership table with explicit per-operation grants (view, run, approve, administer) and immediate revocation checks. No implicit tenant from `user_id`, document metadata, or token's untrusted role names.
4. Database: transactional `session_ownership(session_id PRIMARY KEY REFERENCES sessions(id), owner_issuer NOT NULL, owner_subject NOT NULL, org_id NULL, created_at, policy_version)`; separate `session_grants` with scoped permission, expiry and revocation. Use SQLite initially only with a single worker and a secure DB transaction; plan Postgres+RLS or database-per-tenant after measured concurrent tenancy. Authz must be rechecked at read/write time, not inferred from a cached in-memory session object. Foreign keys enforced; schema migration is additive and versioned.
5. Legacy migration: back up and verify first; sessions lacking an attributable owner are quarantined and inaccessible to normal users. Only an audited administrator with independently verified supporting records can map legacy sessions to principals. Never let UUID possession register ownership, never autoassign old sessions, and never destroy existing document checkpoints during migration.
6. SSE: enforce authentication *before streaming begins*, authorize the exact session, close/revalidate after principal revocation or expiry, use safe opaque cursors without credentials. Reconnection and tab restore must re-authorize; server event history may contain confidential material.
7. Authorization middleware must cover **all** routes below and future file/export endpoints. Public `/api/health` should expose only minimal status. Readiness `/api/ready` may be internal-only. On 401 return a generic challenge; on non-owner prefer indistinguishable 404. Never disclose resource existence to another tenant.
8. Operation principal must be logged using an audit actor ID derived from verified identity. If user enters an optional reviewer name, retain it only as display metadata, not as authorization or independent audit identity.

## Endpoint contract and negative cases

| Route | Minimal role | Required checks |
|---|---|---|
| POST /api/sessions | authenticated reviewer | identity issuer/sub and org membership verified; ignore/reject client user_id |
| POST /api/sessions/{id}/start | owner or run delegate | membership, current status, budget and upload limits |
| GET /api/sessions/{id}/stream | view permission | authenticate before subscription, expiry/revocation and all event frames |
| GET /api/sessions/{id}/status | view permission | owner/tenant and no cross-user metadata leaks |
| GET /api/sessions/{id}/results | view permission | no document, citations or analyst notes exposed cross-user |
| GET /api/sessions/{id}/gates | reviewer permitted | sensitive reviewer/decision trace protected |
| POST /api/sessions/{id}/gate-decision | approve permission | approver identity, exact pending gate ID, idempotency, non-expired authorization |
| POST /api/sessions/{id}/feedback | run permission | stable session owner + active worker constraints |
| POST /api/sessions/{id}/accept | approve permission | completed runs, no pending gates, exact review version |
| POST /api/sessions/{id}/cancel (future) | run permission | atomic cancellation intent, bound run ID, no new tool dispatch |
| GET /api/health | public-minimal or internal | no internal environment details or secrets |

## Cancellation and approval contracts

**Execution state:** created → running ↔ awaiting_gate → awaiting_feedback → completed; cancellation_requested → cancelled; failures → failed. Persist `run_id`, `state`, `version`, `requested_by`, `cancel_requested_at`, `last_heartbeat`. Compare-and-swap (CAS) state transitions in DB. Workers consult cancellation before every model/tool dispatch, after responses, and before mutable side effects. Document unavoidable in-flight provider costs and already committed actions. If task restart is detected, do not present it as successfully cancelled or automatically replay irreversible tools.

**Action policy:** before side effects, record `action_id, agent_id, resource_id, tenant_id, payload_hash, risk_class, approval_id, requested_by, expires_at, state`; approval references exact normalized payload hash and version, can be revoked, expires and is consumed atomically. For external filing, disclosure, deletion or financial commitment, fail closed without an approved and still-authorized approver. After the action, record actual outcome and any needed compensating task. The current human risk gates are *analysis review*, not a universal side-effect authorization layer.

## Backup and restore dependency

`backend/recovery.py` in PR #41 demonstrates how to make and validate consistent SQLite snapshots offline. A complete recovery release requires encrypted off-project backups, independent key management, tested daily/weekly schedules and retention, an isolated restore to a nonproduction service, a tenant-permission parity test, and recorded measured RPO/RTO. Proposed targets (24h RPO, 4h RTO) need business approval and cannot be claimed from a snapshot-check pass.

Railway's documented built-in volume backups restore within the same project and environment. They are not independent off-project disaster recovery. Never replace or remove production volumes as a test. Ask for approved off-project destination and recovery-drill window before scheduling.

## Explicit integration and production release sequence

1. Confirm IdP and tenant isolation model; create staging environment and separate test identity accounts, storage, and provider quotas. Never use actual client documents as canaries.
2. Back up old checkpoint volume and exercise an isolated restore before migration. Assert rollback compatibility and versioned schema.
3. Integrate PR #39 verifier with BFF/OIDC, browser auth and authenticated SSE. Keep the attack tests in PR #40 as explicit expected failures until fixed; then remove decorators and require all pass. Require two separate principals and cross-tenant negative tests, including SSE and reviewer impersonation.
4. Enable backend policy enforcement *before* exposing new cancel and approval endpoints. No feature flag may disable authorization in production. Demonstrate expiry, revocation, session termination, replay and TOCTOU scenarios.
5. Add durable execution/audit ledger with structured redaction and no secret/document contents in operational logs.
6. Legal claims verified against authoritative sources and labeled per proposition, with expert-labeled evaluation set. Unverified model text must stay unverified.
7. Manual WCAG 2.2 AA and measured task usability plus p75 CWV with actual traffic.
8. Staging integration gate → independent security review → approved production migration → monitored promotion → live smoke tests (safe synthetic docs) → documented rollback. CI green and Railway SUCCESS alone are insufficient.

**Release A security gate:** absent/forged/expired/wrong-issuer tokens rejected; cross-principal document, result, SSE, approval, acceptance and cancellation 0 unauthorized successes; all prior tests remain passing. **Gate B recovery:** offsite isolated restoration with measured integrity and RPO/RTO. **Gate C legal:** evidence verdict accuracy and manual accessibility/usability evidence.

## Open architectural decisions
- Managed OIDC provider/client and session design: BFF recommended; no provider approved/configured yet.
- Tenancy: verified owner plus controlled grants, then choose shared Postgres/RLS, dedicated DB or hybrid based on client confidentiality and policy.
- External encrypted backup target, encryption-key custody, retention and legal data residency requirements.
- Jurisdiction-specific authoritative law registries and required human adjudication thresholds.
- Permissioning and user-facing rules for interrupting an already-running provider operation.

**Do not merge the P0 production cutover until these decisions and evidence gates are satisfied.**
