# Gilberto execution control and voting — security contract

**Platform scope:** Brazilian law only. This is not a verified source of legal conclusions.

## Run controls
- `POST /api/sessions/{id}/pause`: owner-only, active running review; request a pause of **new** model dispatch at a safe async boundary. Already dispatched model requests and their charges may finish. The review status remains `running`; `run_control=pause_requested` is surfaced independently to avoid claiming active in-flight work stopped.
- `POST /api/sessions/{id}/resume`: owner-only, only when `run_control=pause_requested` and no provider/cancel failure. Resumes pending work without replaying finished calls. A server restart does not silently resume a paused review: interrupted checkpoint is marked error, partial findings retained.
- `POST /api/sessions/{id}/cancel`: owner-only and irreversible. Wakes any paused dispatch gate so tasks can cancel. May not terminate a network request already in an executor thread.
- Human review gates retain their existing approve, override and reanalysis policy; a human **advisory vote** never bypasses a gate or certifies model accuracy.

## Interactive analysis
- The browser displays agent analysis results already emitted by the server (NOT private internal reasoning), per-round/source flags, and separate model peer-voting ledger.
- `POST /api/sessions/{id}/human-votes`: owner-only, binds to a unique immutable completed `AGENT_ANALYSIS_COMPLETE` event, requires a reason for disagreement/evidence requests, limits repeated submissions and count, persists reviewer identity, decision and explanatory text. Duplicate votes are rejected; the audit event carries `target_event_id` distinct from its SSE sequence ID.
- Votes are **non-binding** and do not mutate agent risk scores, consensus, cited law, or accepted decisions.
- Only an authenticated session owner sees or modifies its results, votes and controls.
- SSE is the observable ledger; owner votes from restored checkpoints and phase progression require reconnect to replay history. No unverified legal conclusion should appear accepted merely because a vote was recorded.

## Release evidence and known limits
- Unit/integration: owner vs unrelated account; pause/resume/cancel transitions; no second provider dispatch while paused; immutability of analysis scores; vote reason, target and duplicate checks; checkpoint restore.
- UI: Playwright checks explicit control requests, live model votes, user review and consent.
- On live staging, separately validate that operator-approved backup endpoint is configured before sending synthetic documents. Never upload client-sensitive material to unapproved providers.
- No production merge before the P0 identity, encrypted backup/restore and Brazilian-law verification gates of the consolidated release are complete.
