# Gilberto – Self-hosted identity (invite-only) operational guide

**Status: draft only (#46 backend and #47 browser). Not deployed; not approved for confidential multiuser work.**

Gilberto can use either managed OIDC (AUTH_MODE=oidc) or local accounts (AUTH_MODE=local). Both feed the same verified (issuer, subject) authorization policy. There is no implicit fallback from either mode to anonymous access.

## Scope of local identity

- No public registration, default administrator account, or hardcoded password. Accounts are created only through an authorized operator shell.
- Argon2id password hashing with per-password salts and high memory cost. Twelve-character minimum. Generic invalid-credential responses plus per-account and per-remote rate limits.
- Opaque, random 256-bit server-side session secret. Only the token hash is persisted. Eight-hour absolute and 30-minute inactivity expiry, revocation on logout, password change, operator password reset or disablement.
- Host-only Secure / HttpOnly / SameSite=Strict browser cookie named __Host-gilberto_session. No JavaScript-readable authentication secret; no JWT signing key to manage.
- Same-origin frontend nginx /api/ reverse proxy, with a shared secret injected as X-Gilberto-Proxy-Auth only at runtime. Backend refuses sensitive requests made directly without that secret.
- Strict Origin verification on mutation endpoints; the local identity user ID maps to the same principal-owner fields already checked by every session route and SSE.
- Browser sign-in, sign-out and password-change forms. Login, session resume and streaming work through same-origin /api and do not carry bearer tokens in a URL.

## Railway staging release sequence

1. Do not change production main or the current Railway production deployment. Set up an isolated staging environment, with a separate backend deployment and persistent volume. Do not copy real client legal data to staging before data-handling review.
2. Generate a high-entropy shared secret on a trusted machine using Python secrets.token_urlsafe(48), and place it only in Railway protected variables. Set backend LOCAL_AUTH_PROXY_SECRET and frontend GILBERTO_PROXY_SECRET to exactly the same value. Never use VITE_ for secrets.
3. Set these backend variables in staging:
   - AUTH_MODE=local
   - IDENTITY_DB_PATH=/data/identity.sqlite3
   - SESSION_DB_PATH=/data/sessions.sqlite3
   - LOCAL_AUTH_APP_ORIGIN=https://EXACT-STAGING-FRONTEND-HOST (no trailing slash, no wildcards)
   - LOCAL_AUTH_PROXY_SECRET=the secret generated in step 2
   - LOCAL_AUTH_COOKIE_SECURE=true
4. Set frontend Vite build variable VITE_AUTH_MODE=local. Set runtime GILBERTO_API_UPSTREAM=https://EXACT-STAGING-BACKEND-HOST (no trailing slash) and runtime GILBERTO_PROXY_SECRET to the same secret. Vite build flags are compiled into assets; confirm the frontend has been rebuilt.
5. From a trusted administrative shell *inside the backend service, with /data mounted*, create the first user using:
       python -m security.local_identity create-user --email lawyer@example.com
   The password is requested without terminal echo via getpass. Do not put passwords into command arguments, environment variables, CI logs or chat transcripts.
6. Log in using the staging frontend URL over HTTPS. Confirm the cookie is set with Secure, HttpOnly, SameSite=Strict and Path=/; confirm it is host-only. Check that no credential is present in localStorage/sessionStorage, request URLs, frontend JavaScript bundles, source maps or application logs.
7. Use two independently created real accounts. Verify cross-user session access is denied, including status, results, gate decisions, SSE, uploads, cancellation and final approval. Test wrong Origin and missing/wrong proxy secret. Verify idle/absolute expiration, password reset, sign-out, and direct backend access rejection.
8. Restore a backup of the *identity and checkpoint databases together* into an isolated staging environment. Establish rotation, encrypted off-site backup, recovery testing, and an approved migration process for legacy ownerless sessions before any production cutover.
9. Verify the high-impact tool approval gateway, operational logging, role/delegation model and MFA decision before authorizing confidential multiuser use.

## Local development only

Run Vite with VITE_AUTH_MODE=local and GILBERTO_PROXY_SECRET equal to the backend LOCAL_AUTH_PROXY_SECRET. Configure the backend LOCAL_AUTH_APP_ORIGIN to match the local Vite origin exactly (for example http://127.0.0.1:5173), AUTH_MODE=local, and LOCAL_AUTH_COOKIE_SECURE=false only for loopback HTTP development. Browsers differ in whether they permit Secure/__Host- cookies on local HTTP; local HTTPS is recommended for browser integration. This insecure cookie setting is prohibited for non-loopback deployment.

## Administrator commands

All commands must run with restricted filesystem access to the persistent identity DB:
- python -m security.local_identity create-user --email name@example.com
- python -m security.local_identity list-users
- python -m security.local_identity reset-password --email name@example.com
- python -m security.local_identity deactivate-user --email name@example.com

Password reset and deactivation revoke existing sessions. Operator shell access is effectively administrator access; protect Railway login and permissions.

## Known omissions and risk acceptance

This is a limited self-hosted *password and session service*, not a general-purpose OIDC identity provider, federated sign-in, or professionally audited authentication product. It does not yet provide MFA/passkeys, email verification, managed password reset, account invitations, org authorization, external SSO, advanced bot/risk detection or independent security certification.

A compromised Railway deployment or stolen browser cookie can still compromise an account. The account-login counters reduce simple password guessing, but are not equivalent to CDN-level rate limiting or fraud controls. Password-reset command execution and database backup/decryption remain operator responsibilities. Session cookies and CSRF protection depend on correct TLS, the trusted reverse proxy and exact Origin configuration.

**Do not merge/deploy solely because tests are green.** Signoff requires a security review, staging evidence, a user bootstrap procedure, controlled rollout and successful encrypted off-site restore. Until then production main must remain unchanged.
