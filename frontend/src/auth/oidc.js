/** Public OAuth2 authorization-code + PKCE client. Tokens are memory-only.
 * No implicit credentials, passwords, ID tokens, or bearer tokens in URLs.
 * This is a short-lived single-tab session; reload requires sign-in again.
 */
const config = {
  authorization: import.meta.env.VITE_OIDC_AUTHORIZATION_ENDPOINT,
  token: import.meta.env.VITE_OIDC_TOKEN_ENDPOINT,
  client: import.meta.env.VITE_OIDC_CLIENT_ID,
  audience: import.meta.env.VITE_OIDC_API_AUDIENCE,
  scope: import.meta.env.VITE_OIDC_SCOPES || 'openid profile',
}
let accessToken = null
let validUntil = 0
let callbackPromise = null
const TX_KEY = 'gilberto.oidc.pkce.transaction.v1'

function validateConfig() {
  if (!config.client || !config.audience || !config.authorization || !config.token) {
    throw new Error('Sign-in is not configured. An administrator must configure the identity provider.')
  }
  for (const url of [config.authorization, config.token]) {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.hash) {
      throw new Error('Identity-provider endpoints must be trusted HTTPS URLs.')
    }
  }
  return config
}

export function isAuthConfigured() {
  try { validateConfig(); return true } catch { return false }
}

function randomUrlSafe(length = 32) {
  const value = crypto.getRandomValues(new Uint8Array(length))
  return btoa(String.fromCharCode(...value)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function encodeUrlSafe(bytes) {
  return btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

export async function startLogin() {
  const identity = validateConfig()
  // A rejected prior callback must not poison the next PKCE transaction.
  callbackPromise = null
  const verifier = randomUrlSafe()
  const challenge = encodeUrlSafe(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)))
  const state = randomUrlSafe()
  const redirectUri = location.origin + location.pathname
  sessionStorage.setItem(TX_KEY, JSON.stringify({
    verifier, state, redirectUri, created: Date.now(),
  }))
  const url = new URL(identity.authorization)
  url.searchParams.set('response_type', 'code')
  url.searchParams.set('client_id', identity.client)
  url.searchParams.set('redirect_uri', redirectUri)
  url.searchParams.set('scope', identity.scope)
  url.searchParams.set('state', state)
  url.searchParams.set('code_challenge_method', 'S256')
  url.searchParams.set('code_challenge', challenge)
  url.searchParams.set('audience', identity.audience)
  location.assign(url.toString())
}

async function exchangeCode() {
  const identity = validateConfig()
  const url = new URL(location.href)
  const code = url.searchParams.get('code')
  const state = url.searchParams.get('state')
  const error = url.searchParams.get('error')
  url.searchParams.delete('code')
  url.searchParams.delete('state')
  url.searchParams.delete('session_state')
  url.searchParams.delete('error')
  url.searchParams.delete('error_description')
  history.replaceState({}, '', url.pathname + url.search + url.hash)
  const txRaw = sessionStorage.getItem(TX_KEY)
  sessionStorage.removeItem(TX_KEY)
  let tx
  try { tx = JSON.parse(txRaw || 'null') } catch { tx = null }
  if (error || !code || !state || !tx || tx.state !== state ||
      !tx.verifier || tx.redirectUri !== location.origin + location.pathname ||
      Date.now() - tx.created > 300_000 || Date.now() < tx.created) {
    throw new Error('Sign-in response could not be validated. Start a fresh sign-in.')
  }
  const body = new URLSearchParams({
    grant_type: 'authorization_code', code, redirect_uri: tx.redirectUri,
    client_id: identity.client, code_verifier: tx.verifier,
  })
  const response = await fetch(identity.token, {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body, credentials: 'omit', cache: 'no-store',
  })
  if (!response.ok) throw new Error('O provedor de identidade recusou a troca de autenticação.')
  const data = await response.json()
  const seconds = Number(data.expires_in)
  if (data.token_type?.toLowerCase() !== 'bearer' ||
      typeof data.access_token !== 'string' || !data.access_token ||
      !Number.isFinite(seconds) || seconds <= 30 || seconds > 86400) {
    throw new Error('O provedor de identidade retornou uma resposta inválida de token de acesso à API.')
  }
  accessToken = data.access_token
  validUntil = Date.now() + seconds * 1000 - 30_000
}

// React StrictMode replays effects after the callback URL is scrubbed.
export function hasPendingCallback() { return callbackPromise !== null }

export function finishLogin() {
  if (!callbackPromise) callbackPromise = exchangeCode()
  return callbackPromise
}

export function hasAccessToken() {
  return !!accessToken && Date.now() < validUntil
}

export function logout() {
  accessToken = null
  validUntil = 0
  callbackPromise = null
  sessionStorage.removeItem(TX_KEY)
  localStorage.removeItem('gilberto.activeSession.v1')
}

export async function authorizedFetch(input, init = {}) {
  if (!hasAccessToken()) throw new Error('Sign-in expired. Sign in again to access legal materials.')
  const headers = new Headers(init.headers || {})
  headers.set('Authorization', 'Bearer ' + accessToken)
  const response = await fetch(input, { ...init, headers, credentials: 'omit', cache: 'no-store' })
  if (response.status === 401) logout()
  return response
}
