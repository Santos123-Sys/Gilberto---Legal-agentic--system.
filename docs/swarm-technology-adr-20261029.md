# Swarm workspace: protocol and observability decision record

Decision date: 29 October 2026. Source baseline: `d013105ede5707fd4681cfdf58f09fee10c46388` on `release/brlaw-security-staging-20261029`; production main was `3e1c85f376635d2b39d5fbd71b61443430ff816a`. This document records researched facts separately from engineering judgments. It does not certify a production release.

## Existing boundaries and acceptance criteria

The staging application uses React 18.3 / Vite 5.4, FastAPI 0.115, Pydantic 2.8.2, CrewAI 0.80, HTTPX 0.27.2 and SQLite checkpoints. Its event journal is `session['events']`; `_append_event` allocates monotonic integer IDs; the existing authorized SSE endpoint replays by cursor. Sessions and legal results stay authoritative in Gilberto. The existing engine exposes per-task queue/execution duration and token estimates, with separate provider-reported aggregate usage. It does not currently prove provider-invoiced prices or per-agent token attribution.

Acceptance for this change: preserve every domain event and cursor; no second execution source; malformed event identities rejected; no legal draft mislabeled as accepted; snapshots exclude document and identity content; disabled telemetry creates no network work; bounded export failures never alter legal results; no raw document, prompt, output, error, user or role name in exported payloads. Tests are fixtures, not a live vendor interoperability certification.

## Research evidence

| Project | Observed release / maintenance | License inspected | Relevant API / constraint |
|---|---|---|---|
| AG-UI | Latest repository release retrieved: `release/2026-10-21`, published 21 October 2026. Active repository. | MIT in upstream repository. | CUSTOM (`name`, `value`), STATE_SNAPSHOT (`snapshot`), lifecycle and tool contracts. Base event metadata can carry stable IDs. Official repository lists CrewAI support, but its current bridge is for CrewAI Flows; binary compatibility with this pinned CrewAI 0.80 custom scheduler is not demonstrated. |
| CopilotKit | Latest main product release retrieved: `v1.83.0`, published 28 October 2026; separate channels release is not the React product version. | MIT in upstream repository; hosted/commercial features remain separate. | React SPA documentation supports React 18+ and Vite, with a separately hosted runtime. Headless `useAgent` can expose state, but requires its agent/runtime integration, not direct reuse of the existing GET journal stream. |
| AutoGen / Studio | Latest Python release retrieved: `python-v0.7.5`, 30 September 2025. Current README says archived and no longer maintained. Older FAQ claims active maintenance and is superseded by this current warning. | Code: MIT `LICENSE-CODE`; documentation/root `LICENSE`: CC BY 4.0. | Studio is explicitly a prototype, not a production application. Agent-team graph, run inspection and message views are UX references only. No source or visual asset copied. |
| Langfuse | Latest server release retrieved: `v4.72.0`, 29 October 2026. Current compatibility page: Python SDK v5, JS SDK v6; Python v5 requires Python 3.11+ and server v4.59.0+. | Core MIT Expat; specified `ee` paths have separate enterprise terms. | Current OTLP endpoint `/api/public/otel/v1/traces`; Basic project-key authentication; ingestion-version header `4`. JSON OTLP explicitly supported. Python SDK is recommended upstream, but unnecessary for the narrow allowlisted exporter here. |

Primary sources, accessed 29 October 2026:

- [AG-UI event contract](https://docs.ag-ui.com/concepts/events), [repository and integration list](https://github.com/ag-ui-protocol/ag-ui), [release](https://github.com/ag-ui-protocol/ag-ui/releases/tag/release/2026-10-21), [CrewAI bridge](https://docs.copilotkit.ai/crewai-crews).
- [CopilotKit React SPA requirements](https://docs.copilotkit.ai/react-spa), [headless hook](https://docs.copilotkit.ai/reference/hooks/useAgent), [architecture](https://docs.copilotkit.ai/concepts/architecture), [release](https://github.com/CopilotKit/CopilotKit/releases/tag/v1.83.0), [license](https://github.com/CopilotKit/CopilotKit/blob/main/LICENSE).
- [AutoGen archive warning](https://github.com/microsoft/autogen), [Studio scope](https://github.com/microsoft/autogen/blob/main/python/packages/autogen-studio/README.md), [code license](https://github.com/microsoft/autogen/blob/main/LICENSE-CODE), [documentation license](https://github.com/microsoft/autogen/blob/main/LICENSE), [last Python release](https://github.com/microsoft/autogen/releases/tag/python-v0.7.5).
- [Langfuse compatibility](https://langfuse.com/docs/compatibility), [OTLP configuration](https://langfuse.com/integrations/native/opentelemetry), [JSON OTLP example](https://langfuse.com/integrations/no-code/elevenlabs), [license](https://github.com/langfuse/langfuse/blob/main/LICENSE), [server release](https://github.com/langfuse/langfuse/releases/tag/v4.72.0), [sizing](https://langfuse.com/self-hosting/configuration/scaling), [client versus server masking](https://langfuse.com/self-hosting/security/data-masking).
- [OTLP JSON protocol](https://opentelemetry.io/docs/specs/otlp/) defines hex trace/span IDs, numeric enum values and decimal-string 64-bit integers.

## Decision matrix — engineering judgment, not vendor ratings

All columns use the same direction: 1 = poor fit / substantial burden or unresolved risk; 3 = workable with controls; 5 = strong fit / low burden. Effort, overhead, infrastructure and cost scores mean *lower* burden is better. Scores compare the proposed usage of each technology, not an objective overall product ranking. No stars/popularity inputs and no arithmetic total disguising security blockers.

| Criterion | AG-UI event adapter | CopilotKit runtime + headless | AutoGen runtime | Langfuse metadata export |
|---|---:|---:|---:|---:|
| Architectural compatibility | 5 | 3 | 1 | 4 |
| Integration effort | 4 | 2 | 1 | 4 |
| Long-term maintainability | 4 | 3 | 1 | 3 |
| Production maturity for this use | 3 | 3 | 1 | 4 |
| Security implications | 4 | 3 | 1 | 3 |
| Licensing suitability | 5 | 5 | 4 | 4 |
| Railway infrastructure burden | 5 | 2 | 2 | 4 |
| Runtime overhead | 5 | 3 | 1 | 4 |
| Operating cost burden | 5 | 3 | 2 | 4 |
| Specific Gilberto requirement fit | 5 | 3 | 1 | 5 |
| Decision | **Adapt** | **Reference patterns; defer dependency** | **Reference only; reject runtime** | **Adapt; disabled until authorized instance verified** |

AG-UI wins here because it can project the existing stream without replacing orchestration. CopilotKit's support for React/Vite is real; rejecting it as incompatible would be incorrect. Its additional runtime and state ownership introduce work without a demonstrated improvement for the current document-review UI. Reconsider when reusable generative interactions justify it. AutoGen's archived runtime conflicts with confidentiality and maintenance requirements. Langfuse solves operational investigation, not authoritative workflow state; its local adapter is cheap, while full self-hosting is a separate, materially heavier decision.

## Implemented event-wire subset and limitations

`backend/workspace_events.py` provides:

1. `project_event(event, run_id=None)`: one CUSTOM event per journal entry; name `gilberto.<original_type>`, full authorized domain payload in `value`; stable integer ID in `metadata.gilbertoEventId`. Round/revision/agent/cluster fields are included only when present. Legacy runs fall back to the session ID, explicitly not a new run identifier.
2. `state_snapshot(session)`: read-only workflow fields and journal watermark. A reconnecting client uses the watermark to avoid replacing newer state with replayed older state, while collecting historical findings by event identity. It must not treat the watermark as permission to discard findings it never received.
3. `stream_end(session)`: CUSTOM transport-end marker, never successful legal acceptance.

Integration belongs in the existing owner-authorized SSE route with `protocol=ag-ui`; preserve the default legacy format. Snapshots and end markers have no SSE ID, so only persisted records advance the cursor. Reconnects use the same authorization/expiry checks. Reject unknown protocol names. The adapter does not create a second journal, background execution, AG-UI POST RunAgent endpoint, frontend tools or model chain-of-thought stream.

This is a documented AG-UI-compatible **event subset**, not complete AG-UI lifecycle conformance. `DEBATE_COMPLETE` means awaiting feedback in the current engine; no `RUN_FINISHED` is fabricated. Full lifecycle pairs, interoperable RunAgent invocation, native tool-call events and SDK conformance remain deferred pending authoritative identifiers and contracts. Do not present a CrewAI model dispatch as a verified external tool invocation.

## Metadata exporter and privacy

`backend/observability.py` exports OTLP JSON using the existing HTTPX dependency. No new dependency is introduced. Auto-instrumentation is intentionally excluded: it can capture prompts/tool arguments before a later redaction stage. Only enums and numeric measurements pass the allowlist. Session, run, agent and cluster IDs are HMAC-pseudonymized with a separate operator key; document names, owner identity, legal text, prompts, outputs, errors and HTTP headers are never read into the payload.

Each record is an instantaneous **journal-event span**, not an invented provider-duration span. Stable trace ID correlates a session; stable span ID correlates a journal event. Round and agent metadata support filtering. Full parent/child duration hierarchy and per-agent provider token allocation are not implemented by this narrow adapter. Existing execution metrics remain available inside the protected application. Provider-reported prompt/completion counts and estimated input counts retain distinct names. No cost is labeled billed.

Activation variables, all server-side:

| Variable | Required value / purpose |
|---|---|
| `GILBERTO_LANGFUSE_ENABLED` | Defaults false; must equal `true` to opt in |
| `GILBERTO_LANGFUSE_OTLP_ENDPOINT` | Approved exact HTTPS URL ending `/api/public/otel/v1/traces` |
| `GILBERTO_LANGFUSE_APPROVED_HOST` | Exact endpoint hostname |
| `GILBERTO_TELEMETRY_CORRELATION_KEY` | Separate secret of at least 32 characters; retain securely for trace lookup/deletion |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Restricted project credentials |
| `GILBERTO_TELEMETRY_SAMPLE_RATE` | Finite 0–1 value; default 0.1, deterministic per session |

Worker queue holds at most 128 records (constructor maximum 1024). One daemon worker exports; callers never wait for HTTP. HTTP operation timeout is 2 seconds per HTTPX timeout phase; no automatic export retries, redirects or environment proxy trust. Responses are bounded at 64 KiB and partial rejection is counted as failure. Failures only increment safe counters. Close discards pending records and does not block shutdown. The durable legal audit is the application journal, not this best-effort exporter. An in-flight exporter can finish after disable/close; no new records are scheduled.

Retention and remote deletion must be configured/tested at the selected instance before activation. The adapter has no remote deletion API, no local export files and no permission to provision an instance. HMAC IDs support an authorized operator mapping back to a session for deletion, while avoiding clear identifiers at the vendor. A data-transfer assessment, access policy, retention period and deletion exercise remain activation gates. Merely configuring keys is not sufficient evidence.

## Infrastructure and operating cost decision

No new Langfuse infrastructure is provisioned. Incremental infrastructure charge for the disabled exporter is zero; incremental enabled CPU/network usage has **not** been measured. No dollar amount is fabricated.

Upstream self-hosting guidance lists web, worker, PostgreSQL, Redis/Valkey, ClickHouse and object storage. Listed minima total 21.5 GiB RAM and 9 CPUs excluding serverless object storage (or 25.5 GiB / 11 CPUs with self-hosted blob storage). These are vendor sizing recommendations, not measured Gilberto consumption. Railway cost requires measured utilization, traffic, retention volume, backups and actual plan rates. A reduced local development deployment may fit less, but cannot establish production sizing.

Recommended next step after security release gates: use an already authorized compatible instance, start with synthetic data and 10% session sampling, measure resource/network increments and retention deletion, then decide whether managed or self-hosted production is justified. Local injected-exporter tests establish adapter behavior only. No live Langfuse ingestion, dashboard visibility, billing, server retention or production throughput has been verified by this change.

## Verification receipt

Executed locally: `python -m unittest tests.test_workspace_events tests.test_workspace_observability -v` from `backend/`: **14 tests passed**. Coverage includes deep-copy isolation, cursor identity/replay order, invalid identity/timestamp handling, no false acceptance, snapshot privacy, export-content allowlist, stable trace correlation, disabled behavior, exporter failure/no retry, bounded slow-export queue, sampling and fail-closed configuration. CI and integrated authorization/stream tests must additionally pass before merging the integrated PR.
