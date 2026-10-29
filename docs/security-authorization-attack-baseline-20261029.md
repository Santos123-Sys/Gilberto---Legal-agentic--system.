# Authorization attack baseline — 29 October 2026

**Source baseline:** `18f61dae499c6d07e72e3bbc8084beb91e26b533`.

## Observed trust boundary
`main._get_session(session_id)` resolves an opaque UUID from memory/SQLite without an authenticated principal. `SessionCreateRequest.user_id` and `GateDecisionRequest.human_review_id` accept caller input. Native EventSource connects with no authenticated header. A server-side lookup of an untrusted UUID is not a permission check.

## Attack scenarios (red, deliberately marked expectedFailure)
1. Anonymous user creates new reviews.
2. Anonymous user reads status, legal results and gate history by UUID.
3. Arbitrary bearer text is ignored by API resource routes.
4. Self-asserted `user_id` does not create a verifiable owner.
5. Self-asserted reviewer can approve a pending gate (replay/expiry controls also absent).
6. Anonymous actor subscribes to a session SSE stream.

These `@unittest.expectedFailure` tests are **proof of missing safeguards**, not remediation. Any CI summary with expected failures must explicitly separate them from passing assertions. Remove the decorator only when the new backend identity and authorization middleware protects the entire route (including SSE), and rerun these tests with a real signed JWT and a second independently authorized subject.

## Enforceable policy
- Owner is immutable, sourced from server-validated `(issuer, subject)` pair, not from request payload. Organisation membership must also be server-verified and revocable.
- Non-owner returns indistinguishable 404 where disclosure would be harmful; absent/invalid auth returns 401 with secure bearer challenge. Distinguish "not found" vs "not authorized" only to permitted operators.
- All mutations including `start`, `feedback`, `gate-decision`, `accept`, and future `cancel` require explicit permissions, checked immediately before execution/commit.
- SSE must authenticate before streaming and must not place bearer tokens into URLs or operational logs. Change native EventSource to a secured same-origin session bridge, or a fetch stream with authorization headers, after OIDC is integrated.
- Quarantine old checkpoints lacking validated owners. Never assign legacy documents to the first caller, infer ownership from UUID, or silently delete them.
- The client may display a reviewer name, but backend audit identity must come exclusively from verified principal. Prevent privilege elevation by untrusted names and organization claims.
- Verify separate principals and organizations in backend, frontend and restore tests. Token expiry, audience, issuer, signature, key rotation and revocation are additional gates.

Ref: OWASP ASVS 5.0 V8.2.2, V8.4.1, V10.3.1–3. Classification: P0. Gate A remains **NOT MET**.
