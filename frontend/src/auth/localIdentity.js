/** Browser side of the locally managed identity service.
 * Credentials are sent to same-origin /api/auth endpoints. The browser stores
 * the opaque session cookie (HttpOnly, Secure, SameSite Strict); JS never sees it.
 */
async function authRequest(path, options = {}) {
  const res = await fetch('/api/auth/' + path, {
    credentials: 'same-origin', cache: 'no-store', ...options,
  })
  const data = await res.json().catch(() => ({}))
  return { res, data }
}

export async function getLocalUser() {
  const { res, data } = await authRequest('me')
  if (res.status === 401) return null
  if (!res.ok) throw new Error('Identity service unavailable. Check the server configuration.')
  return data.user
}

export async function signInLocal(email, password) {
  const { res, data } = await authRequest('login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (res.status === 429) throw new Error('Too many sign-in attempts. Try again later.')
  if (res.status === 401) throw new Error('Invalid email or password.')
  if (!res.ok || !data.user) throw new Error('Sign-in unavailable. Contact the administrator.')
  return data.user
}

export async function signOutLocal() {
  const { res } = await authRequest('logout', { method: 'POST' })
  if (!res.ok) throw new Error('Sign-out failed. Retry before leaving this device.')
  localStorage.removeItem('gilberto.activeSession.v1')
}

export async function changeLocalPassword(currentPassword, newPassword) {
  const { res, data } = await authRequest('change-password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  if (!res.ok) throw new Error(data.detail || 'Password change failed.')
  return data
}
