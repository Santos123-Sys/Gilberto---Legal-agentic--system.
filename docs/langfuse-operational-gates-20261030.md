# Langfuse controlled operational integration (30 Oct 2026)

## Implementation and evidence boundary
Gilberto has an optional privacy-first OTLP/HTTP JSON exporter in `backend/observability.py`, operating after its authoritative SQLite checkpoint. Export is disabled unless all exact HTTPS endpoint, approved-host, separate correlation key, Langfuse project key pair and opt-in flag are valid. It is **not** a dependency of Brazilian legal analysis or a replacement for the session event journal.

This PR adds administrator-only `GET /api/admin/observability/status` and explicit `POST /api/admin/observability/probe`. The latter sends a random synthetic metadata-only span through the configured exporter (no real session, document, user identity, prompt or answer), returning only ingestion acceptance. A 200 acceptance is **not** evidence of queryability, retention, per-agent billed usage, deletion, data residency, or a production end-to-end trace. OTLP error response text, credentials and HTTP headers are never returned in the probe receipt.

The exporter uses Langfuse v4's OTLP endpoint `/api/public/otel/v1/traces` and `x-langfuse-ingestion-version: 4`. Refer to the official compatibility and OpenTelemetry integration guides before activating with an instance. Never use the old ingestion endpoint.

## Activation gates (all mandatory)
- Record owner authorization for data transfer, controller/processor terms and Brazilian confidentiality compliance.
- Select approved Langfuse deployment, region and retention/deletion policy, verify tenancy and access restrictions.
- Configure only backend secrets: `GILBERTO_LANGFUSE_ENABLED=true`, `GILBERTO_LANGFUSE_OTLP_ENDPOINT`, `GILBERTO_LANGFUSE_APPROVED_HOST`, `GILBERTO_TELEMETRY_CORRELATION_KEY` (32+ chars), `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `GILBERTO_TELEMETRY_SAMPLE_RATE=0.1`. Keep frontend devoid of all keys.
- Authenticate as an authorized local administrator and use the synthetic `POST /api/admin/observability/probe`; confirm the synthetic span is queryable in the selected tenant.
- Verify instance retention, restricted access and test deletion (including backups). Record screenshot/log evidence without any real confidential documents.
- Run synthetic legal analysis under an explicitly authorized account. Inspect correlation, event ordering, event-count/dropped-count, source timestamps and absence of raw prompt/document/response text in exported spans.
- Measure measured resource overhead, queue loss and actual plan pricing for at least one representative run; do not claim invoice-backed cost from model token estimates.
- Only then approve activation for confidential legal sessions at a controlled sampling percentage.

## Deliberate limitations
Exporter records instantaneous journal-event spans, not invented model-duration or parent-child tool spans. Real provider dispatch may be modeled by native task traces in a future PR only when an authoritative start/end pair exists. The current engine does not provide source-authoritative external tool-call IDs. Live Langfuse provider credentials were not configured in the Railway staging variables at audit time and no Langfuse ingestion has been demonstrated. Retain the feature disabled until all above gates pass.

## Rollback
Set `GILBERTO_LANGFUSE_ENABLED=false` in Railway backend and deploy. This disables new telemetry without disabling legal operations. Keep source legal journal records and backups unchanged. Removing already exported data requires deletion at the authorized Langfuse instance following its retention/deletion process.
