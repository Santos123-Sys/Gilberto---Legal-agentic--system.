import fs from 'node:fs'
import { test, expect } from './authenticated-fixture.js'

const fixture = {
  num_rounds: 1,
  active_clusters: [{ id: 'foundation', name: 'Foundation', agents: 1 }],
  agent_roster: [{
    id: 'foundation', name: 'Foundation',
    manager: { id: 'foundation:manager:test', kind: 'manager', role: 'Test Manager', display_name: 'Test Manager', avatar_key: 'a12b3c4d' },
    agents: [{ id: 'foundation:specialist:test', kind: 'specialist', role: 'Test Specialist',
      display_name: 'Test Specialist', cluster_id: 'foundation', avatar_key: '8b2c3d4e',
      working_style: 'Synthetic legal fixture' }],
  }],
  coordination_roster: {
    orchestrator: { id: 'coordination:orchestrator:test', role: 'Master Reviewer',
      display_name: 'Master Reviewer', kind: 'orchestrator', avatar_key: 'ac1234ab' },
    adversarial: { id: 'coordination:adversarial:test', role: 'Devil Test',
      display_name: 'Devil Test', kind: 'adversarial', avatar_key: '5aabbccd' },
  },
}

async function start(page) {
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) { window.testStreams.push(this); setTimeout(() => this.onopen?.(), 0) }
      close() { this.closed = true }
    }
  })
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname === '/api/health') return route.fulfill({ json: { status: 'ok' } })
    if (pathname.endsWith('/status')) return route.fulfill({ json: {
      status: 'running', config: fixture, run_control: 'running', execution_state: 'RUNNING',
    } })
    if (pathname.endsWith('/start')) return route.fulfill({ json: { status: 'started' } })
    return route.fulfill({ json: { session_id: 'synthetic-release', status: 'created', config: fixture } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'only-synthetic-br-contract.txt', mimeType: 'text/plain',
    buffer: Buffer.from('This fixture contains no genuine confidential contracts.'),
  })
  await page.getByRole('button', { name: 'Iniciar debate' }).click()
  await page.getByRole('button', { name: 'Prosseguir com a análise' }).click()
  await expect(page.getByRole('region', { name: 'Central de comando dos agentes do Gilberto' })).toBeVisible()
}

for (const width of [390, 768, 1280, 1920]) {
  test('synthetic screenshot and interaction at ' + width + 'px', async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await start(page)
    const inspector = page.getByRole('complementary', { name: 'Inspetor da execução' })
    await expect(inspector).toBeVisible()
    await inspector.getByRole('tab', { name: 'Eventos' }).click()
    await expect(inspector.getByText('Nenhum evento do servidor registrado.')).toBeVisible()
    await inspector.getByRole('tab', { name: 'Agente' }).click()
    await expect(inspector.getByText('Test Specialist', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: /Test Specialist/ }).click()
    await expect(inspector.getByText('Test Specialist', { exact: true })).toBeVisible()
    const path = 'test-results/swarm-screenshots/swarm-' + width + '.png'
    fs.mkdirSync('test-results/swarm-screenshots', { recursive: true })
    await page.screenshot({ path, fullPage: true, animations: 'disabled' })
  })
}
