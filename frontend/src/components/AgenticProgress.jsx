import { Activity, Check, Circle, Clock3, Loader, Radio, RefreshCw, ShieldAlert } from 'lucide-react'

const STAGES = [
  { id: 'clusters', label: 'Revisão especializada em paralelo', hint: 'As frentes jurídicas configuradas revisam o documento por meio de requisições cadenciadas ao modelo.' },
  { id: 'adversarial', label: 'Revisão adversarial', hint: 'Um revisor separado procura lacunas, pressupostos e fundamentações frágeis.' },
  { id: 'synthesis', label: 'Síntese do coordenador', hint: 'O coordenador concilia as conclusões e prepara a análise consolidada.' },
  { id: 'checks', label: 'Controles de qualidade e revisão humana', hint: 'As etapas de risco são apresentadas para sua revisão quando a análise as aciona.' },
  { id: 'result', label: 'Análise final', hint: 'O relatório completo aparecerá aqui quando a execução estiver pronta.' },
]

const CLUSTERS = [
  ['foundation', 'Fundamentos'],
  ['financial_risk', 'Risco financeiro'],
  ['mitigation_exit', 'Mitigação e saída'],
  ['compliance', 'Conformidade'],
  ['strategy', 'Estratégia'],
]

function eventCopy(event) {
  const cluster = event.cluster_name || (typeof event.cluster === 'string' ? event.cluster.replaceAll('_', ' ') : null) || 'Equipe especializada'
  const messages = {
    DEBATE_START: ['Análise iniciada', 'O documento foi aceito e as equipes especializadas estão sendo coordenadas.'],
    ROUND_START: [`Rodada ${event.round || ''} iniciada`.replace(/\s+/g, ' '), 'As frentes de análise revisam o documento por meio de requisições cadenciadas ao modelo.'],
    CLUSTER_START: [`Revisão de ${cluster} iniciada`, 'Esta frente examina as questões jurídicas que lhe foram atribuídas.'],
    AGENT_THINKING: [`${event.agent || 'Um especialista'} está revisando`, 'O agente está preparando suas conclusões para esta frente.'],
    AGENT_ANALYSIS_COMPLETE: [`${event.agent || 'Um especialista'} apresentou conclusões`, 'Suas conclusões estão disponíveis para a revisão da equipe.'],
    AGENT_VOTING: [`${event.agent || 'Um especialista'} está avaliando as conclusões dos pares`, 'A equipe compara conclusões e identifica divergências.'],
    AGENT_VOTE_CAST: [`${event.agent || 'Um especialista'} concluiu a revisão entre pares`, 'O agente apresentou sua revisão.'],
    CLUSTER_COMPLETE: [`Conclusões de ${cluster} prontas`, 'Esta frente concluiu sua análise.'],
    DEVILS_ADVOCATE_START: ['Revisão adversarial iniciada', 'O revisor testa pressupostos e procura lacunas nas conclusões dos especialistas.'],
    DEVILS_ADVOCATE_COMPLETE: ['Revisão adversarial concluída', `${event.identified_gaps?.length || 0} possível(is) lacuna(s) identificada(s) para a síntese.`],
    MASTER_MANAGER_START: ['Síntese do coordenador iniciada', 'O coordenador concilia conclusões, divergências e sinais de risco.'],
    MASTER_MANAGER_COMPLETE: ['Análise consolidada preparada', 'O coordenador apresentou a conclusão principal e a análise que a fundamenta.'],
    GATE_TRIGGERED: [`Revisão humana solicitada${event.gate_number ? ` · Etapa ${event.gate_number}` : ''}`, event.trigger?.description || event.record?.trigger?.description || 'Um ponto de controle de risco exige sua atenção antes que a análise prossiga.'],
    GATE_RESOLVED: [`Etapa ${event.gate_number || ''} revisada`.replace(/\s+/g, ' '), 'Sua decisão foi registrada.'],
    ROUND_COMPLETE: [`Rodada ${event.round || ''} concluída`.replace(/\s+/g, ' '), 'O resumo da rodada está pronto e o debate pode passar à próxima etapa.'],
    DEBATE_COMPLETE: ['Execução da análise concluída', 'O resultado está sendo preparado para revisão.'],
    PROVIDER_WAIT: ['Aguardando capacidade do provedor', 'A requisição está na fila para respeitar os limites configurados do provedor.'],
    CLUSTER_FAILED: [`Falha na revisão de ${cluster}`, `Código do motivo: ${event.code || 'unexpected_failure'}. A frente incompleta não pode ser usada em uma análise jurídica final.`],
    ERROR: ['A análise foi interrompida', event.message || 'O serviço retornou um erro.'],
  }
  return messages[event.type] || [event.type?.replaceAll('_', ' ').toLowerCase() || 'Atualização da análise', 'O fluxo da análise registrou uma nova atualização.']
}

function eventTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function deriveStage(events) {
  const has = (type) => events.some(event => event.type === type)
  if (has('DEBATE_COMPLETE')) return 4
  if (has('MASTER_MANAGER_START') || has('MASTER_MANAGER_COMPLETE')) return 3
  if (has('DEVILS_ADVOCATE_START') || has('DEVILS_ADVOCATE_COMPLETE')) return 2
  return 0
}

function currentRoundEvents(events) {
  let latestStart = -1
  for (let index = 0; index < events.length; index += 1) {
    if (events[index].type === 'ROUND_START' || events[index].type === 'FEEDBACK_RECEIVED') latestStart = index
  }
  return latestStart >= 0 ? events.slice(latestStart) : events
}

export function AgenticProgress({ events = [], rounds = [], totalRounds = 1, connectionState, lastEventAt, onReconnect, status = 'running' }) {
  const stopped = status === 'error' || status === 'cancelled'
  const stopping = status === 'cancellation_requested'
  const activeEvents = currentRoundEvents(events)
  const currentStage = deriveStage(activeEvents)
  const roundCount = Math.max(1, Number(totalRounds) || 1)
  const currentRound = Math.min(roundCount, rounds.length + 1)
  const completedClusters = new Set(activeEvents.filter(event => event.type === 'CLUSTER_COMPLETE').map(event => event.cluster))
  const latest = events.slice(-7).reverse()
  const configured = events.find(event => event.type === 'DEBATE_START')?.active_clusters
  const visibleClusters = configured ? CLUSTERS.filter(([id]) => configured.includes(id)) : []
  const connection = stopped && connectionState === 'closed'
    ? { label: 'Atualizações encerradas após falha', className: 'text-red-300', icon: <ShieldAlert size={13} /> }
    : {
    connecting: { label: 'Conectando às atualizações em tempo real', className: 'text-amber-300', icon: <Loader size={13} className="animate-spin" /> },
    connected: { label: 'Atualizações em tempo real conectadas', className: 'text-emerald-300', icon: <Radio size={13} /> },
    reconnecting: { label: 'Reconectando às atualizações em tempo real', className: 'text-amber-300', icon: <Loader size={13} className="animate-spin" /> },
    disconnected: { label: 'Atualizações em tempo real desconectadas', className: 'text-red-300', icon: <ShieldAlert size={13} /> },
    closed: { label: 'Atualizações da execução encerradas', className: 'text-slate-400', icon: <Check size={13} /> },
    idle: { label: 'Preparando as atualizações em tempo real', className: 'text-slate-400', icon: <Clock3 size={13} /> },
  }[connectionState] || { label: 'Preparando as atualizações em tempo real', className: 'text-slate-400', icon: <Clock3 size={13} /> }

  return (
    <section className="space-y-5">
      <div className="card p-5 sm:p-6 border border-gold-500/25">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-gold-400">Análise em tempo real</p>
            <p className="sr-only" role="status">{stopped ? 'Análise interrompida' : STAGES[currentStage].label}</p>
            <h2 className="font-display text-2xl text-slate-100 mt-1">{stopping ? 'Cancelamento solicitado — encerrando o trabalho' : stopped ? 'Análise interrompida — revisão incompleta' : 'Suas equipes jurídicas estão trabalhando'}</h2>
            <p className="text-sm text-slate-400 mt-2 max-w-2xl">{stopped ? 'Somente as conclusões já recebidas são exibidas. Esta não é uma análise jurídica aceita nem integralmente verificada.' : 'Acompanhe aqui as etapas relevantes do debate. A análise final e eventuais pedidos de revisão aparecerão nesta área de trabalho.'}</p>
          </div>
          <div className="rounded-xl border border-slate-700/70 bg-slate-900/60 px-4 py-3 min-w-44">
            <div className={`flex items-center gap-2 text-xs ${connection.className}`}>
              {connection.icon}<span>{connection.label}</span>
            </div>
            <p className="text-xs text-slate-500 mt-2">{lastEventAt ? `Última atualização às ${eventTime(lastEventAt)}` : 'Aguardando a primeira atualização de progresso'}</p>
            {(connectionState === 'disconnected' || connectionState === 'reconnecting') && (
              <button onClick={onReconnect} className="mt-3 inline-flex items-center gap-1.5 text-xs text-gold-300 hover:text-gold-200" type="button">
                <RefreshCw size={12} /> Reconectar
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3 mt-6">
          {STAGES.map((stage, index) => {
            const done = index < currentStage
            const active = !stopped && index === currentStage
            return (
              <div key={stage.id} className={`rounded-xl border p-3 min-h-28 ${active ? 'border-gold-500/50 bg-gold-500/10' : done ? 'border-emerald-500/25 bg-emerald-500/5' : 'border-slate-700/60 bg-slate-900/40'}`}>
                <div className="flex items-center gap-2">
                  {done ? <Check size={15} className="text-emerald-400" /> : active ? <Loader size={15} className="text-gold-300 animate-spin" /> : <Circle size={14} className="text-slate-600" />}
                  <span className={`text-xs font-medium ${active ? 'text-gold-200' : done ? 'text-emerald-300' : 'text-slate-400'}`}>{stage.label}</span>
                </div>
                <p className="text-[11px] leading-relaxed text-slate-500 mt-2">{stage.hint}</p>
              </div>
            )
          })}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-700/50 mt-5 pt-4 text-xs">
          <span className="text-slate-400">Rodada do debate <strong className="text-slate-200">{currentRound} de {totalRounds || 1}</strong></span>
          <span className="text-slate-500">{rounds.length} {rounds.length === 1 ? 'rodada resumida' : 'rodadas resumidas'} · {events.length} atualizações de progresso</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.8fr)] gap-5">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={15} className="text-gold-400" />
            <h3 className="font-display text-lg text-slate-100">O que os agentes já fizeram</h3>
          </div>
          {latest.length ? (
            <ol className="space-y-0">
              {latest.map((event, index) => {
                const [title, description] = eventCopy(event)
                return <li key={`${event.timestamp || 'event'}-${events.length - index}`} className="flex gap-3 pb-4 last:pb-0">
                  <div className="flex flex-col items-center">
                    <span className={`mt-1 h-2.5 w-2.5 rounded-full ${event.type === 'ERROR' ? 'bg-red-400' : event.type === 'GATE_TRIGGERED' ? 'bg-amber-400' : index === 0 ? 'bg-gold-300' : 'bg-slate-600'}`} />
                    {index < latest.length - 1 && <span className="w-px flex-1 bg-slate-700/70 mt-1" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <p className="text-sm text-slate-200">{title}</p>
                      <time className="text-[11px] text-slate-600">{eventTime(event.timestamp)}</time>
                    </div>
                    <p className="text-xs leading-relaxed text-slate-500 mt-1">{description}</p>
                  </div>
                </li>
              })}
            </ol>
          ) : (
            <div className="flex items-center gap-3 py-5 text-sm text-slate-400">
              <Loader size={16} className="animate-spin text-gold-400" />
              O servidor aceitou a execução. Aguardando o primeiro evento dos agentes…
            </div>
          )}
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">⚖️</span>
            <h3 className="font-display text-lg text-slate-100">Equipes de revisão em paralelo</h3>
          </div>
          <div className="space-y-2">
            {visibleClusters.map(([id, name]) => {
              const complete = completedClusters.has(id)
              const active = activeEvents.some(event => event.cluster === id && ['CLUSTER_START', 'AGENT_THINKING', 'AGENT_VOTING'].includes(event.type)) && !complete
              return <div key={id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/50 bg-slate-900/40 px-3 py-2.5">
                <span className="text-sm text-slate-300">{name}</span>
                <span className={`inline-flex items-center gap-1.5 text-xs ${complete ? 'text-emerald-300' : active ? 'text-gold-300' : 'text-slate-500'}`}>
                  {complete ? <Check size={13} /> : active ? <Loader size={12} className="animate-spin" /> : <Circle size={11} />}
                  {complete ? 'Conclusões prontas' : active ? 'Em andamento' : 'Na fila'}
                </span>
              </div>
            })}
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500 mt-4">O progresso reflete os eventos recebidos do servidor; nenhum percentual ou prazo de conclusão é estimado.</p>
        </div>
      </div>
    </section>
  )
}

