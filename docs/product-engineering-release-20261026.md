# Reliable first review and explicit review depth

Applied skills: Engineering Workbench (AI Engineer) and Product Workbench (Product Manager).

## Evidence and priority
The previous production synthetic contract run failed in all five workstreams; each task failed in under two seconds. The report correctly remained incomplete but the cause was hidden. The active pipeline used a CrewAI execution loop for tasks with fixed prompts and no tools. A local mock returning plain JSON demonstrated that this loop could repeatedly reject the output format; that reproduces an integration risk, not the proven cause of the production incident.

Priority is a user reaching an inspectable contract draft, with a useful explanation when blocked. There are no interviews or usage statistics supporting a broader redesign. The existing stored failure is a baseline incident, not a fleet failure-rate estimate.

## Delivered behavior
- Fixed workflow stages invoke the documented Maritaca chat completion endpoint directly, one HTTP request per dispatched task; no automatic retry or autonomous parse loop. JSON and Pydantic validation remain outside the model call.
- Missing credentials, rejected credentials, permission, billing, invalid request, rate limits, network errors, truncation and invalid response each have safe recovery guidance. Provider bodies, prompts and credentials are excluded from errors. The first provider failure stops queued work in this engine.
- Full review remains the default. Focused draft is an explicit alternative: one reviewer combining the workstream's expertise, then manager synthesis, then adversarial review and final synthesis. All configured workstreams still run. With all five enabled, one initial full round uses 47 calls; focused uses 12. Revisions cost additional calls. These are modeled counts, not measured latency or legal-quality claims.
- Server preview returns actual roster and initial call count. Review depth persists in checkpoints and is restored for feedback after restart. Existing sessions default to full depth.

## Acceptance and measurement
Transport tests exercise successful content, exact endpoint/one request, no undocumented request parameters, safe failure mapping, missing key/no dispatch, truncation and malformed response. Orchestration tests verify queued calls stop after provider failure and a focused workstream includes combined expertise without peer votes. Existing completion/gate/persistence regressions remain release gates.

Measure live completion or a specific actionable provider failure, actual dispatched calls, queue and execution times, output schema validity and recovery. A representative synthetic canary checks conflicting payment dates and asymmetric termination terms. One canary cannot establish legal accuracy, source validity or equivalence of the two review depths. Benchmark depth against lawyer-labeled documents before changing the default. No quality percentage or speed improvement is claimed without those measurements.

## Next priorities and boundaries
Now: verify direct provider transport and first report after deployment. Next: labeled issue-recall/citation benchmark and account-wide provider pacing. Later: account authorization and off-volume recovery. This release does not add agents, external tools, provider fallback, legal-source verification or off-site backup. SQLite checkpoints remain one-worker storage. Rollback is a PR revert; persisted sessions remain backward compatible.

Official transport reference: https://docs.maritaca.ai/api/pt/completion . The transport uses model, messages, temperature and max_tokens. JSON-only output is instructed and validated locally; no undocumented response_format parameter is sent.
