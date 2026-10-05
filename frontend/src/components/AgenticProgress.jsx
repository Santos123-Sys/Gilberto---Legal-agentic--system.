import { Activity, Check, Circle, Clock3, Loader, Radio, RefreshCw, ShieldAlert } from 'lucide-react'

const STAGES = [
  { id: 'clusters', label: 'Parallel specialist review', hint: 'Five legal workstreams examine the document at the same time.' },
  { id: 'adversarial', label: 'Adversarial review', hint: 'A separate reviewer looks for gaps, assumptions and weak reasoning.' },
  { id: 'synthesis', label: 'Manager synthesis', hint: 'The manager reconciles findings and prepares the consolidated analysis.' },
  { id: 'checks', label: 'Quality and human checks', hint: 'Risk gates are surfaced for your review when the analysis triggers them.' },
  { id: 'result', label: 'Final analysis', hint: 'The complete report will appear here when the run is ready.' },
]

const CLUSTERS = [
  ['foundation', 'Foundation'],
  ['financial_risk', 'Financial risk'],
  ['mitigation_exit', 'Mitigation & exit'],
  ['compliance', 'Compliance'],
  ['strategy', 'Strategy'],
]

function eventCopy(event) {
  const cluster = event.cluster_name || (typeof event.cluster === 'string' ? event.cluster.replaceAll('_', ' ') : null) || 'Specialist team'
  const messages = {
    DEBATE_START: ['Analysis started', 'The document was accepted and the specialist teams are being coordinated.'],
    ROUND_START: [`Round ${event.round || ''} started`.trim(), 'The teams are reviewing the document in parallel.'],
    CLUSTER_START: [`${cluster} review started`, 'This workstream is examining its assigned legal issues.'],
    AGENT_THINKING: [`${event.agent || 'A specialist'} is reviewing`, 'The agent is preparing its findings for this workstream.'],
    AGENT_ANALYSIS_COMPLETE: [`${event.agent || 'A specialist'} submitted findings`, 'Its findings are now available to the team review.'],
    AGENT_VOTING: [`${event.agent || 'A specialist'} is checking peer findings`, 'The team is comparing conclusions and identifying disagreements.'],
    AGENT_VOTE_CAST: [`${event.agent || 'A specialist'} completed peer review`, 'The agent has submitted its review.'],
    CLUSTER_COMPLETE: [`${cluster} findings are ready`, 'This workstream has completed its analysis.'],
    DEVILS_ADVOCATE_START: ['Adversarial review started', 'The reviewer is testing assumptions and looking for gaps across the specialist findings.'],
    DEVILS_ADVOCATE_COMPLETE: ['Adversarial review complete', `${event.identified_gaps?.length || 0} potential gaps were identified for the synthesis.`],
    MASTER_MANAGER_START: ['Manager synthesis started', 'The manager is reconciling findings, disagreements and risk signals.'],
    MASTER_MANAGER_COMPLETE: ['Consolidated analysis prepared', 'The manager has returned the main conclusion and supporting analysis.'],
    GATE_TRIGGERED: [`Human review requested${event.gate_number ? ` · Gate ${event.gate_number}` : ''}`, event.trigger?.description || event.record?.trigger?.description || 'A risk checkpoint needs your attention before the analysis can proceed.'],
    GATE_RESOLVED: [`Gate ${event.gate_number || ''} reviewed`.trim(), 'Your decision has been recorded.'],
    ROUND_COMPLETE: [`Round ${event.round || ''} complete`.trim(), 'The round summary is ready and the debate can move to its next step.'],
    DEBATE_COMPLETE: ['Analysis run complete', 'The result is being prepared for review.'],
    ERROR: ['The analysis stopped', event.message || 'The service returned an error.'],
  }
  return messages[event.type] || [event.type?.replaceAll('_', ' ').toLowerCase() || 'Analysis update', 'The analysis workflow recorded a new update.']
}

function eventTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
    if (events[index].type === 'ROUND_START') latestStart = index
  }
  return latestStart >= 0 ? events.slice(latestStart) : events
}

export function AgenticProgress({ events = [], rounds = [], totalRounds = 1, connectionState, lastEventAt, onReconnect }) {
  const activeEvents = currentRoundEvents(events)
  const currentStage = deriveStage(activeEvents)
  const roundCount = Math.max(1, Number(totalRounds) || 1)
  const currentRound = Math.min(roundCount, rounds.length + 1)
  const completedClusters = new Set(activeEvents.filter(event => event.type === 'CLUSTER_COMPLETE').map(event => event.cluster))
  const latest = events.slice(-7).reverse()
  const connection = {
    connecting: { label: 'Connecting to live updates', className: 'text-amber-300', icon: <Loader size={13} className="animate-spin" /> },
    connected: { label: 'Live updates connected', className: 'text-emerald-300', icon: <Radio size={13} /> },
    reconnecting: { label: 'Reconnecting to live updates', className: 'text-amber-300', icon: <Loader size={13} className="animate-spin" /> },
    disconnected: { label: 'Live updates disconnected', className: 'text-red-300', icon: <ShieldAlert size={13} /> },
    closed: { label: 'Run updates finished', className: 'text-slate-400', icon: <Check size={13} /> },
    idle: { label: 'Preparing live updates', className: 'text-slate-400', icon: <Clock3 size={13} /> },
  }[connectionState] || { label: 'Preparing live updates', className: 'text-slate-400', icon: <Clock3 size={13} /> }

  return (
    <section className="space-y-5" aria-live="polite">
      <div className="card p-5 sm:p-6 border border-gold-500/25">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.18em] text-gold-400">Live analysis</p>
            <h2 className="font-display text-2xl text-slate-100 mt-1">Your legal teams are working</h2>
            <p className="text-sm text-slate-400 mt-2 max-w-2xl">Follow the meaningful stages of the debate here. The final analysis and any review requests will appear in this workspace.</p>
          </div>
          <div className="rounded-xl border border-slate-700/70 bg-slate-900/60 px-4 py-3 min-w-44">
            <div className={`flex items-center gap-2 text-xs ${connection.className}`}>
              {connection.icon}<span>{connection.label}</span>
            </div>
            <p className="text-xs text-slate-500 mt-2">{lastEventAt ? `Last update ${eventTime(lastEventAt)}` : 'Waiting for the first progress update'}</p>
            {(connectionState === 'disconnected' || connectionState === 'reconnecting') && (
              <button onClick={onReconnect} className="mt-3 inline-flex items-center gap-1.5 text-xs text-gold-300 hover:text-gold-200" type="button">
                <RefreshCw size={12} /> Reconnect
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3 mt-6">
          {STAGES.map((stage, index) => {
            const done = index < currentStage
            const active = index === currentStage
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
          <span className="text-slate-400">Debate round <strong className="text-slate-200">{currentRound} of {totalRounds || 1}</strong></span>
          <span className="text-slate-500">{rounds.length} {rounds.length === 1 ? 'round' : 'rounds'} summarized · {events.length} progress updates</span>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.8fr)] gap-5">
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Activity size={15} className="text-gold-400" />
            <h3 className="font-display text-lg text-slate-100">What the agents have done</h3>
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
              The backend accepted the run. Waiting for the first agent event…
            </div>
          )}
        </div>

        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-lg">⚖️</span>
            <h3 className="font-display text-lg text-slate-100">Parallel review teams</h3>
          </div>
          <div className="space-y-2">
            {CLUSTERS.map(([id, name]) => {
              const complete = completedClusters.has(id)
              const active = activeEvents.some(event => event.cluster === id && ['CLUSTER_START', 'AGENT_THINKING', 'AGENT_VOTING'].includes(event.type)) && !complete
              return <div key={id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-700/50 bg-slate-900/40 px-3 py-2.5">
                <span className="text-sm text-slate-300">{name}</span>
                <span className={`inline-flex items-center gap-1.5 text-xs ${complete ? 'text-emerald-300' : active ? 'text-gold-300' : 'text-slate-500'}`}>
                  {complete ? <Check size={13} /> : active ? <Loader size={12} className="animate-spin" /> : <Circle size={11} />}
                  {complete ? 'Findings ready' : active ? 'Working' : 'Queued'}
                </span>
              </div>
            })}
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500 mt-4">Progress reflects events received from the backend; no percentage or completion time is estimated.</p>
        </div>
      </div>
    </section>
  )
}
