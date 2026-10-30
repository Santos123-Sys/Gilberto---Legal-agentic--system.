import { useMemo, useState } from 'react'

const label = e => 'Revision ' + (Number.isInteger(e.revision) ? e.revision : 0) +
  ' · Round ' + (Number.isInteger(e.round) ? e.round : 'unattributed')

// All views derive from immutable journal records. Never treat model assertions
// or text matching as verified Brazilian legal authority.
export function groupReviewEvents(events = []) {
  const groups = new Map()
  events.filter(e => Number.isInteger(e.event_id) &&
    ['AGENT_ANALYSIS_COMPLETE', 'AGENT_VOTE_CAST', 'CLUSTER_COMPLETE', 'GATE_RESOLVED',
     'DEVILS_ADVOCATE_COMPLETE', 'MASTER_MANAGER_COMPLETE'].includes(e.type))
    .forEach(e => {
      const key = label(e)
      if (!groups.has(key)) groups.set(key, { key, firstId: e.event_id, events: [] })
      groups.get(key).events.push(e)
    })
  return [...groups.values()].sort((a, b) => b.firstId - a.firstId)
}

function ClaimRow({ finding, audit, index }) {
  const contract = audit?.contract_quote
  const authority = audit?.legal_authority
  return <li className="border border-slate-700 rounded-md p-3 space-y-2">
    <p className="text-xs font-semibold text-slate-200">Claim #{index + 1} · {finding?.status || 'status unavailable'}</p>
    <p className="text-sm text-slate-300 whitespace-pre-wrap">{finding?.item || 'Claim text unavailable'}</p>
    <dl className="text-xs space-y-1">
      <div><dt className="text-slate-400 inline">Source passage: </dt>
        <dd className="inline break-words">{finding?.evidence || 'No passage cited'}</dd></div>
      <div><dt className="text-slate-400 inline">Text comparison: </dt>
        <dd className="inline">{contract?.status || 'not checked'}</dd></div>
      {contract?.document_sha256 && <div><dt className="text-slate-400 inline">Document SHA-256: </dt>
        <dd className="inline font-mono break-all">{contract.document_sha256}</dd></div>}
      <div><dt className="text-slate-400 inline">Brazilian legal authority asserted: </dt>
        <dd className="inline">{finding?.legal_basis || 'None supplied'}</dd></div>
      {authority && <div><dt className="text-slate-400 inline">Authority provenance check: </dt>
        <dd className="inline whitespace-pre-wrap break-words">{JSON.stringify(authority)}</dd></div>}
      <div className="text-amber-300">Legal applicability and source text: NOT INDEPENDENTLY VERIFIED</div>
    </dl>
  </li>
}

export function ReviewHistoryInspector({ events = [] }) {
  const groups = useMemo(() => groupReviewEvents(events), [events])
  const [selection, setSelection] = useState('latest')
  const selected = selection === 'latest' ? groups[0] : groups.find(g => g.key === selection)
  const analyses = selected?.events.filter(e => e.type === 'AGENT_ANALYSIS_COMPLETE') || []
  const votes = selected?.events.filter(e => e.type === 'AGENT_VOTE_CAST') || []
  const clusters = selected?.events.filter(e => e.type === 'CLUSTER_COMPLETE') || []
  const summaries = selected?.events.filter(e => e.type === 'MASTER_MANAGER_COMPLETE') || []
  return <section aria-label="Historical legal findings and dissent" className="space-y-3">
    <p className="text-xs text-slate-400">Historical rounds and feedback revisions are preserved. Selecting an older record never updates the current legal score or human decisions.</p>
    <label htmlFor="review-history-round" className="block text-xs text-slate-300 font-semibold">Recorded analysis round</label>
    <select id="review-history-round" value={selection} onChange={e => setSelection(e.target.value)}
      className="bg-slate-800 border border-slate-600 rounded-md p-2 w-full text-sm text-slate-100">
      <option value="latest">{groups[0]?.key || 'No recorded rounds'}</option>
      {groups.slice(1).map(g => <option key={g.key} value={g.key}>{g.key}</option>)}
    </select>
    {!selected && <p className="text-slate-500">There are no historical findings.</p>}
    {selected && <>
      <p className="text-xs text-blue-300">{selected.key} · {analyses.length} analyses · {votes.length} peer votes</p>
      {analyses.map(e => {
        const parsed = e.parsed || {}
        const audit = parsed.evidence_audit || {}
        const findings = Array.isArray(parsed.key_findings) ? parsed.key_findings : []
        return <article key={e.event_id} className="rounded-lg border border-slate-700/70 p-3 space-y-2">
          <h4 className="text-sm font-semibold">{e.agent || 'Unattributed specialist'} · {e.cluster || 'unattributed'}</h4>
          <p className="text-xs text-slate-400">Event #{e.event_id} · model risk score: {Number.isFinite(parsed.score) ? parsed.score : 'not recorded'}/10</p>
          <p className="text-xs text-amber-300">Source verification: {audit.source_verification_status || 'NOT_VERIFIED'}</p>
          <p className="text-xs text-slate-400 whitespace-pre-wrap">{parsed.reasoning || 'No recorded summary'}</p>
          {findings.length > 0 && <ol className="space-y-2">{findings.map((f, i) =>
            <ClaimRow key={i} index={i} finding={f} audit={audit.findings?.find(a => a.index === i)} />)}</ol>}
        </article>
      })}
      <h4 className="font-medium text-sm">Peer votes and dissent</h4>
      {votes.map(e => <article key={e.event_id} className="border border-slate-700 rounded-md p-3">
        <p className="text-xs font-medium">{e.voter || 'Unattributed voter'} · {e.cluster} · event #{e.event_id}</p>
        <pre className="text-xs text-slate-300 whitespace-pre-wrap break-words">{JSON.stringify(e.scores || {}, null, 2)}</pre>
      </article>)}
      {!votes.length && <p className="text-xs text-slate-500">No peer votes attributed to this round.</p>}
      {clusters.map(e => <div key={e.event_id} className="rounded-md p-3 bg-slate-800/50">
        <p className="text-xs font-medium">{e.cluster_name || e.cluster} · manager synthesis</p>
        <p className="text-xs text-slate-300">Aggregated model risk: {e.summary?.aggregated_score ?? 'not recorded'} · {e.summary?.classification || 'unclassified'}</p>
        <p className="text-xs text-amber-300 whitespace-pre-wrap">Dissent: {e.summary?.dissent_notes || 'No explicit manager dissent notes recorded'}</p>
      </div>)}
      {summaries.map(e => <p key={e.event_id} className="text-xs text-slate-300">Master synthesis recorded at event #{e.event_id}; this does not by itself prove final human acceptance.</p>)}
    </>}
  </section>
}
