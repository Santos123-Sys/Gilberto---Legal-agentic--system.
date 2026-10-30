import { test, expect } from '@playwright/test'

test('interrupted execution is described as stopped, never shown as agents still working', async ({ page }) => {
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) { this.url = url; window.testStreams.push(this); setTimeout(() => this.onopen?.(), 0) }
      close() {}
    }
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    await route.fulfill({ json: path.endsWith('/sessions')
      ? { session_id: 'failed-run', status: 'created', config: { num_rounds: 1, active_clusters: [{ id: 'foundation', agents: 4 }], model_call_budget: 250 } }
      : { status: 'started' } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({ name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from('contract') })
  await page.getByRole('button', { name: 'Start Debate' }).click()
  await page.getByRole('button', { name: 'Proceed with Analysis' }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1)
  await page.evaluate(() => window.testStreams[0].onmessage({ data: JSON.stringify({
    event_id: 1, type: 'ERROR', message: 'Review was interrupted',
  }) }))
  await expect(page.getByRole('heading', { name: 'Analysis stopped — review incomplete' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Your legal teams are working' })).toHaveCount(0)
  await expect(page.getByText('This is not an accepted or fully verified legal analysis.', { exact: false })).toBeVisible()
})


test('feedback round failure cannot display previous-round green stage completions', async ({ page }) => {
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) { this.url = url; window.testStreams.push(this); setTimeout(() => this.onopen?.(), 0) }
      close() {}
    }
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    await route.fulfill({ json: path.endsWith('/sessions')
      ? { session_id: 'failed-feedback', status: 'created', config: { num_rounds: 2, active_clusters: [{ id: 'foundation', agents: 4 }], model_call_budget: 250 } }
      : { status: 'started' } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({ name: 'synthetic.txt', mimeType: 'text/plain', buffer: Buffer.from('synthetic contract') })
  await page.getByRole('button', { name: 'Start Debate' }).click()
  await page.getByRole('button', { name: 'Proceed with Analysis' }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1)
  await page.evaluate(() => {
    const events = [
      { event_id: 1, type: 'DEBATE_START', active_clusters: ['foundation', 'strategy'] },
      { event_id: 2, type: 'ROUND_START', round: 1 },
      { event_id: 3, type: 'DEVILS_ADVOCATE_COMPLETE', round: 1 },
      { event_id: 4, type: 'MASTER_MANAGER_COMPLETE', round: 1 },
      { event_id: 5, type: 'DEBATE_COMPLETE', round: 1 },
      { event_id: 6, type: 'FEEDBACK_RECEIVED', round: 2, feedback: 'recheck' },
      { event_id: 7, type: 'CLUSTER_FAILED', round: 2, cluster: 'foundation', code: 'rate_limit' },
      { event_id: 8, type: 'CLUSTER_FAILED', round: 2, cluster: 'strategy', code: 'invalid_model_output' },
      { event_id: 9, type: 'ERROR', message: 'Re-analysis incomplete: foundation (rate_limit), strategy (invalid_model_output)' },
    ]
    for (const event of events) {
      window.testStreams[0].onmessage({ data: JSON.stringify(event) })
    }
  })
  await expect(page.getByRole('heading', { name: 'Analysis stopped — review incomplete' })).toBeVisible()
  await expect(page.getByText('foundation review failed', { exact: false }).first()).toBeVisible()
  const synthesisStage = page.getByText('Manager synthesis', { exact: true }).first().locator('..').locator('..')
  await expect(synthesisStage).not.toHaveClass(/border-emerald-500/)
  await expect(page.getByText('Final analysis', { exact: true }).first()).toBeVisible()
})
