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
