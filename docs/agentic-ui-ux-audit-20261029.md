# Gilberto — Agentic Interface, UI/UX engineering audit

**Snapshot:** 29 October 2026 | **Initial source:** `4c229d8` | **Release candidate updates:** see [issue #27](../issues/27) | **Status:** partial remediation; no full WCAG or legal-accuracy certification.

## 1. Inspectable architecture

The user configures a Brazilian contract review, confirms an execution preview, uploads a document, watches five potential specialist workstreams, reviews risk gates, and either accepts the synthesized analysis or provides feedback. FastAPI manages in-memory session tasks and a SQLite checkpoint store; React consumes cursor-based SSE events. The provider supports a bounded, deterministic multi-step review, not unrestricted tool autonomy. Railway operates separate frontend/backend services.

**Observations grounded in source:** `backend/main.py`, `backend/session_store.py`, `backend/engines/debate_engine_v3.py`, `frontend/src/App.jsx`, `frontend/src/hooks/useAgenticSession.js`, `AgentClusterPanel.jsx`, `AgenticProgress.jsx`, `GateReviewPanel.jsx`, `SynthesisDashboard.jsx`.

**Security stop:** `_get_session` checks only the opaque session ID. No verified principal-to-session authorization exists. Consequently, session confidentiality, gate permissions, and multiuser production use cannot be certified. Separately, there is no independently demonstrated off-volume restoration. Never portray a browser session ID as authentication.

## 2. Prioritized gap register

| ID | Severity | Difficulty | Evidence | User consequence | Acceptance target |
|---|---|---|---|---|---|
| AUTH-1 | P0 | Hard | session retrieval by UUID, no principal check | possible unauthorized legal document disclosure/action | unauthenticated and cross-user denial with secure migration |
| CTRL-1 | P0 | Hard | no cancel endpoint | run and model cost not controllable | idempotent server cancellation; explicit residual in-flight warning |
| STATE-1 | P1 | Hard | cluster status and score scanned across rounds | previous result may look current | separate current vs past rounds; browser regression |
| STATE-2 | P1 | Hard | interrupted run displays active-worker headline | misleading progress | state-aligned failure message, no animated active state |
| RESUME-1 | P1 | Hard | recover via SSE replay alone | gate state may be delayed or stale | reconcile server-approved pending/resolved review data |
| EVID-1 | P1 | Hard | generated citations not verified against text spans | ungrounded legal claims may appear supported | claim-to-source span validation plus legal reference checks |
| UI-1 | P1 | Medium | five static agent cards | scope confusion | only configured workstreams and critic visible |
| UI-2 | P1 | Medium | long conditional workflow | extra cognitive/navigation effort | tested phase navigation, keyboard skip link, 390px reflow |
| UI-3 | P2 | Medium | dynamic Tailwind text class interpolation | status colors may be absent after purge | static typed classes, visual assertion |
| A11Y-1 | P1 | Easy | decision selection not semantically exposed | uncertain review decision for AT users | aria-pressed and mobile touch targets |
| A11Y-2 | P1 | Easy | status announcements not centrally bounded | repeated announcements | validated polite/alert announcements |
| OBS-1 | P1 | Medium | no field Vitals or user timing | improvement unproven | consent-based RUM, p75 LCP/INP/CLS and observed task timing |

See [issue #27](https://github.com/Santos123-Sys/Gilberto---Legal-agentic--system./issues/27) for PR/dependency updates.

## 3. Transferable competitive patterns

| Product | Verified pattern | Suitable Gilberto adaptation | What not to copy |
|---|---|---|---|
| Claude Code | plan/manual/auto execution permissions | explicit proposed vs approved vs executed distinction | terminal permissions without human reviewer identity |
| ChatGPT Work / legacy Agent | user-visible narrated progress and confirmation for consequential actions | backend-owned execution milestones, pause for material legal approval | equating narration with verified agent execution |
| Cursor Agent | sandbox/allowlist/approval policies for tool actions | least-privilege delegated tools and review of side effects | unrestricted autonomous shell access |
| Gilberto baseline | bounded workstreams and human risk gates | retain deterministic review and exact gate IDs | UI states inferred from stale progress |

Sources: [Claude permission modes](https://support.claude.com/en/articles/14554922-claude-code-user-faq), [ChatGPT agent control patterns](https://openai.com/index/introducing-chatgpt-agent/), [Cursor run modes](https://cursor.com/docs/agent/security/run-modes), [WCAG focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html).

## 4. Reproducible baseline and metric definitions

At baseline commit `4c229d8`, GitHub Actions run `40831143580` passed **44 backend unit tests**, **7 Playwright browser tests**, and the production Vite build. Those are synthetic, mostly mocked browser workflows. They **do not** measure live provider accuracy, legal evidence truth, 90th-percentile work time, human cognitive load, or assistive-technology accessibility.

Use an identical test set for before/after `U`. When `U_baseline=1`, `U_new/U_baseline > 1` is impossible. For newly introduced formerly-unimplemented acceptance cases, report absolute before/after passes and denominator, rather than an undefined division by zero. Run both baseline and candidate on the same test definitions and environment before attributing improvement.

| Metric | Baseline as of snapshot | Target / reproducible protocol |
|---|---|---|
| Automated backend suite | 44/44 passed | all previously passing plus new fault tests |
| Automated frontend suite | 7/7 passed | all existing plus new keyboard/viewport/interruption tests |
| Task completion | Not measured on real users | scripted contract upload, gate review, acceptance, retry; same tasks/participants and devices |
| Agent reliability | Not measured on live provider | fixed labeled legal sample with expected outcomes, independent adjudication |
| Observability | Not measured | event-to-truth audit of proposed, started, paused, stopped and complete states |
| Median completion time/clicks | Not measured | same participant recruitment, time task beginning to verified outcome |
| Core Web Vitals | Not measured | p75 LCP, INP, CLS by device profile; report sample counts and environment |
| Accessibility | Existing focus CSS; no full manual audit | automated axe + keyboard walkthrough + screen reader on desktop/mobile |
| Error recovery | no measured recovery rate | replay/reload/injected 502/restart scenarios; data parity and task outcomes |
| User authorization | No user-ownership layer | negative cross-user tests before exposing sessions publicly |
| Legal traceability | No claim-grounding rate | exact claim/source span matches and citation validity, human-labeled |

## 5. Verification and deployment criteria

For every PR: immutable base SHA, changed test cases, CI links, browser scenario, merge SHA, and Railway deploy ID for *both* services. Verify both service SHA and online status independently. Do not equate Railway SUCCESS with end-to-end feature validation. A real live legal-document canary needs a safe synthetic contract and actual provider integration without client data. Reject release for authorization, integrity, accessibility or critical flow regression.

**Known limitations:** third-party browser/live service navigation was not available from this chat, so a human-keyboard/AT walkthrough, real-user timing, lawful data source checks, complete owner authentication, offsite backup restore, production legal accuracy, and field Web Vitals remain unverified. These block the requested definition of done even if PR CI succeeds.

## 6. Release and rollback bookkeeping

Use the PR list and checks linked from [audit issue #27](https://github.com/Santos123-Sys/Gilberto---Legal-agentic--system./issues/27). Rollback is revert to last verified merge SHA and Railway release of that commit, subject to session-volume compatibility; do not delete the SQLite volume or silently reset human gate decisions.
