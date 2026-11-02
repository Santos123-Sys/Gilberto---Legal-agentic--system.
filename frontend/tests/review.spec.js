import { test, expect } from './authenticated-fixture.js'

const config = { num_rounds: 1, num_agents: 4, workflow_type: 'contract_review', jurisdiction: 'BR',
  active_clusters: [{ id: 'foundation', name: 'Foundation', agents: 4 }], max_feedback_rounds: 2, model_call_budget: 250 }
const synthesis = { final_score: 6, final_classification: 'Relevante', confidence: 4,
  executive_summary: 'Synthetic review for interface testing.', critical_actions: [], approval_checklist: [] }

async function setup(page, acceptStatus = 200, focused = false) {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) {
        this.url = url
        window.testStreams.push(this)
        setTimeout(() => this.onopen?.(), 0)
      }
      close() { this.closed = true }
    }
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const response = path.endsWith('/accept')
      ? { status: acceptStatus, body: acceptStatus === 200 ? { status: 'completed' } : { detail: 'Conclua a análise e todas as revisões obrigatórias antes do aceite' } }
      : path.endsWith('/gate-decision')
        ? { status: 200, body: { status: 'awaiting_gate', gate_id: route.request().postDataJSON().gate_id,
            remaining_pending: ['second'], record: { gate_id: route.request().postDataJSON().gate_id, gate_number: 1, status: 'approved' } } }
        : path.endsWith('/start') ? { status: 200, body: { status: 'started' } }
          : path.endsWith('/feedback') ? { status: 409, body: { detail: 'Limite de reanálises atingido' } }
            : path.endsWith('/status') ? { status: 200, body: { status: 'awaiting_feedback' } }
              : { status: 200, body: { session_id: 'test-session', config: { ...config, review_depth: focused ? 'focused' : 'full', initial_model_calls: focused ? 4 : 11 }, status: 'created' } }
    await route.fulfill({ status: response.status, json: response.body })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({ name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic contract for UI testing.') })
  if (focused) await page.getByLabel('Profundidade da revisão', { exact: true }).selectOption('focused')
  await page.getByRole('button', { name: 'Iniciar debate' }).click()
  await expect(page.getByText('4 especialistas · requisições escalonadas', { exact: false })).toBeVisible()
  await expect(page.getByText('Number of Agents', { exact: false })).toHaveCount(0)
  if (focused) await expect(page.getByText('focada · 4 chamadas iniciais ao provedor', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Prosseguir com a análise' }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1)
  return errors
}

async function emit(page, events) {
  await page.evaluate(events => {
    const stream = window.testStreams.at(-1)
    for (const event of events) stream.onmessage({ data: JSON.stringify({ timestamp: '2026-10-22T12:00:00Z', ...event }) })
  }, events)
}

test('resolving one of two same-number gates leaves the other visible', async ({ page }) => {
  const errors = await setup(page)
  const gate = { gate_number: 1, trigger: { description: 'Review the termination clause' } }
  await emit(page, [
    { event_id: 1, type: 'DEBATE_START', active_clusters: ['foundation'] },
    { event_id: 2, type: 'GATE_TRIGGERED', ...gate, gate_id: 'first' },
    { event_id: 3, type: 'GATE_TRIGGERED', ...gate, gate_id: 'second' },
    { event_id: 3, type: 'GATE_TRIGGERED', ...gate, gate_id: 'second' },
  ])
  await expect(page.getByRole('heading', { name: 'Etapa 1: Revisão por baixa confiança' })).toHaveCount(2)
  await page.getByRole('button', { name: 'Aprovar', exact: true }).first().click()
  await page.getByLabel('FUNDAMENTAÇÃO DO ESPECIALISTA').first().fill('Reviewed the clause against the source.')
  await page.getByRole('button', { name: 'Enviar decisão' }).first().click()
  await expect(page.getByRole('heading', { name: 'Etapa 1: Revisão por baixa confiança' })).toHaveCount(1)
  expect(errors).toEqual([])
})

test('rejected acceptance displays server error and retains the report', async ({ page }) => {
  const errors = await setup(page, 409)
  await emit(page, [{ event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' }])
  await page.getByRole('button', { name: 'Aceitar a análise final' }).click()
  await page.getByRole('button', { name: 'Confirmar o aceite final' }).click()
  await expect(page.getByRole('alert')).toContainText('Conclua a análise e todas as revisões obrigatórias antes do aceite')
  await expect(page.getByRole('heading', { name: 'Análise aceita' })).toHaveCount(0)
  await expect(page.getByText(synthesis.executive_summary)).toBeVisible()
  expect(errors).toEqual([])
})

test('failed feedback retains typed correction and current report', async ({ page }) => {
  await setup(page)
  await emit(page, [{ event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' }])
  await page.getByLabel('Comentários para a próxima revisão').fill('Please reconsider the termination clause.')
  await page.getByRole('button', { name: 'Enviar e debater novamente' }).click()
  await expect(page.getByRole('alert')).toContainText('Limite de reanálises atingido')
  await expect(page.getByLabel('Comentários para a próxima revisão')).toHaveValue('Please reconsider the termination clause.')
  await expect(page.getByText(synthesis.executive_summary)).toBeVisible()
})

test('mobile failure preserves partial findings and reset ignores stale events', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const errors = await setup(page)
  await emit(page, [{ event_id: 1, type: 'CLUSTER_COMPLETE', cluster: 'foundation', summary: { summary: 'Retained clause analysis.' } },
    { event_id: 2, type: 'ERROR', message: 'Specialist review incomplete: compliance' }])
  await expect(page.getByRole('region', { name: 'Conclusões especializadas mantidas' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
  await page.getByRole('button', { name: 'Nova análise' }).click()
  await emit(page, [{ event_id: 3, type: 'DEBATE_COMPLETE' }])
  await expect(page.getByRole('heading', { name: 'Configure sua análise' })).toBeVisible()
  expect(errors).toEqual([])
})


test('review depth choice is sent to the server and the actual call plan is visible', async ({ page }) => {
  const request = page.waitForRequest(r => r.url().endsWith('/api/sessions') && r.method() === 'POST')
  const errors = await setup(page, 200, true)
  expect((await request).postDataJSON().review_depth).toBe('focused')
  expect(errors).toEqual([])
})

test('oversized file is rejected before session creation', async ({ page }) => {
  let created = 0
  await page.route('**/api/sessions', route => {
    created += 1
    return route.fulfill({ json: { session_id: 'unexpected' } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'large.txt', mimeType: 'text/plain', buffer: Buffer.alloc(10 * 1024 * 1024 + 1, 'a'),
  })
  await expect(page.getByRole('alert')).toContainText('limite de envio de 10 MB')
  await expect(page.getByRole('button', { name: 'Iniciar debate' })).toBeDisabled()
  expect(created).toBe(0)
})

test('unsupported file extension is rejected before analysis', async ({ page }) => {
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'script.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('fake file'),
  })
  await expect(page.getByRole('alert')).toContainText('Tipo de arquivo não suportado')
  await expect(page.getByRole('button', { name: 'Iniciar debate' })).toBeDisabled()
})

test('new round does not inherit completed workstream score or status from prior round', async ({ page }) => {
  const errors = await setup(page)
  await emit(page, [
    { event_id: 1, type: 'ROUND_START', round: 1 },
    { event_id: 2, type: 'CLUSTER_COMPLETE', cluster: 'foundation', summary: { aggregated_score: 9, confidence_aggregate: 4 } },
    { event_id: 3, type: 'ROUND_START', round: 2 },
    { event_id: 4, type: 'AGENT_THINKING', cluster: 'foundation', agent: 'Current-round reviewer' },
    { event_id: 5, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 6, type: 'DEBATE_COMPLETE' },
  ])
  await expect(page.getByRole('heading', { name: 'Fundamentos' }).last()).toBeVisible()
  await expect(page.getByText('Current-round reviewer', { exact: true })).toBeVisible()
  await expect(page.getByText('9.0', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('agent workspace lists only the configured specialist scope', async ({ page }) => {
  const errors = await setup(page)
  await emit(page, [
    { event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' },
  ])
  const workspace = page.getByRole('region', { name: 'Área de trabalho dos agentes' })
  await expect(workspace.getByRole('heading', { name: 'Fundamentos', exact: true })).toBeVisible()
  await expect(workspace.getByRole('heading', { name: 'Conformidade', exact: true })).toHaveCount(0)
  await expect(workspace.getByRole('heading', { name: 'Risco financeiro', exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('out of sequence progress cannot fabricate a complete review or lose a gate', async ({ page }) => {
  const errors = await setup(page)
  await emit(page, [{ event_id: 2, type: 'GATE_TRIGGERED', gate_id: 'missing-first', gate_number: 1,
    trigger: { description: 'Approval needed' } }])
  await expect(page.getByRole('alert')).toContainText('O histórico de progresso está incompleto')
  await expect(page.getByRole('heading', { name: 'Etapa 1: Revisão por baixa confiança' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Reconectar', exact: true }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(2)
  await emit(page, [
    { event_id: 1, type: 'DEBATE_START', active_clusters: ['foundation'] },
    { event_id: 2, type: 'GATE_TRIGGERED', gate_id: 'missing-first', gate_number: 1,
      trigger: { description: 'Approval needed' } },
  ])
  await expect(page.getByRole('heading', { name: 'Etapa 1: Revisão por baixa confiança' })).toHaveCount(1)
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('acceptance requires a second explicit decision and can be dismissed', async ({ page }) => {
  let acceptanceCalls = 0
  await setup(page)
  await page.route('**/api/sessions/*/accept', async route => {
    acceptanceCalls += 1
    await route.fulfill({ json: { status: 'completed' } })
  })
  await emit(page, [
    { event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' },
  ])
  await page.getByRole('button', { name: 'Aceitar a análise final' }).click()
  await expect(page.getByRole('group', { name: 'Confirmar o aceite final' })).toBeVisible()
  expect(acceptanceCalls).toBe(0)
  await page.getByRole('button', { name: 'Continuar revisando' }).click()
  expect(acceptanceCalls).toBe(0)
  await page.getByRole('button', { name: 'Aceitar a análise final' }).click()
  await page.getByRole('button', { name: 'Confirmar o aceite final' }).click()
  await expect(page.getByRole('heading', { name: 'Análise aceita' })).toBeVisible()
  expect(acceptanceCalls).toBe(1)
})

test('legal draft presents an inspectable manual evidence verification checklist', async ({ page }) => {
  const errors = await setup(page)
  await emit(page, [
    { event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' },
  ])
  await page.getByText('Lista de verificação das provas (manual)').click()
  await expect(page.getByText('Localize cada cláusula contratual citada', { exact: false })).toBeVisible()
  await expect(page.getByText('Estas verificações não são realizadas nem certificadas', { exact: false })).toBeVisible()
  expect(errors).toEqual([])
})
