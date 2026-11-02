# Gilberto swarm workspace — Reliability and release verification

**Date:** 30 October 2026. **Jurisdiction:** Brazilian law only.
This document distinguishes synthetic CI evidence, Railway deployment status and live production readiness. It is not an approval to merge the draft production release #72.

## New automated gates
- Backend runs all unittest tests, including authenticated/cross-owner session access, AG-UI cursor replay, native acceptance semantics, versioned pause/stop race conditions, deterministic legal score calculation, source-audit preservation, Langfuse exporter isolation and provider failure.
- Playwright exercises current-round status, evidence provenance, model and human voting separation, historical dissent, original agent identity interactions, mobile workspace and desktop widths 390/768/1280/1920. Screenshots are generated exclusively from synthetic fixture documents and uploaded as 7-day CI artifacts. Automated screenshots are not user research or a complete WCAG 2.2 AA audit.
- Browser production Vite build and nginx same-origin proxy configuration are tested.
- Backup gateway unittest and container build are mandatory.
- Staging anonymous smoke checks local identity (401), CSRF (403), telemetry admin access (401), backup gateway health and unauthorized upload rejection.
- `staging-release-contract` fails if **any** backend, frontend, gateway or staging smoke prerequisite is skipped/failed. Its green result means synthetic staging CI prerequisites only.

## Release validation matrix

| Category | Automated | Live remaining |
| --- | --- | --- |
| Session authorization | OIDC negative tests, local identity fixture, same-origin CSRF, protected SSE | Two real independent accounts against Railway staging; role revocation mid-stream |
| Run controls | Controlled execution-state and cancellation tests | In-flight paid provider, ambiguous timeout and delayed response; stop/resume race under real traffic |
| AG-UI | Canonical journal event IDs, ordered replay, native documented lifecycle, protected capabilities | Full RunAgent POST / frontend SDK interoperability (not implemented); no fabricated tool IDs |
| Agent graph | Canonical roster, synthetic selectable identities, viewport screenshots | Manual high-fidelity visual and WCAG 2.2 AA review; real usability timing |
| Evidence and voting | Deterministic source-presence status, per-revision/round test fixtures, human-review preservation | Lawyer-certified source texts; blind accuracy corpus and reviewer agreement |
| Langfuse | Allowlist, HMAC pseudonyms, bounded queue, synthetic probe, disabled/unavailable isolation | Authorized external instance, keys, ingestion/query/delete verification, retention/data region approval |
| Financial accountability | Provider-reported vs estimated counts remain separate | Invoice-backed actual costs and p50/p95 latency under representative runs |
| Persistence | Local SQLite checkpoint/restart tests | Independently verified encrypted offsite backup and isolated restore, legacy owner migration |
| Production delivery | CI and Railway deployment SHA reconciliation | Production secrets, rollback rehearsal, verified production E2E canary |

## Operator evidence checklist

Record immutable commit SHA, all Actions run URLs and check outcomes, screenshot artifact ID, backend and frontend Railway deployment IDs/SHAs, date/time and HTTP readiness checks. On staging, use a **nonconfidential synthetic Brazilian contract** to verify sign-in, start, agent inspector, evidence, vote, pause/resume, stop in a separate session, human gate decision, final acceptance, refresh reconciliation and retained partial findings. Never infer the state of a remote provider from HTTP health alone.

Before deploying production confirm the minimum two-account isolation, database restore, consented primary and backup inference, legal-quality acceptance, actual usage/cost, telemetry confidentiality, and rollback procedure. Failure of one mandatory gate blocks promotion. Preserve production volumes, identity database and historic ownerless records. Existing production remains on main until #72 conditions have been independently met.

## Rollback
Use Railway's last verified backend and frontend deployments (both must share a compatible SHA), retain /data and remote backup state. Disable experimental workspace using `VITE_SWARM_WORKSPACE=false` at frontend build time if necessary. Langfuse exporter can independently be disabled using `GILBERTO_LANGFUSE_ENABLED=false`. Do not delete persisted legal materials to recover a build.
