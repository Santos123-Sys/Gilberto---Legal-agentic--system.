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
  if (!res.ok) throw new Error('Serviço de identidade indisponível. Verifique a configuração do servidor.')
  return data.user
}

export async function signInLocal(email, password) {
  const { res, data } = await authRequest('login', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (res.status === 429) throw new Error('Tentativas de acesso em excesso. Tente novamente mais tarde.')
  if (res.status === 401) throw new Error('E-mail ou senha inválidos.')
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
  if (!res.ok) throw new Error(data.detail || 'Falha ao alterar a senha.')
  return data
}


export async function bootstrapAvailable() {
  const { res, data } = await authRequest('bootstrap-status')
  if (!res.ok) return false
  return data.available === true
}

export async function bootstrapAdmin(email, password, bootstrapToken) {
  const { res, data } = await authRequest('bootstrap', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, bootstrap_token: bootstrapToken }),
  })
  if (!res.ok || data.status !== 'administrator_created') {
    throw new Error(res.status === 409 ? 'A configuração inicial já foi concluída.' :
      'A configuração inicial foi recusada. Verifique o token de uso único e sua validade.')
  }
  return data.user
}
