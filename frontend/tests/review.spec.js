import { test, expect } from '@playwright/test'

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
      ? { status: acceptStatus, body: acceptStatus === 200 ? { status: 'completed' } : { detail: 'Finish required review first' } }
      : path.endsWith('/gate-decision')
        ? { status: 200, body: { status: 'awaiting_gate', gate_id: route.request().postDataJSON().gate_id,
            remaining_pending: ['second'], record: { gate_id: route.request().postDataJSON().gate_id, gate_number: 1, status: 'approved' } } }
        : path.endsWith('/start') ? { status: 200, body: { status: 'started' } }
          : path.endsWith('/feedback') ? { status: 409, body: { detail: 'Re-analysis limit reached' } }
            : path.endsWith('/status') ? { status: 200, body: { status: 'awaiting_feedback' } }
              : { status: 200, body: { session_id: 'test-session', config: { ...config, review_depth: focused ? 'focused' : 'full', initial_model_calls: focused ? 4 : 11 }, status: 'created' } }
    await route.fulfill({ status: response.status, json: response.body })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({ name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic contract for UI testing.') })
  if (focused) await page.getByLabel('Review depth', { exact: true }).selectOption('focused')
  await page.getByRole('button', { name: 'Start Debate' }).click()
  await expect(page.getByText('4 specialists · requests are staggered', { exact: false })).toBeVisible()
  await expect(page.getByText('Number of Agents', { exact: false })).toHaveCount(0)
  if (focused) await expect(page.getByText('focused · 4 initial provider calls', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Proceed with Analysis' }).click()
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
  await expect(page.getByRole('heading', { name: 'Gate 1: Low Confidence Review' })).toHaveCount(2)
  await page.getByRole('button', { name: 'Approve', exact: true }).first().click()
  await page.getByLabel('EXPERT REASONING').first().fill('Reviewed the clause against the source.')
  await page.getByRole('button', { name: 'Submit Decision' }).first().click()
  await expect(page.getByRole('heading', { name: 'Gate 1: Low Confidence Review' })).toHaveCount(1)
  expect(errors).toEqual([])
})

test('rejected acceptance displays server error and retains the report', async ({ page }) => {
  const errors = await setup(page, 409)
  await emit(page, [{ event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' }])
  await page.getByRole('button', { name: 'Accept Final Analysis' }).click()
  await expect(page.getByRole('alert')).toContainText('Finish required review first')
  await expect(page.getByRole('heading', { name: 'Analysis Accepted' })).toHaveCount(0)
  await expect(page.getByText(synthesis.executive_summary)).toBeVisible()
  expect(errors).toEqual([])
})

test('failed feedback retains typed correction and current report', async ({ page }) => {
  await setup(page)
  await emit(page, [{ event_id: 1, type: 'MASTER_MANAGER_COMPLETE', summary: synthesis },
    { event_id: 2, type: 'DEBATE_COMPLETE' }])
  await page.getByLabel('Feedback for the next review').fill('Please reconsider the termination clause.')
  await page.getByRole('button', { name: 'Submit & Re-Debate' }).click()
  await expect(page.getByRole('alert')).toContainText('Re-analysis limit reached')
  await expect(page.getByLabel('Feedback for the next review')).toHaveValue('Please reconsider the termination clause.')
  await expect(page.getByText(synthesis.executive_summary)).toBeVisible()
})

test('mobile failure preserves partial findings and reset ignores stale events', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const errors = await setup(page)
  await emit(page, [{ event_id: 1, type: 'CLUSTER_COMPLETE', cluster: 'foundation', summary: { summary: 'Retained clause analysis.' } },
    { event_id: 2, type: 'ERROR', message: 'Specialist review incomplete: compliance' }])
  await expect(page.getByRole('region', { name: 'Retained specialist findings' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false)
  await page.getByRole('button', { name: 'New Analysis' }).click()
  await emit(page, [{ event_id: 3, type: 'DEBATE_COMPLETE' }])
  await expect(page.getByRole('heading', { name: 'Configure Your Analysis' })).toBeVisible()
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
  await expect(page.getByRole('alert')).toContainText('10 MB upload limit')
  await expect(page.getByRole('button', { name: 'Start Debate' })).toBeDisabled()
  expect(created).toBe(0)
})

test('unsupported file extension is rejected before analysis', async ({ page }) => {
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'script.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('fake file'),
  })
  await expect(page.getByRole('alert')).toContainText('Unsupported file type')
  await expect(page.getByRole('button', { name: 'Start Debate' })).toBeDisabled()
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
  await expect(page.getByRole('heading', { name: 'Foundation' }).last()).toBeVisible()
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
  const workspace = page.getByRole('region', { name: 'Agent workspace' })
  await expect(workspace.getByRole('heading', { name: 'Foundation', exact: true })).toBeVisible()
  await expect(workspace.getByRole('heading', { name: 'Compliance', exact: true })).toHaveCount(0)
  await expect(workspace.getByRole('heading', { name: 'Financial Risk', exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('out of sequence progress cannot fabricate a complete review or lose a gate', async ({ page }) => {
  const errors = await setup(page)
  await emit(page, [{ event_id: 2, type: 'GATE_TRIGGERED', gate_id: 'missing-first', gate_number: 1,
    trigger: { description: 'Approval needed' } }])
  await expect(page.getByRole('alert')).toContainText('Progress history is incomplete')
  await expect(page.getByRole('heading', { name: 'Gate 1: Low Confidence Review' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Reconnect', exact: true }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(2)
  await emit(page, [
    { event_id: 1, type: 'DEBATE_START', active_clusters: ['foundation'] },
    { event_id: 2, type: 'GATE_TRIGGERED', gate_id: 'missing-first', gate_number: 1,
      trigger: { description: 'Approval needed' } },
  ])
  await expect(page.getByRole('heading', { name: 'Gate 1: Low Confidence Review' })).toHaveCount(1)
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(errors).toEqual([])
})
