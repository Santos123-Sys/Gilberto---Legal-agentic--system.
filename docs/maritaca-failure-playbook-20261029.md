# Maritaca failure triage — 29 October 2026

Scope: Brazilian-law review requests sent through the direct Maritaca chat-completions transport. Do not send client documents to diagnostic tools or another provider without authorization.

## What is and is not established

The existing string "Maritaca is unavailable" was emitted for any unclassified non-2xx HTTP response. It was **not** evidence that the provider was globally down. Production Railway has variable names `MARITACA_API_KEY`, `MARITACA_BASE_URL`, and `MARITACA_MODEL`, but the connected environment does not expose their values. Availability cannot be confirmed by reading app health; this only reports configuration presence. There is no historical HTTP status in persisted application logs for the cited failed run.

## Safe classification (no response-body or key logging)

- 400/422: request rejected. Check model name, payload/schema, and supported parameters.
- 401/403: credential or permission. Check account access and model entitlement.
- 402: account balance or billing.
- 404/405: endpoint or model mismatch. Check configured base URL and the documented `/api/chat/completions` path.
- 408: provider timeout. Outcome is uncertain; do not resubmit automatically.
- 429: account rate limits. Inspect limits and pace requests; wait before new analysis.
- 500–599: provider-side HTTP failure, **not proof** of a platform-wide outage.
- 3xx: unexpected redirect; verify trusted base URL and API path.
- Connection or client timeout: network failure/unknown completion, not conclusive provider outage.

Failure logs include only categorical code and numeric HTTP status; persisted per-task stage metrics include status when available. No provider response body, legal source text, credentials, or request headers are logged. Each model POST is sent at most once. This prevents unaccounted replay of a possibly billable or completed response.

## Operational validation before release

1. Compare Railway deployment SHA to the GitHub merge SHA; confirm source points to the intended branch.
2. Read sanitized application log categories and task metrics. Capture the specific HTTP status (or timeout/connection) and UTC timestamp for a new failure.
3. Independently check Maritaca's own status page, the documented chat-completions endpoint and authenticated `GET /api/models` using the service's existing environment secret. Never paste the key or a real document into logs, issues, or browser devtools. A model-list success does **not** prove paid inference is healthy.
4. If the service has 401/403/402/404/422, correct credential, account, URL, or model rather than retrying. For 429, assess usage and configured pacing. For 5xx, consult provider status, preserve checkpoint, and explicitly request a new run only after recovering.
5. Run unit tests and, after a staged rollout, a consented synthetic non-confidential end-to-end completion test. Record model, deployment SHA, HTTP status and costs. Do not claim the real-provider incident is resolved without this evidence.

Reference: https://docs.maritaca.ai/api/pt/completion and https://docs.maritaca.ai/pt/status.
