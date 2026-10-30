import { useMemo, useState } from 'react'

const label = e => 'Revisão ' + (Number.isInteger(e.revision) ? e.revision : 0) +
  ' · Rodada ' + (Number.isInteger(e.round) ? e.round : 'não atribuída')

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
    <p className="text-xs font-semibold text-slate-200">Afirmação #{index + 1} · {finding?.status || 'status indisponível'}</p>
    <p className="text-sm text-slate-300 whitespace-pre-wrap">{finding?.item || 'Texto da afirmação indisponível'}</p>
    <dl className="text-xs space-y-1">
      <div><dt className="text-slate-400 inline">Trecho da fonte: </dt>
        <dd className="inline break-words">{finding?.evidence || 'Nenhum trecho citado'}</dd></div>
      <div><dt className="text-slate-400 inline">Comparação de texto: </dt>
        <dd className="inline">{contract?.status || 'não verificado'}</dd></div>
      {contract?.document_sha256 && <div><dt className="text-slate-400 inline">Document SHA-256: </dt>
        <dd className="inline font-mono break-all">{contract.document_sha256}</dd></div>}
      <div><dt className="text-slate-400 inline">Fundamento jurídico brasileiro alegado: </dt>
        <dd className="inline">{finding?.legal_basis || 'Nenhum informado'}</dd></div>
      {authority && <div><dt className="text-slate-400 inline">Verificação da procedência do fundamento: </dt>
        <dd className="inline whitespace-pre-wrap break-words">{JSON.stringify(authority)}</dd></div>}
      <div className="text-amber-300">Aplicabilidade jurídica e texto da fonte: NÃO VERIFICADOS DE FORMA INDEPENDENTE</div>
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
  return <section aria-label="Histórico de conclusões jurídicas e divergências" className="space-y-3">
    <p className="text-xs text-slate-400">As rodadas anteriores e as revisões por comentário são preservadas. Selecionar um registro antigo nunca altera a pontuação jurídica atual nem as decisões humanas.</p>
    <label htmlFor="review-history-round" className="block text-xs text-slate-300 font-semibold">Rodada de análise registrada</label>
    <select id="review-history-round" value={selection} onChange={e => setSelection(e.target.value)}
      className="bg-slate-800 border border-slate-600 rounded-md p-2 w-full text-sm text-slate-100">
      <option value="latest">{groups[0]?.key || 'Nenhuma rodada registrada'}</option>
      {groups.slice(1).map(g => <option key={g.key} value={g.key}>{g.key}</option>)}
    </select>
    {!selected && <p className="text-slate-500">Não há conclusões no histórico.</p>}
    {selected && <>
      <p className="text-xs text-blue-300">{selected.key} · {analyses.length} análise(s) · {votes.length} voto(s) entre pares</p>
      {analyses.map(e => {
        const parsed = e.parsed || {}
        const audit = parsed.evidence_audit || {}
        const findings = Array.isArray(parsed.key_findings) ? parsed.key_findings : []
        return <article key={e.event_id} className="rounded-lg border border-slate-700/70 p-3 space-y-2">
          <h4 className="text-sm font-semibold">{e.agent || 'Especialista não identificado'} · {e.cluster || 'não atribuído'}</h4>
          <p className="text-xs text-slate-400">Evento #{e.event_id} · pontuação de risco do modelo: {Number.isFinite(parsed.score) ? parsed.score : 'não registrada'}/10</p>
          <p className="text-xs text-amber-300">Verificação das fontes: {audit.source_verification_status || 'NÃO VERIFICADO'}</p>
          <p className="text-xs text-slate-400 whitespace-pre-wrap">{parsed.reasoning || 'Nenhum resumo registrado'}</p>
          {findings.length > 0 && <ol className="space-y-2">{findings.map((f, i) =>
            <ClaimRow key={i} index={i} finding={f} audit={audit.findings?.find(a => a.index === i)} />)}</ol>}
        </article>
      })}
      <h4 className="font-medium text-sm">Votos entre pares e divergências</h4>
      {votes.map(e => <article key={e.event_id} className="border border-slate-700 rounded-md p-3">
        <p className="text-xs font-medium">{e.voter || 'Votante não identificado'} · {e.cluster} · evento #{e.event_id}</p>
        <pre className="text-xs text-slate-300 whitespace-pre-wrap break-words">{JSON.stringify(e.scores || {}, null, 2)}</pre>
      </article>)}
      {!votes.length && <p className="text-xs text-slate-500">Nenhum voto entre pares atribuído a esta rodada.</p>}
      {clusters.map(e => <div key={e.event_id} className="rounded-md p-3 bg-slate-800/50">
        <p className="text-xs font-medium">{e.cluster_name || e.cluster} · síntese do coordenador</p>
        <p className="text-xs text-slate-300">Risco agregado do modelo: {e.summary?.aggregated_score ?? 'não registrado'} · {e.summary?.classification || 'sem classificação'}</p>
        <p className="text-xs text-amber-300 whitespace-pre-wrap">Divergência: {e.summary?.dissent_notes || 'Nenhuma nota de divergência registrada pelo coordenador'}</p>
      </div>)}
      {summaries.map(e => <p key={e.event_id} className="text-xs text-slate-300">Síntese final registrada no evento #{e.event_id}; isso, por si só, não comprova o aceite humano final.</p>)}
    </>}
  </section>
}
