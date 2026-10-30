import { test, expect } from '@playwright/test'

const loggedInUser = { id: 'private-identity-uuid-123', email: 'lawyer@example.com' }

async function mockIdentity(page, options = {}) {
  const calls = []
  let loggedIn = false
  let currentPassword = 'Correct-Strong-Password-2026'
  const effectiveUser = options.admin ? { ...loggedInUser, role: 'admin' } : loggedInUser
  await page.route('**/api/**', async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    calls.push({ path, method: request.method(), headers: request.headers() })
    expect(url.origin).toBe('http://127.0.0.1:5174')
    expect(request.headers().authorization).toBeUndefined()
    if (path === '/api/auth/me') {
      await route.fulfill(loggedIn
        ? { json: { user: effectiveUser } }
        : { status: 401, json: { detail: 'Authentication required' } })
      return
    }
    if (path === '/api/auth/login') {
      const body = request.postDataJSON()
      if (body.email === loggedInUser.email && body.password === currentPassword) {
        loggedIn = true
        await route.fulfill({ json: { user: effectiveUser } })
      } else {
        await route.fulfill({ status: options.throttle ? 429 : 401, json: {
          detail: options.throttle ? 'Too many attempts' : 'Invalid credentials',
        } })
      }
      return
    }
    if (path === '/api/auth/logout') {
      loggedIn = false
      await route.fulfill({ json: { status: 'signed_out' } })
      return
    }
    if (path === '/api/auth/change-password') {
      const body = request.postDataJSON()
      if (body.current_password !== currentPassword || body.new_password.length < 12) {
        await route.fulfill({ status: 400, json: { detail: 'Invalid current or new password' } })
      } else {
        currentPassword = body.new_password
        await route.fulfill({ json: { status: 'password_changed' } })
      }
      return
    }
    if (path === '/api/admin/backups/status') {
      await route.fulfill({ json: {
        enabled: true, last_success_at: 1793210000,
        last_verify_at: 1793210000, object: 'gilberto/staging/mock.glbk',
      } })
      return
    }
    if (path === '/api/admin/backups/run') {
      await route.fulfill({ json: { status: 'uploaded', counts: {} } })
      return
    }
    if (path === '/api/admin/backups/verify') {
      await route.fulfill({ json: { status: 'restored_and_verified', counts: {} } })
      return
    }
    if (path === '/api/sessions') {
      if (!loggedIn) {
        await route.fulfill({ status: 401, json: { detail: 'Authentication required' } })
      } else {
        await route.fulfill({ json: { session_id: 'safe-local-test', status: 'created',
          config: { num_rounds: 1, num_agents: 4, review_depth: 'full',
            active_clusters: [{ id: 'foundation', agents: 4 }], model_call_budget: 250 } } })
      }
      return
    }
    await route.fulfill({ status: 404, json: { detail: 'Not found' } })
  })
  return { calls }
}

async function login(page, password = 'Correct-Strong-Password-2026') {
  await page.getByLabel('E-mail', { exact: true }).fill(loggedInUser.email)
  await page.getByLabel('Senha', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
}

test('requires local credentials before legal workspace, creates session and signs out', async ({ page }) => {
  const { calls } = await mockIdentity(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Gilberto — Acesso seguro' })).toBeVisible()
  await expect(page.locator('#doc-upload')).toHaveCount(0)
  await login(page)
  await expect(page.locator('#doc-upload')).toBeVisible()
  await page.locator('#doc-upload').setInputFiles({
    name: 'public-synthetic.txt', mimeType: 'text/plain',
    buffer: Buffer.from('Only synthetic, nonconfidential legal document'),
  })
  await page.getByRole('button', { name: 'Iniciar debate' }).click()
  await expect(page.getByText('4 specialists · requests are staggered', { exact: false })).toBeVisible()
  expect(calls.some(c => c.path === '/api/sessions' && c.method === 'POST')).toBe(true)
  await page.getByRole('button', { name: 'Sair' }).click()
  await expect(page.locator('#doc-upload')).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Gilberto — Acesso seguro' })).toBeVisible()
})

test('incorrect password never exposes confidential workspace', async ({ page }) => {
  await mockIdentity(page)
  await page.goto('/')
  await login(page, 'incorrect')
  await expect(page.getByRole('alert')).toContainText('E-mail ou senha inválidos')
  await expect(page.locator('#doc-upload')).toHaveCount(0)
})

test('login rate limit has clear feedback and does not silently authenticate', async ({ page }) => {
  await mockIdentity(page, { throttle: true })
  await page.goto('/')
  await login(page, 'incorrect')
  await expect(page.getByRole('alert')).toContainText('Tentativas de acesso em excesso')
  await expect(page.locator('#doc-upload')).toHaveCount(0)
})

test('password change is sent only to same-origin identity endpoint', async ({ page }) => {
  const { calls } = await mockIdentity(page)
  await page.goto('/')
  await login(page)
  await page.getByRole('button', { name: 'Conta' }).click()
  await page.getByLabel('Senha atual').fill('Correct-Strong-Password-2026')
  await page.getByLabel('Nova senha (mínimo de 12 caracteres)').fill('Upgraded-Strong-2026!')
  await page.getByLabel('Confirme a nova senha').fill('Upgraded-Strong-2026!')
  await page.getByRole('button', { name: 'Atualizar senha' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Senha alterada' }).first()).toBeVisible()
  expect(calls.filter(c => c.path === '/api/auth/change-password' && c.method === 'POST').length).toBe(1)
  await page.getByRole('button', { name: 'Sair' }).click()
  await login(page, 'Upgraded-Strong-2026!')
  await expect(page.locator('#doc-upload')).toBeVisible()
})


test('administrator can upload encrypted backup and verify isolated restore', async ({ page }) => {
  const { calls } = await mockIdentity(page, { admin: true })
  await page.goto('/')
  await login(page)
  await page.getByRole('button', { name: 'Conta' }).click()
  await page.getByRole('button', { name: 'Status do backup' }).click()
  await expect(page.getByText('Último teste de restauração:', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Fazer backup agora' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Backup criptografado enviado' }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Verificar restauração isolada' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Restauração isolada do backup verificada' }).first()).toBeVisible()
  expect(calls.filter(c => c.path === '/api/admin/backups/run').length).toBe(1)
  expect(calls.filter(c => c.path === '/api/admin/backups/verify').length).toBe(1)
})

test('non-administrator cannot see privileged backup controls', async ({ page }) => {
  await mockIdentity(page)
  await page.goto('/')
  await login(page)
  await page.getByRole('button', { name: 'Conta' }).click()
  await expect(page.getByRole('button', { name: 'Fazer backup agora' })).toHaveCount(0)
})


test('first administrator setup requires its one-time secret and password confirmation', async ({ page }) => {
  await mockIdentity(page)
  await page.route('**/api/auth/bootstrap-status', async route => {
    await route.fulfill({ json: { available: true } })
  })
  await page.route('**/api/auth/bootstrap', async route => {
    const body = route.request().postDataJSON()
    expect(body.email).toBe(loggedInUser.email)
    expect(body.password).toBe('New-Administrator-Passphrase2026')
    expect(body.bootstrap_token).toBe('fixture-setup-token-only-00000000000000000000000')
    await route.fulfill({ json: { user: { ...loggedInUser, role: 'admin' },
                                 status: 'administrator_created' } })
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Criar o primeiro administrador' })).toBeVisible()
  await page.getByLabel('E-mail', { exact: true }).fill(loggedInUser.email)
  await page.getByLabel('Senha', { exact: true }).fill('New-Administrator-Passphrase2026')
  await page.getByLabel('Confirme a senha do administrador').fill('New-Administrator-Passphrase2026')
  await page.getByLabel('Token de configuração de uso único').fill('fixture-setup-token-only-00000000000000000000000')
  await page.getByRole('button', { name: 'Criar o primeiro administrador' }).click()
  await expect(page.locator('#doc-upload')).toBeVisible()
  await page.getByRole('button', { name: 'Conta' }).click()
  await expect(page.getByRole('button', { name: 'Fazer backup agora' })).toBeVisible()
})
