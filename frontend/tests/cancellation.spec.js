import { test, expect } from './authenticated-fixture.js'

test('authenticated owner can request cancellation and sees unambiguous status', async ({ page }) => {
  let cancellationCalls = 0
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/cancel')) {
      cancellationCalls++
      expect(route.request().headers()['authorization']).toBe('Bearer synthetic-browser-test-jwt')
      await route.fulfill({ json: { status: 'cancellation_requested', provider_in_flight_possible: true } })
      return
    }
    await route.fulfill({ json: path.endsWith('/sessions')
      ? { session_id: 'cancel-test', status: 'created', config: { num_rounds: 1,
          active_clusters: [{ id: 'foundation', agents: 4 }], model_call_budget: 250 } }
      : { status: 'started' } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from('synthetic'),
  })
  await page.getByRole('button', { name: 'Iniciar debate' }).click()
  await page.getByRole('button', { name: 'Prosseguir com a análise' }).click()
  await expect(page.getByRole('button', { name: 'Cancelar análise' })).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar análise' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Cancelamento solicitado' }).first()).toBeVisible()
  expect(cancellationCalls).toBe(1)
})
