# Gilberto P0 authenticated-release preflight (draft)

The authenticated frontend/backend implementation is on draft PRs #39, #43 and #44. **Do not merge or promote to Railway production before the conditions below are verified.** Existing main remains unauthenticated; a deployment of the unconfigured branch fails closed (new sessions return 503, and the UI shows an identity-provider configuration error).

## Required managed OIDC configuration

Configure a real standards-compliant provider and register a public SPA (Authorization Code + PKCE S256). The **API**, not the browser, must validate RS256 access tokens signed by the provider and with its own **resource-server audience**, not the SPA client ID.

Backend service variables (set in staging first; never place private keys or client secrets into Vite variables):

```
OIDC_ISSUER=https://provider.example/issuer/
OIDC_AUDIENCE=gilberto-api
OIDC_JWKS_URL=https://provider.example/issuer/jwks.json
CORS_ORIGINS=https://your-staging-frontend.example
```

Frontend build-time variables (public, non-secret; each must be present **before the Vite build**):

```
VITE_OIDC_AUTHORIZATION_ENDPOINT=https://provider.example/authorize
VITE_OIDC_TOKEN_ENDPOINT=https://provider.example/token
VITE_OIDC_CLIENT_ID=your-public-spa-client-id
VITE_OIDC_API_AUDIENCE=gilberto-api
VITE_OIDC_SCOPES=openid profile
VITE_API_URL=https://your-staging-backend.example
```

Replace placeholders with the real provider configuration; do not use them as operational values. Provider must permit the authorized redirect URI (exactly the public SPA origin + path), browser CORS code exchange at the token endpoint and issue **RS256 JWT API access tokens** with `iss, sub, aud, exp, iat`. Some providers require a resource indicator rather than an audience parameter; adapt and verify with the provider-specific registration before release.

## Required approval and smoke tests

- Register two independent IdP users (A and B); create a legal session as A and verify B receives 404 on status/results/gates, SSE, start, feedback, acceptance and cancellation (when implemented). Without a bearer token or with fake/expired/wrong-issuer/wrong-audience tokens, the API returns 401.
- Old unowned checkpoints must remain on disk but be inaccessible (404) to all ordinary users. Prepare an administrator-reviewed provenance-based migration; never claim by knowing the UUID.
- Test OAuth `state` mismatch and CSRF-style callback injection; never store JWT access tokens in cookies, URLs, localStorage or sessionStorage. PKCE verifier/state in sessionStorage is transient, deleted on callback.
- Inspect the Network panel: each REST call and SSE stream must include `Authorization: Bearer` **header**, never a credential in path/query; confirm access-token expiry closes streams and reconnect cannot bypass authorization.
- Validate browser login in desktop and mobile, token expiry, sign-out, refresh, SSE replay, gate approval and alternate-account access.
- Run backend signed JWT negative tests in PR #43 and all existing Playwright scenarios under the simulated IdP in PR #44. Simulation proves UI plumbing only, not real provider interoperability.
- Exercise authorized confidential-data redaction in operations logs and perform backup restore in isolated staging before any migration.

## Known limitations / further release blockers

- The implemented browser session is short-lived and **memory-only**; reload requires signing in again. No refresh-token rotation, immediate bearer-token revocation, centralized device logout, or organization membership/delegation has been implemented. The `(issuer,sub)` owner check is per-user isolation, not collaborative tenant roles.
- Native EventSource was replaced by authenticated fetch; the stream is bounded by access-token expiry but there is no real-time token introspection/revocation midstream.
- Protected high-impact tool gateway, server-authoritative cancellation, encrypted off-project backup and isolated restore are **not implemented** by this PR.
- No managed IdP and no OIDC variables were found in Railway production at source inspection. Main should stay unchanged and production should not receive client legal documents until integrated IdP staging, security review and legacy migration are approved.
