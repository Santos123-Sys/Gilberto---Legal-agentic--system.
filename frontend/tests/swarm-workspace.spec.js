import { test, expect } from './authenticated-fixture.js'

const roster = {
  id: 'foundation',
  name: 'Foundation & Document Integrity',
  color: '#38bdf8',
  manager: {
    id: 'foundation:manager:foundation-manager', cluster_id: 'foundation', kind: 'manager',
    role: 'Foundation Manager', display_name: 'Foundation Manager', avatar_key: '9dbcf42c',
  },
  agents: [{
    id: 'foundation:specialist:brazilian-contract-classifier', cluster_id: 'foundation',
    kind: 'specialist', role: 'Brazilian Contract Classifier',
    display_name: 'Brazilian Contract Classifier', avatar_key: '21ab34cd',
    specialization: 'Brazilian commercial contracts', working_style: 'Systematic and precise',
  }],
}
const config = {
  num_rounds: 2, review_depth: 'focused',
  active_clusters: [{ id: 'foundation', name: roster.name, agents: 1 }],
  agent_roster: [roster],
  coordination_roster: {
    orchestrator: {
      id: 'coordination:orchestrator:master', role: 'Master Legal Partner',
      display_name: 'Master Legal Partner', kind: 'orchestrator', avatar_key: '4b5512ab',
    },
    adversarial: {
      id: 'coordination:adversarial:devils-advocate', role: 'Devil’s Advocate',
      display_name: 'Devil’s Advocate', kind: 'adversarial', avatar_key: '7c3261af',
    },
  },
}

async function start(page) {
  await page.addInitScript(() => {
    window.testStreams = []
    window.EventSource = class {
      constructor(url) { this.url = url; window.testStreams.push(this); setTimeout(() => this.onopen?.(), 0) }
      close() { this.closed = true }
    }
  })
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/health') return route.fulfill({ json: { status: 'ok' } })
    if (path.endsWith('/status')) return route.fulfill({ json: {
      status: 'running', config, execution_state: 'RUNNING', run_control: 'running',
    } })
    if (path.endsWith('/start')) return route.fulfill({ json: { status: 'started' } })
    return route.fulfill({ json: { session_id: 'swarm-fixture', status: 'created', config } })
  })
  await page.goto('/')
  await page.locator('#doc-upload').setInputFiles({
    name: 'synthetic-br-law.txt', mimeType: 'text/plain',
    buffer: Buffer.from('Synthetic contract for a Brazilian-law-only review'),
  })
  await page.getByRole('button', { name: 'Start Debate' }).click()
  await page.getByRole('button', { name: 'Proceed with Analysis' }).click()
  await expect.poll(() => page.evaluate(() => window.testStreams.length)).toBe(1)
}

async function emit(page, rows) {
  await page.evaluate(rows => {
    const stream = window.testStreams.at(-1)
    rows.forEach(row => stream.onmessage({ data: JSON.stringify({
      timestamp: '2026-10-30T09:00:00Z', session_id: 'swarm-fixture', ...row,
    }) }))
  }, rows)
}

test('uses backend roster only and inspects grounded current agent findings', async ({ page }) => {
  await start(page)
  const panel = page.getByRole('region', { name: 'Gilberto swarm command center' })
  await expect(panel).toBeVisible()
  await expect(panel.getByText('1 configured specialists')).toBeVisible()
  await expect(panel.getByText('Foundation & Document Integrity')).toBeVisible()
  await expect(panel.getByText('Compliance', { exact: true })).toHaveCount(0)
  await expect(panel.getByRole('button', { name: /Devil’s Advocate/ })).toBeVisible()

  await emit(page, [
    { event_id: 1, type: 'ROUND_START', round: 1, execution_state: 'RUNNING' },
    { event_id: 2, type: 'AGENT_ANALYSIS_COMPLETE', agent: 'Brazilian Contract Classifier',
      agent_id: roster.agents[0].id, cluster: 'foundation', round: 1,
      parsed: { reasoning: 'Synthetic termination clause needs legal review.',
        key_findings: ['Notice obligation requires checking'],
        supporting_evidence: ['Synthetic contract section 4'],
        evidence_audit: { source_verification_status: 'NOT_VERIFIED' } } },
  ])
  await panel.getByRole('button', { name: /Brazilian Contract Classifier/ }).click()
  const inspector = page.getByRole('complementary', { name: 'Run inspector' })
  await expect(inspector.getByText('Synthetic termination clause needs legal review.')).toBeVisible()
  await inspector.getByRole('tab', { name: 'Evidence' }).click()
  await expect(inspector.getByText('Synthetic contract section 4')).toBeVisible()
  await expect(inspector.getByText('Verification: NOT_VERIFIED')).toBeVisible()
  await inspector.getByRole('tab', { name: 'Costs' }).click()
  await expect(inspector.getByText('Provider usage not yet reported')).toBeVisible()
})

test('isolates old round findings and votes from current decision workspace', async ({ page }) => {
  await start(page)
  await emit(page, [
    { event_id: 1, type: 'ROUND_START', round: 1 },
    { event_id: 2, type: 'AGENT_ANALYSIS_COMPLETE', agent: 'Brazilian Contract Classifier',
      agent_id: roster.agents[0].id, cluster: 'foundation', round: 1,
      parsed: { reasoning: 'Old synthetic finding' } },
    { event_id: 3, type: 'AGENT_VOTE_CAST', voter: 'Brazilian Contract Classifier',
      agent_id: roster.agents[0].id, cluster: 'foundation', round: 1, scores: { score: 2 } },
    { event_id: 4, type: 'ROUND_START', round: 2 },
  ])
  const panel = page.getByRole('region', { name: 'Gilberto swarm command center' })
  await expect(panel.getByText('0 current-round analyses recorded')).toBeVisible()
  await panel.getByRole('button', { name: /Brazilian Contract Classifier/ }).click()
  const inspector = page.getByRole('complementary', { name: 'Run inspector' })
  await expect(inspector.getByText('No completed analysis in the current round')).toBeVisible()
  await expect(inspector.getByText('Old synthetic finding')).toHaveCount(0)
  await inspector.getByRole('tab', { name: 'Votes' }).click()
  await expect(inspector.getByText('No current-round model peer votes.')).toBeVisible()
})

test('inspector remains navigable on narrow screens without fictitious agents', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await start(page)
  await expect(page.getByRole('link', { name: 'Inspect' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Events' })).toBeVisible()
  await page.getByRole('tab', { name: 'Events' }).click()
  await expect(page.getByText('No backend events recorded.')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Review results' })).toHaveAttribute('href', '#gilberto-review-desk')
})


test('shows source-level contract verification without certifying legal authority or hiding dissent', async ({ page }) => {
  await start(page)
  await emit(page, [
    { event_id: 1, type: 'ROUND_START', round: 1 },
    { event_id: 2, type: 'AGENT_ANALYSIS_COMPLETE', agent: 'Brazilian Contract Classifier',
      cluster: 'foundation', round: 1, revision: 0, parsed: {
        score: 7, reasoning: 'Synthetic disputed clause',
        key_findings: [{ item: 'Notice is due', status: 'WARNING',
          evidence: 'Synthetic contract 12.2', legal_basis: 'Brazilian Civil Code claim' }],
        evidence_audit: { source_verification_status: 'NOT_VERIFIED',
          findings: [{ index: 0, status: 'quoted_contract_text_present_legal_basis_unverified',
            contract_quote: { status: 'present_in_supplied_document', document_sha256: 'synthetic-sha' },
            legal_authority: { status: 'unverified_official_text' } }] },
      } },
    { event_id: 3, type: 'AGENT_VOTE_CAST', voter: 'Brazilian Contract Classifier',
      cluster: 'foundation', round: 1, revision: 0,
      scores: { scores: { 'Peer 2': 8 }, rationale: 'Disagree on notice.' } },
    { event_id: 4, type: 'CLUSTER_COMPLETE', cluster: 'foundation',
      cluster_name: 'Foundation', round: 1, revision: 0,
      summary: { aggregated_score: 7, classification: 'Relevante', dissent_notes: 'Manager flags source dispute' } },
  ])
  await page.getByRole('tab', { name: 'History' }).click()
  const history = page.getByRole('region', { name: 'Historical legal findings and dissent' })
  await expect(history.getByText('Notice is due')).toBeVisible()
  await expect(history.getByText('Synthetic contract 12.2')).toBeVisible()
  await expect(history.getByText('present_in_supplied_document')).toBeVisible()
  await expect(history.getByText('Legal applicability and source text: NOT INDEPENDENTLY VERIFIED')).toBeVisible()
  await expect(history.getByText('Manager flags source dispute')).toBeVisible()
  await page.getByRole('tab', { name: 'Tools' }).click()
  await expect(page.getByText('No independently identified external tool-call lifecycle', { exact: false })).toBeVisible()
})
