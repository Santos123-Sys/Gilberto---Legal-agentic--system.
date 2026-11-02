import { useMemo, useState } from 'react'
import { ReviewHistoryInspector } from './ReviewHistoryInspector'
import { Activity, AlertCircle, BookOpen, Clock3, FileSearch, Network, Receipt, Scale, Vote } from 'lucide-react'

// This is a projection of the authenticated session, never a second workflow state.
// No standalone agent names, confidence scores, verification claims or task counts.
export function currentExecutionEvents(events = []) {
  const index = events.findLastIndex(event =>
    event.type === 'ROUND_START' || event.type === 'FEEDBACK_RECEIVED')
  return index === -1 ? events : events.slice(index)
}

export function agentActivity(agent, events = []) {
  if (!agent) return { label: 'Não observado', last: null, result: null }
  const relevant = events.filter(event =>
    event.agent_id === agent.id ||
    (event.cluster === agent.cluster_id && (event.agent === agent.role || event.voter === agent.role)))
  const last = relevant.at(-1) || null
  const result = relevant.filter(event => event.type === 'AGENT_ANALYSIS_COMPLETE').at(-1) || null
  const labels = {
    AGENT_THINKING: 'Análise enviada',
    AGENT_ANALYSIS_COMPLETE: 'Análise registrada',
    AGENT_VOTING: 'Voto entre pares enviado',
    AGENT_VOTE_CAST: 'Voto entre pares registrado',
  }
  return { label: labels[last?.type] || 'Não observado', last, result }
}

function Identity({ agent, label }) {
  const hash = agent?.avatar_key || '000000'
  const hue = parseInt(hash.slice(0, 4), 16) % 360
  const initials = (agent?.display_name || agent?.role || '?')
    .split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase()
  const seed = parseInt(hash.slice(4, 8), 16) || 0
  const glyph = seed % 4
  return <svg aria-hidden="true" viewBox="0 0 48 48" className="shrink-0 w-9 h-9 rounded-xl border border-white/20"
    style={{ background: 'hsl(' + hue + ' 45% 23%)' }}>
    <circle cx="24" cy="24" r="19" fill="none" stroke="hsl(45 70% 75%)" strokeOpacity=".55" strokeWidth="1.3" />
    <circle cx="24" cy="24" r={6 + seed % 4} fill="hsl(45 70% 78%)" fillOpacity=".25" />
    {glyph === 0 && <path d="M24 7 L40 34 L8 34 Z" fill="none" stroke="white" strokeWidth="2" />}
    {glyph === 1 && <path d="M24 6 L42 24 L24 42 L6 24 Z" fill="none" stroke="white" strokeWidth="2" />}
    {glyph === 2 && <><path d="M8 24 H40 M24 8 V40" stroke="white" strokeWidth="2" /><circle cx="24" cy="24" r="12" stroke="white" fill="none" strokeWidth="1.5" /></>}
    {glyph === 3 && <path d="M9 14 L39 14 L32 36 L16 36 Z" fill="none" stroke="white" strokeWidth="2" />}
    <text x="24" y="28" fill="white" fontSize="9" fontWeight="700" textAnchor="middle">{initials.slice(0, 2)}</text>
  </svg>
}

function DataText({ value, fallback = 'Não registrado' }) {
  if (value == null || value === '') return <span className="text-slate-500">{fallback}</span>
  if (typeof value === 'string' || typeof value === 'number') return <span className="break-words whitespace-pre-wrap">{value}</span>
  return <pre className="text-xs whitespace-pre-wrap break-words overflow-auto max-h-52">{JSON.stringify(value, null, 2)}</pre>
}

function SummaryRow({ title, children }) {
  return <div className="py-2 border-b border-slate-700/60 last:border-b-0">
    <dt className="text-xs uppercase tracking-wider text-slate-400 mb-1">{title}</dt>
    <dd className="text-sm text-slate-200"><>{children}</></dd>
  </div>
}

function InspectPanel({ tab, agent, events, current, metrics, status, sessionId, connectionState, pendingCount }) {
  const data = agentActivity(agent, current)
  const modelVotes = current.filter(e => e.type === 'AGENT_VOTE_CAST')
  const humanVotes = events.filter(e => e.type === 'HUMAN_VOTE_RECORDED')
  const findings = current.filter(e => e.type === 'AGENT_ANALYSIS_COMPLETE')
  return <div className="space-y-3 text-sm">
    {tab === 'agent' && <>
      {agent ? <dl>
        <div className="flex items-center gap-3 mb-3">
          <Identity agent={agent} />
          <div className="min-w-0"><h4 className="font-semibold text-slate-100 break-words">{agent.display_name || agent.role}</h4>
            <p className="text-xs text-slate-400">{agent.kind} · {data.label}</p></div>
        </div>
        <SummaryRow title="Especialização"><DataText value={agent.specialization} /></SummaryRow>
        <SummaryRow title="Estilo de trabalho"><DataText value={agent.working_style} /></SummaryRow>
        <SummaryRow title="Último evento"><DataText value={data.last ? ('#' + data.last.event_id + ' · ' + data.last.type) : null} /></SummaryRow>
        <SummaryRow title="Fundamentação jurídica registrada"><DataText value={data.result?.parsed?.reasoning} fallback="Nenhuma análise concluída na rodada atual" /></SummaryRow>
        <SummaryRow title="Principais conclusões"><DataText value={data.result?.parsed?.key_findings} /></SummaryRow>
        <SummaryRow title="Avaliação das provas"><DataText value={data.result?.parsed?.evidence_audit} fallback="Não verificado de forma independente" /></SummaryRow>
      </dl> : <p className="text-slate-400">Selecione um especialista configurado ou um agente coordenador.</p>}
      <p className="text-xs text-amber-300">Todas as identidades representam papéis de IA, e não advogados inscritos na OAB. As conclusões dos agentes exigem verificação humana e das fontes.</p>
    </>}
    {tab === 'events' && <>
      <dl>
        <SummaryRow title="ID da sessão"><span className="font-mono break-all">{sessionId}</span></SummaryRow>
        <SummaryRow title="Fluxo jurídico"><DataText value={status} /></SummaryRow>
        <SummaryRow title="Fluxo de eventos (transporte)"><DataText value={connectionState} /></SummaryRow>
        <SummaryRow title="Etapas de revisão humana pendentes">{pendingCount}</SummaryRow>
      </dl>
      <ol aria-label="Linha do tempo de eventos da rodada atual" className="space-y-2 max-h-80 overflow-y-auto">
        {[...current].reverse().slice(0, 40).map(e => <li key={e.event_id} className="border-l-2 border-slate-500 pl-3 py-1">
          <span className="font-mono text-xs text-slate-400">#{e.event_id} {e.timestamp ? ' · ' + e.timestamp : ''}</span>
          <p className="break-words">{e.type} {e.agent || e.voter || e.cluster || ''}</p>
        </li>)}
        {!current.length && <li className="text-slate-500">Nenhum evento do servidor registrado.</li>}
      </ol>
      <p className="text-xs text-slate-400">A linha do tempo mostra eventos registrados; a conexão do fluxo não comprova que os agentes estejam em execução.</p>
    </>}
    {tab === 'evidence' && <>
      <p className="text-xs text-amber-300">Um dispositivo legal ou trecho de documento citado não é verificado de forma independente apenas porque um agente de IA o mencionou.</p>
      {findings.length ? findings.map(e => <article key={e.event_id} className="rounded-lg border border-slate-700 p-3 space-y-2">
        <h4 className="font-semibold">{e.agent || 'Agente'} · evento #{e.event_id}</h4>
        <p className="text-xs text-amber-300">Verificação: {e.parsed?.evidence_audit?.source_verification_status || 'NÃO VERIFICADO'}</p>
        <p className="text-xs text-slate-400">Provas de suporte alegadas</p>
        <DataText value={e.parsed?.supporting_evidence} />
        <p className="text-xs text-slate-400">Auditoria do documento e das citações</p>
        <DataText value={e.parsed?.evidence_audit} />
      </article>) : <p className="text-slate-500">Nenhuma conclusão de agente registrada na rodada atual.</p>}
    </>}
    {tab === 'votes' && <>
      <p className="text-xs text-slate-400">Os votos são atribuídos à rodada atual. Os votos consultivos humanos são distintos dos votos entre modelos e das etapas de aprovação jurídica.</p>
      {modelVotes.map(e => <article key={e.event_id} className="rounded-lg border border-slate-700 p-3">
        <h4 className="font-semibold">{e.voter} · {e.cluster}</h4>
        <p className="text-xs text-slate-400">Rodada {e.round ?? 'desconhecida'} · evento #{e.event_id}</p>
        <DataText value={e.scores} />
      </article>)}
      {!modelVotes.length && <p className="text-slate-500">Nenhum voto entre modelos na rodada atual.</p>}
      <h4 className="font-medium pt-2 border-t border-slate-700">Histórico de votos consultivos humanos ({humanVotes.length})</h4>
      {humanVotes.slice(-10).reverse().map(e => <p key={e.event_id} className="text-xs text-slate-300">
        Evento #{e.event_id}: {e.decision} · refere-se ao evento de agente #{e.target_event_id}
      </p>)}
    </>}
    {tab === 'history' && <ReviewHistoryInspector events={events} />}
    {tab === 'tools' && <div className="space-y-2 text-sm">
      <p className="text-amber-300">O registro de eventos atual do CrewAI não expõe nenhum ciclo de chamadas a ferramentas externas identificado de forma independente.</p>
      <p className="text-slate-400">Envios ao modelo e afirmações sobre fontes não são apresentados como chamadas verificadas a ferramentas externas. As chamadas a ferramentas só aparecerão quando o servidor emitir IDs, nomes e status de ferramentas autorizados.</p>
    </div>}
    {tab === 'costs' && <>
      <p className="text-xs text-slate-400">Os contadores operacionais vêm do servidor. Nenhum faturamento ou custo é inferido da referência de design.</p>
      <dl>
        <SummaryRow title="Envios ao modelo registrados"><DataText value={metrics?.model_calls} /></SummaryRow>
        <SummaryRow title="Tokens de entrada estimados (não faturados)"><DataText value={metrics?.estimated_input_tokens} /></SummaryRow>
        <SummaryRow title="Uso informado pelo provedor"><DataText value={metrics?.provider_usage} fallback="Uso ainda não informado pelo provedor" /></SummaryRow>
        <SummaryRow title="Teto de custo reservado (estimativa em USD)"><DataText value={metrics?.reserved_upper_bound_usd} /></SummaryRow>
        <SummaryRow title="Latência por grupo (ms)"><DataText value={metrics?.cluster_latencies} /></SummaryRow>
        <SummaryRow title="Medições de execução das tarefas"><DataText value={metrics?.model_tasks} /></SummaryRow>
      </dl>
      <p className="text-xs text-amber-300">Reservas estimadas e contadores do provedor não são cobranças faturadas verificadas. Não se afirma a cobertura de rastreamento externo pelo Langfuse.</p>
    </>}
  </div>
}

const TABS = [
  { id: 'agent', label: 'Agente', icon: FileSearch },
  { id: 'events', label: 'Eventos', icon: Activity },
  { id: 'evidence', label: 'Provas', icon: BookOpen },
  { id: 'votes', label: 'Votos', icon: Vote },
  { id: 'costs', label: 'Custos', icon: Receipt },
  { id: 'history', label: 'Histórico', icon: BookOpen },
  { id: 'tools', label: 'Ferramentas', icon: FileSearch },
]

export function SwarmWorkspace({
  sessionId, config, events = [], status, connectionState, pendingGates = [],
  executionMetrics = {}, executionState, documentName,
}) {
  const [selectedId, setSelectedId] = useState(null)
  const [tab, setTab] = useState('agent')
  const current = useMemo(() => currentExecutionEvents(events), [events])
  const roster = Array.isArray(config?.agent_roster) ? config.agent_roster : []
  const coordination = config?.coordination_roster || {}
  const allAgents = roster.flatMap(c => [...(c.agents || []), ...(c.manager ? [c.manager] : [])])
  if (coordination.orchestrator) allAgents.unshift(coordination.orchestrator)
  if (coordination.adversarial) allAgents.push(coordination.adversarial)
  const agent = allAgents.find(a => a.id === selectedId) || allAgents[0] || null
  const currentRound = current.find(e => e.type === 'ROUND_START')?.round ||
    current.find(e => typeof e.round === 'number')?.round
  const completed = current.filter(e => e.type === 'AGENT_ANALYSIS_COMPLETE').length
  const configured = roster.reduce((total, c) => total + (c.agents || []).length, 0)
  const selectAgent = (id) => { setSelectedId(id); setTab('agent') }

  const orchestratorEvent = current.filter(e => e.type === 'MASTER_MANAGER_START' || e.type === 'MASTER_MANAGER_COMPLETE').at(-1)
  const adversaryEvent = current.filter(e => e.type === 'DEVILS_ADVOCATE_START' || e.type === 'DEVILS_ADVOCATE_COMPLETE').at(-1)
  return <section aria-label="Central de comando dos agentes do Gilberto" className="my-6 space-y-4">
    <header className="rounded-xl border border-slate-700 bg-[#0b1728] p-4 sm:p-5 flex flex-wrap justify-between gap-3">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-blue-300">Área de trabalho / Análise jurídica brasileira</p>
        <h2 className="text-xl font-semibold text-slate-100">Central de comando da análise jurídica</h2>
        <p className="text-xs text-slate-400 mt-1">{documentName || 'Nome do documento indisponível'} · Rodada {currentRound ?? 'não iniciada'} / {config?.num_rounds ?? '?'}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span role="status" className="rounded-md border border-slate-500 px-3 py-2 text-slate-200">Fluxo: {executionState || status}</span>
        <span className="rounded-md border border-slate-600 px-3 py-2 text-slate-300">Transmissão: {connectionState}</span>
        <a href="#gilberto-inspector" className="rounded-md border border-blue-500/60 px-3 py-2 text-blue-300 hover:bg-blue-900/30">Inspecionar</a>
        <a href="#gilberto-review-desk" className="rounded-md border border-blue-500/60 px-3 py-2 text-blue-300 hover:bg-blue-900/30">Revisar resultados</a>
      </div>
    </header>
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.9fr)] gap-4 items-start">
      <section aria-label="Fluxo dos agentes em tempo real" className="min-w-0 rounded-xl border border-slate-700 bg-[#0b1728] p-4 sm:p-5">
        <div className="flex items-start justify-between gap-2">
          <div><h3 className="font-semibold tracking-wide text-slate-100 flex items-center gap-2"><Network size={17} /> Equipe de agentes / fluxo registrado</h3>
            <p className="text-xs text-slate-400 mt-1">{configured} {configured === 1 ? 'especialista configurado' : 'especialistas configurados'} · {roster.length} {roster.length === 1 ? 'grupo configurado' : 'grupos configurados'} · {completed} {completed === 1 ? 'análise registrada' : 'análises registradas'} na rodada atual</p>
          </div>
          <span className="text-xs text-blue-300 shrink-0">Rodada {currentRound ?? '—'}</span>
        </div>
        <figure aria-label="Dependências reais de execução" className="mt-4 rounded-lg bg-slate-900/50 p-3 text-xs text-slate-300">
          <div className="flex flex-wrap gap-2 items-center justify-center" aria-hidden="true">
            {['Especialistas', 'Votação entre pares', 'Coordenadores de grupo', 'Advogado do diabo', 'Síntese final', 'Revisão humana'].map((stage, i) =>
              <span key={stage} className="flex items-center gap-2">
                {i > 0 && <span className="text-blue-400">→</span>}
                <span className="rounded-md border border-slate-600 p-1.5">{stage}</span>
              </span>)}
          </div>
          <figcaption className="mt-2">As dependências seguem estas etapas. O trabalho dos grupos pode se sobrepor, mas especialistas e votação entre pares dentro de cada grupo são executados em sequência. O nó coordenador aparece acima das equipes para navegação, e não para indicar que a síntese é executada primeiro.</figcaption>
        </figure>
        {coordination.orchestrator && <div className="max-w-sm mx-auto mt-5">
          <button type="button" onClick={() => selectAgent(coordination.orchestrator.id)}
            aria-pressed={agent?.id === coordination.orchestrator.id}
            className="w-full text-left rounded-xl border border-blue-500/60 bg-slate-800/70 p-3 flex items-center gap-3 focus-visible:outline focus-visible:outline-amber-300">
            <Identity agent={coordination.orchestrator} />
            <span className="min-w-0"><span className="font-semibold text-sm text-slate-100 block">{coordination.orchestrator.display_name}</span>
              <span className="text-xs text-slate-400">{orchestratorEvent?.type === 'MASTER_MANAGER_COMPLETE' ? 'Síntese registrada' : orchestratorEvent ? 'Síntese iniciada' : 'Aguardando a etapa de síntese'}</span>
            </span>
          </button>
          <div aria-hidden="true" className="h-6 w-px bg-blue-500/50 mx-auto" />
        </div>}
        {!roster.length && <div role="note" className="border border-amber-500/40 rounded-lg p-4 text-sm text-amber-300">
          A lista de agentes configurada está indisponível. Atualize a sessão autorizada; nenhum agente fictício é exibido.
        </div>}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {roster.map(cluster => {
            const scoped = current.filter(e => e.cluster === cluster.id)
            const finished = scoped.some(e => e.type === 'CLUSTER_COMPLETE')
            const active = !finished && scoped.length > 0
            return <div key={cluster.id} className="rounded-xl border border-slate-700/90 bg-slate-800/40 p-3 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-3">
                <div><h4 className="text-sm font-semibold text-slate-100">{cluster.name}</h4>
                  <p className="text-xs text-slate-400">{finished ? 'Síntese do grupo registrada' : active ? 'Atividade registrada' : 'Nenhuma execução observada'}</p>
                </div>
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: finished ? '#34d399' : active ? '#60a5fa' : '#64748b' }} />
              </div>
              <div className="space-y-1.5">
                {(cluster.agents || []).map(member => {
                  const activity = agentActivity(member, current)
                  return <button type="button" key={member.id} onClick={() => selectAgent(member.id)}
                    aria-pressed={agent?.id === member.id}
                    className="w-full flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-900/50 px-2 py-2 text-left hover:border-blue-400 focus-visible:outline focus-visible:outline-amber-300 aria-pressed:border-blue-400">
                    <Identity agent={member} />
                    <span className="min-w-0"><span className="text-xs text-slate-100 block break-words">{member.display_name}</span>
                      <span className="text-[11px] text-slate-400 block">{activity.label}</span></span>
                  </button>
                })}
                {cluster.manager && <button type="button" onClick={() => selectAgent(cluster.manager.id)} aria-pressed={agent?.id === cluster.manager.id}
                  className="w-full flex items-center gap-2 rounded-lg border border-blue-900/50 bg-slate-900/30 px-2 py-2 text-left focus-visible:outline focus-visible:outline-amber-300 aria-pressed:border-blue-400">
                  <Identity agent={cluster.manager} />
                  <span className="min-w-0"><span className="text-xs text-slate-200 block break-words">{cluster.manager.display_name}</span>
                    <span className="text-[11px] text-slate-400">Coordenador · {finished ? 'Síntese registrada' : 'Nenhuma conclusão registrada'}</span></span>
                </button>}
              </div>
              <p className="mt-2 text-[11px] text-slate-500">Análises dos especialistas → votos entre pares → síntese do coordenador</p>
            </div>
          })}
        </div>
        {coordination.adversarial && <div className="mt-4 rounded-lg border border-pink-800/70 bg-pink-950/15 p-3">
          <button type="button" onClick={() => selectAgent(coordination.adversarial.id)} aria-pressed={agent?.id === coordination.adversarial.id}
            className="flex w-full items-center gap-3 text-left rounded-md focus-visible:outline focus-visible:outline-amber-300">
            <Identity agent={coordination.adversarial} />
            <span><span className="text-sm font-medium text-slate-100">{coordination.adversarial.display_name}</span>
              <span className="block text-xs text-slate-400">{adversaryEvent?.type === 'DEVILS_ADVOCATE_COMPLETE' ? 'Conclusões adversariais registradas' : adversaryEvent ? 'Revisão adversarial iniciada' : 'Aguardando as análises dos grupos'}</span></span>
          </button>
          <p className="mt-2 text-xs text-slate-400">Revisão adversarial separada; não substitui fontes verificadas nem aprovação humana.</p>
        </div>}
      </section>
      <aside id="gilberto-inspector" aria-label="Inspetor da execução" className="min-w-0 rounded-xl border border-slate-700 bg-[#0b1728] p-4 sm:p-5 scroll-mt-24">
        <div className="flex items-center justify-between gap-2 mb-3">
          <h3 className="font-semibold text-slate-100">Inspetor da execução</h3>
          <span className="text-xs text-slate-400 flex items-center gap-1"><Clock3 size={12} /> Somente registros</span>
        </div>
        <div role="tablist" aria-label="Visões do inspetor" className="flex flex-wrap gap-1 mb-4">
          {TABS.map(t => <button key={t.id} type="button" id={'inspector-tab-' + t.id}
            role="tab" aria-selected={tab === t.id} aria-controls="gilberto-inspector-panel" onClick={() => setTab(t.id)}
            className={'rounded-md px-2.5 py-2 text-xs flex items-center gap-1 focus-visible:outline focus-visible:outline-amber-300 ' +
              (tab === t.id ? 'bg-blue-800 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700')}>
            <t.icon size={13} /> {t.label}
          </button>)}
        </div>
        <div role="tabpanel" id="gilberto-inspector-panel" aria-labelledby={'inspector-tab-' + tab} className="min-w-0">
          <InspectPanel tab={tab} agent={agent} events={events} current={current}
            metrics={executionMetrics} status={status} sessionId={sessionId}
            connectionState={connectionState} pendingCount={pendingGates.length} />
        </div>
        {pendingGates.length > 0 && <p role="status" className="mt-4 flex items-start gap-2 text-xs text-amber-300">
          <AlertCircle size={14} /> {pendingGates.length} etapa(s) obrigatória(s) de revisão jurídica pendente(s). As decisões permanecem na mesa de revisão autorizada.
        </p>}
      </aside>
    </div>
    <p className="text-xs text-slate-500 flex items-center gap-2"><Scale size={13} /> Somente direito brasileiro. A visualização é uma projeção do registro em tempo real, e não uma verificação jurídica. Um envio pausado ainda pode ter trabalho em curso no provedor.</p>
  </section>
}
