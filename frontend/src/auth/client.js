import { authorizedFetch as oidcFetch } from './oidc'

// API credentials depend on the explicitly selected authentication mode.
// Local mode uses only same-origin, HttpOnly cookies. Never store or expose
// the local session ID to JavaScript.
export const localIdentityEnabled = import.meta.env.VITE_AUTH_MODE === 'local'

export async function authorizedFetch(input, init = {}) {
  if (!localIdentityEnabled) return oidcFetch(input, init)
  const response = await fetch(input, {
    ...init, credentials: 'same-origin', cache: 'no-store',
  })
  if (response.status === 401) {
    window.dispatchEvent(new Event('gilberto:local-session-expired'))
  }
  return response
}
