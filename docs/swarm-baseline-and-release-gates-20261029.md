# Swarm workspace: baseline, scope and release gates

Audit date: 29 October 2026. This is engineering evidence, not legal certification.

## Immutable baselines

- Default branch main: `3e1c85f376635d2b39d5fbd71b61443430ff816a`.
- Existing integrated staging branch: `release/brlaw-security-staging-20261029`, commit `d013105ede5707fd4681cfdf58f09fee10c46388`.
- Production frontend deployment `8b44a7c3-309f-41b6-8f1d-5c452897c4e6` and backend `431ebae2-bcda-4a1f-8ed0-90592497178c`: Railway SUCCESS at the main SHA above.
- Staging backend `3f7d113a-bd58-49e4-b28b-c61568d07bd4`, frontend `ac0aec8d-b9df-446a-8951-2043a0ba2372`: SUCCESS at the staging SHA above.
- Production promotion is already tracked in draft PR #72. Reuse existing security PRs #39–54, #74 and control/provider PRs #75–77; do not duplicate or bypass them.

## Reproduced baseline

An isolated worktree at the staging SHA ran the unchanged suites: 148/148 backend unittest tests, 18/18 OIDC fixture browser tests, 7/7 local-identity browser tests, 3/3 frontend unit tests. Vite production build passed: JS 263.26 kB (77.89 kB gzip), CSS 32.95 kB (7.25 kB gzip). Local Python 3.12; CI/Railway Python 3.11 is a separate required gate.

Baseline accessibility is partial automated coverage, not a WCAG certificate. Paid provider dispatches, real legal quality, production latency p50/p95, real-user task times, billed token cost and backup restore were not measured here. No simulated measurements are substituted.

## Gap register

| Priority | Evidence and gap | Treatment |
|---|---|---|
| P0 | Production main predates local identity implementation; staging has protected owners, CSRF/proxy trust, expiring sessions and legacy quarantine | Keep production promotion blocked by PR #72 until real two-account deployment verification and provisioning |
| P0 | Existing pause records only `pause_requested`, without effective pause acknowledgment | Add provider-dispatch boundary acknowledgment and server-owned state/version receipts |
| P0 | Cancellation cancelled child tasks without awaiting cleanup | Drain coroutine cleanup, persist terminal history, ignore late remote results |
| P1 | Interrupted sessions preserve findings but cannot safely restart engine work | Explicit INTERRUPTED state; resume disabled; no fabricated resumability |
| P1 | Hook skipped replay for cancelled sessions | Restore cancelled/cancellation-requested history and backend configuration |
| P1 | Existing UI hardcodes presentation scope and lacks contextual inspection | Backend-derived identities, current-round filtering, responsive swarm shell and accessible inspector |
| P1 | Existing SSE is authoritative, sequenced and owner-authorized; no AG-UI projection | Optional projection on the same stream/cursor; never a second event authority |
| P1 | No authorized telemetry destination or measured infrastructure budget | Disabled-by-default metadata-only bounded adapter; no infrastructure provisioned |
| P0 release | Staging first-admin setup incomplete; no primary/fallback API key variable present | Real authenticated staging and provider checks blocked; do not manufacture credentials or infer provider success from health |

## Bounded PR sequence and acceptance

1. Execution controls: preserve legacy API; pause drains active work, resume never replays completed requests, idempotent stop, stale command rejection, durable terminal and interruption state. Test all control transitions, cross-owner denial and late output handling. No prompts/scoring edits.
2. Backend workspace contracts: canonical roster plus optional AG-UI event-wire projection, versioned snapshots, metadata-only observability. Test roster identity/scope, ordered projection, reconnect authorization, default no-export and exporter failure isolation. No new infrastructure or direct AutoGen dependency.
3. Frontend workspace: backend-derived hierarchy, separate actual adversarial stage, inspector and accessible responsive shell; retained upload, review, feedback and final acceptance. Test all unchanged workflows plus round isolation, stopped refresh and four viewport widths.
4. Verification/report: reconcile exact CI and staging SHAs; publish screenshots and remaining gate evidence. Production merge/deploy only after all mandatory PR #72 and task release gates pass.

## Control semantics and operating constraints

`status` remains the compatible legal workflow field. `execution_state` distinguishes CREATED, PREPARING, RUNNING, PAUSE_REQUESTED, PAUSED, RESUMING, AWAITING_HUMAN_REVIEW, AWAITING_FEEDBACK, STOP_REQUESTED, STOPPING, STOPPED, COMPLETED, ERROR and INTERRUPTED. `control_version` advances on state changes. New clients supply `?expected_version=N`; stale commands receive 409. Stop remains idempotent even if the first response was lost.

PAUSED means no new provider dispatch and no active provider coroutine. Deterministic processing of a completed response can still finish. A mandatory human gate takes precedence over manual pause in the displayed workflow state. Resume never authorizes a gate. Python threads and already dispatched remote calls cannot be killed safely and may still incur charges; no automatic retry follows an ambiguous timeout. Interrupted recovery retains findings and requires a new run.

The existing single-worker SQLite deployment is required. This is not a distributed lock. Keep one uvicorn worker and one Railway replica until a shared transactional command/journal design is implemented and tested.

## Rollback

Staging rollback reference is baseline `d013105` with the two deployment IDs above. Preserve `/data` and both SQLite stores. Use Railway rollback/redeploy of a verified existing build; do not delete volumes or claim unowned sessions. Production is not promoted while blockers remain. An additive workspace can be disabled with `VITE_SWARM_WORKSPACE=false` at frontend build time, retaining the prior interface.
