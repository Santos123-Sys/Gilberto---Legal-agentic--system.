import { test, expect } from './authenticated-fixture.js'

async function launch(page, calls) {
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) { this.url = url; window.testStreams.push(this); setTimeout(() => this.onopen?.(), 0) }
      close() { this.closed = true }
    }
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/health') {
      await route.fulfill({ json: { status: 'ok', backup_provider: { configured: false } } })
      return
    }
    if (path.endsWith('/pause') || path.endsWith('/resume') || path.endsWith('/human-votes')) {
      calls.push({ path, body: route.request().postDataJSON?.() })
      if (path.endsWith('/pause')) await route.fulfill({ json: { run_control: 'pause_requested', provider_in_flight_possible: true } })
      else if (path.endsWith('/resume')) await route.fulfill({ json: { run_control: 'running' } })
      else await route.fulfill({ json: { status: 'recorded',
        vote: { ...route.request().postDataJSON(), event_id: 2, reviewer: 'synthetic-owner' } } })
      return
    }
    if (path.endsWith('/start')) await route.fulfill({ json: { status: 'started' } })
    else if (path.endsWith('/status')) await route.fulfill({ json: { status: 'running' } })
    else await route.fulfill({ json: { session_id: 'owner-test', status: 'created',
      config: { num_rounds: 1, active_clusters: [{ id: 'foundation', agents: 4 }],
        model_call_budget: 250 } } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'synthetic.txt', mimeType: 'text/plain',
    buffer: Buffer.from('Synthetic Brazilian law review for UI testing'),
  })
  await page.getByRole('button', { name: 'Iniciar debate' }).click()
  await page.getByRole('button', { name: 'Prosseguir com a análise' }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1)
}

async function emit(page, rows) {
  await page.evaluate(rows => {
    const stream = window.testStreams.at(-1)
    rows.forEach(row => stream.onmessage({ data: JSON.stringify({ timestamp: '2026-10-29T15:00:00Z', ...row }) }))
  }, rows)
}

test('owner pauses new model dispatch and explicitly resumes', async ({ page }) => {
  const calls = []
  await launch(page, calls)
  await page.getByRole('button', { name: 'Pausar o envio aos agentes' }).click()
  await expect(page.getByText('O envio de novas requisições à IA está pausado.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Retomar o envio aos agentes' }).click()
  await expect(page.getByRole('button', { name: 'Pausar o envio aos agentes' })).toBeVisible()
  expect(calls.map(c => c.path)).toEqual(['/api/sessions/owner-test/pause', '/api/sessions/owner-test/resume'])
})

test('user inspects model votes and submits distinct expert advisory vote', async ({ page }) => {
  const calls = []
  await launch(page, calls)
  await emit(page, [
    { event_id: 1, type: 'ROUND_START', round: 1 },
    { event_id: 2, type: 'AGENT_ANALYSIS_COMPLETE', agent: 'Brazilian law reviewer', cluster: 'foundation',
      round: 1, parsed: { score: 7, reasoning: 'Synthetic evidence not yet verified',
        confidence_level: 2, evidence_audit: { source_verification_status: 'NOT_VERIFIED' } } },
    { event_id: 3, type: 'AGENT_VOTE_CAST', voter: 'Peer legal model',
      cluster: 'foundation', round: 1, scores: { score: 7 } },
  ])
  await expect(page.getByRole('heading', { name: 'Painel de análises dos agentes e votação' })).toBeVisible()
  await expect(page.getByText('Synthetic evidence not yet verified')).toBeVisible()
  await page.getByText('Registro de votos entre modelos').click()
  await expect(page.getByText('Peer legal model')).toBeVisible()
  await page.getByLabel('Sua avaliação').selectOption('needs_evidence')
  await page.getByLabel('Motivo (obrigatório)').fill('Verify the STF citation and statute version.')
  await page.getByRole('button', { name: 'Registrar voto consultivo para o evento #2' }).click()
  await expect(page.getByText('Seu voto consultivo registrado: provas insuficientes')).toBeVisible()
  const vote = calls.find(c => c.path.endsWith('/human-votes'))
  expect(vote.body).toMatchObject({ event_id: 2, decision: 'needs_evidence',
    reasoning: 'Verify the STF citation and statute version.' })
  await expect(page.getByText('Estas são avaliações geradas por IA', { exact: false })).toBeVisible()
})
