import { useMemo, useState } from 'react'
import { Activity, MessageSquare, ShieldCheck, Vote } from 'lucide-react'

/** This is a view of persisted SSE outcomes, not private model chain-of-thought. */
export function AgentReviewConsole({ events = [], humanVotes = [], status, onVote }) {
  const [selected, setSelected] = useState({})
  const [reason, setReason] = useState({})
  const [sending, setSending] = useState(null)
  const [notice, setNotice] = useState('')
  const analyses = useMemo(() => events.filter(e => e.type === 'AGENT_ANALYSIS_COMPLETE').slice(-30), [events])
  const peerVotes = useMemo(() => events.filter(e => e.type === 'AGENT_VOTE_CAST').slice(-40), [events])
  const canVote = ['running', 'awaiting_gate', 'awaiting_feedback'].includes(status)
  const byId = new Map(humanVotes.map(v => [v.event_id, v]))

  const submit = async (eventId) => {
    const choice = selected[eventId] || 'needs_evidence'
    const explanation = (reason[eventId] || '').trim()
    if (choice !== 'agree' && !explanation) {
      setNotice('Informe o motivo da divergência ou do pedido de provas jurídicas.')
      return
    }
    setSending(eventId)
    setNotice('')
    try {
      const ok = await onVote(eventId, choice, explanation)
      setNotice(ok ? 'Seu voto consultivo foi registrado na trilha de auditoria da sessão.' : 'O servidor não aceitou este voto.')
    } finally {
      setSending(null)
    }
  }

  return (
    <section className="card p-5 space-y-5" aria-label="Análise interativa dos agentes e votação">
      <div className="flex items-start gap-3">
        <Activity size={19} className="text-gold-400 mt-1" />
        <div>
          <h2 className="font-display text-lg text-slate-100">Painel de análises dos agentes e votação</h2>
          <p className="text-sm text-slate-400 mt-1">
            Examine os resultados concluídos dos agentes e os votos entre pares à medida que chegam. Seus votos de especialista são registrados
            separadamente e não alteram o consenso da IA, as fontes jurídicas, a pontuação de risco nem as etapas obrigatórias de revisão humana.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-slate-300" role="status">
        <span><ShieldCheck size={13} className="inline mr-1" />{analyses.length} análise(s) recente(s) de agentes</span>
        <span><Vote size={13} className="inline mr-1" />{peerVotes.length} voto(s) recente(s) entre modelos</span>
        <span><MessageSquare size={13} className="inline mr-1" />{humanVotes.length} voto(s) consultivo(s) humano(s)</span>
      </div>
      {notice && <p role="status" className="text-sm text-amber-300">{notice}</p>}
      {analyses.length === 0 && <p className="text-sm text-slate-400">Ainda não há análises concluídas pelos agentes. O painel é atualizado quando a saída do modelo é registrada.</p>}
      <div className="space-y-3 max-h-[720px] overflow-y-auto pr-1">
        {analyses.slice().reverse().map(event => {
          const vote = byId.get(event.event_id)
          const parsed = event.parsed || {}
          const audit = parsed.evidence_audit || {}
          const choice = selected[event.event_id] || 'needs_evidence'
          return <article key={event.event_id} className="rounded-lg border border-slate-700/70 p-4 space-y-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <h3 className="text-sm font-medium text-slate-100">{event.agent || 'Especialista'}</h3>
                <p className="text-xs text-slate-400">Rodada {event.round || '?'} · {event.cluster_name || event.cluster || 'Frente de análise'} · Evento #{event.event_id}</p>
              </div>
              <span className="text-sm text-gold-300">Pontuação de risco: {typeof parsed.score === 'number' ? parsed.score.toFixed(1).replace('.', ',') : 'Não verificada'}/10</span>
            </div>
            {parsed.reasoning && <p className="text-sm text-slate-300 whitespace-pre-wrap break-words">{parsed.reasoning}</p>}
            <p className="text-xs text-amber-300">Confiança do agente: {parsed.confidence_level ?? 'desconhecida'}/5 · Situação das citações: {audit.source_verification_status || 'não verificadas de forma independente'}</p>
            <details className="text-xs text-slate-400">
              <summary className="cursor-pointer hover:text-slate-200">Ver conclusões e auditoria das provas</summary>
              <pre className="whitespace-pre-wrap break-words mt-2 p-3 bg-slate-900/60 rounded-md max-h-60 overflow-y-auto">{JSON.stringify({
                findings: parsed.key_findings || [], cited_evidence: parsed.supporting_evidence || [],
                recommendations: parsed.recommendations || [], evidence_audit: audit,
              }, null, 2)}</pre>
            </details>
            {vote ? <p className="text-sm text-green-300" role="status">
              Seu voto consultivo registrado: {({ agree: 'concordo', disagree: 'discordo', needs_evidence: 'provas insuficientes' })[vote.decision] || vote.decision}
            </p> : canVote ? <div className="border-t border-slate-700/60 pt-3 space-y-2">
              <label className="block text-xs text-slate-300" htmlFor={`vote-${event.event_id}`}>Sua avaliação</label>
              <select id={`vote-${event.event_id}`} value={choice} disabled={sending === event.event_id}
                onChange={e => setSelected(prev => ({ ...prev, [event.event_id]: e.target.value }))}
                className="w-full bg-slate-800 rounded-md p-2 text-sm text-slate-200">
                <option value="agree">Concordo com este agente</option>
                <option value="disagree">Discordo / apontar erro</option>
                <option value="needs_evidence">Solicitar provas melhores</option>
              </select>
              <label className="block text-xs text-slate-300" htmlFor={`reason-${event.event_id}`}>Motivo {choice !== 'agree' ? '(obrigatório)' : '(opcional)'}</label>
              <textarea id={`reason-${event.event_id}`} rows={2} maxLength={2000} disabled={sending === event.event_id}
                value={reason[event.event_id] || ''} onChange={e => setReason(prev => ({ ...prev, [event.event_id]: e.target.value }))}
                placeholder="Indique um fundamento jurídico brasileiro, um fato controvertido ou uma prova ausente"
                className="w-full bg-slate-800 rounded-md p-2 text-sm text-slate-200" />
              <button type="button" onClick={() => submit(event.event_id)} disabled={sending === event.event_id}
                className="btn-secondary text-sm disabled:opacity-50">Registrar voto consultivo para o evento #{event.event_id}</button>
            </div> : <p className="text-xs text-slate-500">A votação está encerrada nesta etapa da revisão.</p>}
          </article>
        })}
      </div>
      <details className="border-t border-slate-700/60 pt-4">
        <summary className="cursor-pointer font-medium text-slate-200 text-sm">Registro de votos entre modelos ({peerVotes.length} voto(s) recente(s))</summary>
        <p className="text-xs text-slate-400 my-2">Estas são avaliações geradas por IA, e não pareceres de advogados independentes nem decisões vinculantes.</p>
        <div className="max-h-72 overflow-y-auto space-y-2">
          {peerVotes.slice().reverse().map(event => <div key={event.event_id} className="text-xs rounded-md bg-slate-800/50 p-3">
            <p className="text-slate-200">{event.voter || 'Modelo votante'} · Rodada {event.round} · {event.cluster_name || event.cluster}</p>
            <pre className="text-slate-400 whitespace-pre-wrap break-words mt-1">{JSON.stringify(event.scores || {}, null, 2).slice(0, 3000)}</pre>
          </div>)}
          {!peerVotes.length && <p className="text-xs text-slate-500">Nenhum voto de modelo foi registrado ainda.</p>}
        </div>
      </details>
    </section>
  )
}
