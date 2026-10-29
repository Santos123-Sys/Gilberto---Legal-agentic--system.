# Maritaca continuity — controlled backup inference (29 October 2026)

Scope: Brazilian law only. A failing Maritaca review must NEVER be marked complete merely because a secondary model is reachable. Agent agreement is not legal source verification.

## Risk mitigation behavior

1. **Detect and contain:** Existing provider diagnostics classify status/timeout and stop queued model calls after failure. Save completed agent events, audit records and cost reservations. Do not silently retry timeouts, gateway 5xx, malformed responses or connection losses, where processing/billing may be uncertain.
2. **Operator preauthorization:** A separate OpenAI-compatible inference endpoint is usable only when `FALLBACK_LLM_BASE_URL`, `FALLBACK_LLM_MODEL`, `FALLBACK_LLM_API_KEY`, and `FALLBACK_LLM_ALLOWED_HOSTS` are configured. Only HTTPS, exact allowlisted DNS names and conventional /v1 or /api paths are accepted. Disallow IPs, local/internal names, credentials in URL, redirects and arbitrary ports. Keep credentials only on the server.
3. **Owner consent:** Before any backup-provider dispatch, the authenticated owner must choose **Operator-approved backup**, check the legal-document transfer consent box, review the destination and confirm the new analysis. The server verifies consent and operator configuration independently. No cross-vendor background failover.
4. **Cost/privacy:** Selecting backup may produce additional vendor charges. Keep the existing per-review model-call ceiling and separate configurable fallback token prices (`FALLBACK_LLM_INPUT_PRICE_USD_PER_1M`, `FALLBACK_LLM_OUTPUT_PRICE_USD_PER_1M`); if a monetary ceiling is enabled, missing backup rates cause a 503 before any dispatch. Check Brazilian attorney-client confidentiality, data retention, processing agreements and international data transfer legal basis before approving any endpoint.
5. **Recovery:** A failed/uncertain run is **not resumed** automatically. Use retained partial findings for review, then start a new authorized session and reupload the source document. A new model output cannot be silently equated to the first model’s results. Preserve human expert gate and citation verification obligations.
6. **Rollback:** Unset `FALLBACK_LLM_API_KEY` or `FALLBACK_LLM_ALLOWED_HOSTS` to immediately disable new backup sessions; do not remove persisted consent records, model task provenance, or old checkpoints. Monitor error codes, submitted jobs and reported model usage without logging client document text.

## Release checks

- Simulated 429, 503, timeout and network errors must never result in automatic retry or implicit cross-provider routing.
- Reject forged consent, unallowlisted HTTP endpoints, internal DNS/IP addresses and invalid pricing.
- Verify a primary session uses Maritaca `Key` authorization, while a consented backup session uses the configured `Bearer` scheme.
- Verify model choice survives a checkpoint reload; no secrets in its stored config or logs.
- Both staging CI and consented synthetic-only live inference must pass before production routing is enabled.
- Real backup provider credentials and approved hostname have **not** been provisioned by this PR. Availability cannot be claimed.
