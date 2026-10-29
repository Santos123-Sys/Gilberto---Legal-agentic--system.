import { test, expect } from '@playwright/test'

test('gate choice exposes selected state to assistive technology and reflows on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) { this.url = url; window.testStreams.push(this); setTimeout(() => this.onopen?.(), 0) }
      close() { this.closed = true }
    }
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    const payload = path.endsWith('/sessions')
      ? { session_id: 'access-test', status: 'created', config: { num_rounds: 1, active_clusters: [{ id: 'foundation', agents: 4 }], model_call_budget: 250 } }
      : { status: 'started' }
    await route.fulfill({ json: payload })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({ name: 'review.txt', mimeType: 'text/plain', buffer: Buffer.from('Review text.') })
  await page.getByRole('button', { name: 'Start Debate' }).click()
  await page.getByRole('button', { name: 'Proceed with Analysis' }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1)
  await page.evaluate(() => window.testStreams[0].onmessage({
    data: JSON.stringify({ event_id: 1, type: 'GATE_TRIGGERED', gate_id: 'gate-a', gate_number: 1,
      trigger: { description: 'Check risk', affected_cluster: 'foundation' } }),
  }))
  const group = page.getByRole('group', { name: 'Review decision' })
  await expect(group).toBeVisible()
  const approve = group.getByRole('button', { name: 'Approve' })
  const override = group.getByRole('button', { name: 'Override' })
  await expect(approve).toHaveAttribute('aria-pressed', 'false')
  await override.click()
  await expect(override).toHaveAttribute('aria-pressed', 'true')
  await expect(approve).toHaveAttribute('aria-pressed', 'false')
  await expect(page.locator('html')).not.toHaveJSProperty('scrollWidth', 5000)
})
