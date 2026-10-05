import React, { useMemo } from 'react'
import { Brain, CheckCircle, Vote, Loader, AlertTriangle } from 'lucide-react'

const CLUSTER_CONFIG = {
  foundation: { name: 'Foundation', icon: '🏛️', color: '#6366f1' },
  financial_risk: { name: 'Financial Risk', icon: '💰', color: '#f59e0b' },
  mitigation_exit: { name: 'Mitigation & Exit', icon: '🛡️', color: '#10b981' },
  compliance: { name: 'Compliance', icon: '⚖️', color: '#8b5cf6' },
  strategy: { name: 'Strategy', icon: '♟️', color: '#ec4899' },
}

function getClusterStatus(clusterId, events) {
  const clusterEvents = events.filter(e => e.cluster === clusterId)
  if (clusterEvents.some(e => e.type === 'CLUSTER_COMPLETE')) return 'complete'
  if (clusterEvents.some(e => e.type === 'AGENT_VOTING')) return 'voting'
  if (clusterEvents.some(e => e.type === 'AGENT_THINKING')) return 'running'
  return 'pending'
}

function getClusterScore(clusterId, events) {
  const complete = events.find(e => e.type === 'CLUSTER_COMPLETE' && e.cluster === clusterId)
  const value = Number(complete?.summary?.aggregated_score)
  return Number.isFinite(value) ? Math.min(10, Math.max(0, value)) : null
}

function getClusterConfidence(clusterId, events) {
  const complete = events.find(e => e.type === 'CLUSTER_COMPLETE' && e.cluster === clusterId)
  const value = Number(complete?.summary?.confidence_aggregate)
  return Number.isFinite(value) ? Math.min(5, Math.max(0, value)) : null
}

function getAgentStatuses(clusterId, events) {
  const agents = {}
  events
    .filter(e => e.cluster === clusterId)
    .forEach(e => {
      if (e.type === 'AGENT_THINKING') {
        agents[e.agent] = { status: 'thinking', role: e.agent }
      } else if (e.type === 'AGENT_ANALYSIS_COMPLETE') {
        agents[e.agent] = { status: 'done', role: e.agent, parsed: e.parsed }
      } else if (e.type === 'AGENT_VOTING') {
        agents[e.agent] = { ...agents[e.agent], status: 'voting' }
      } else if (e.type === 'AGENT_VOTE_CAST') {
        agents[e.agent] = { ...agents[e.agent], status: 'voted' }
      }
    })
  return Object.values(agents)
}

const STATUS_CONFIG = {
  pending: { label: 'Waiting', color: 'slate', animated: false },
  running: { label: 'Analyzing', color: 'gold', animated: true },
  voting: { label: 'Voting', color: 'blue', animated: true },
  complete: { label: 'Complete', color: 'green', animated: false },
}

export function AgentClusterPanel({ events }) {
  const clusters = useMemo(() => {
    return Object.entries(CLUSTER_CONFIG).map(([id, config]) => ({
      id,
      ...config,
      status: getClusterStatus(id, events),
      score: getClusterScore(id, events),
      confidence: getClusterConfidence(id, events),
      agents: getAgentStatuses(id, events),
    }))
  }, [events])

  const daEvent = events.find(e => e.type === 'DEVILS_ADVOCATE_COMPLETE')
  const daStatus = events.some(e => e.type === 'DEVILS_ADVOCATE_START')
    ? daEvent ? 'complete' : 'running'
    : 'pending'

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {clusters.map(cluster => (
          <ClusterCard key={cluster.id} cluster={cluster} />
        ))}

        {/* Devil's Advocate Card */}
        <DevilsAdvocateCard status={daStatus} result={daEvent} />
      </div>
    </div>
  )
}

function ClusterCard({ cluster }) {
  const status = STATUS_CONFIG[cluster.status]

  return (
    <div
      className="card p-4 border-2 transition-all duration-500"
      style={{ borderColor: cluster.status === 'complete' ? cluster.color : undefined }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{cluster.icon}</span>
          <div>
            <h4 className="text-sm font-medium text-slate-100">{cluster.name}</h4>
            <div className={`flex items-center gap-1 text-xs text-${status.color}-400`}>
              {status.animated && <Loader size={10} className="animate-spin" />}
              <span>{status.label}</span>
            </div>
          </div>
        </div>

        {cluster.score !== null && (
          <ScoreRing score={cluster.score} color={cluster.color} size={48} />
        )}
      </div>

      {/* Confidence bar */}
      {cluster.confidence !== null && (
        <div className="mb-3">
          <div className="flex justify-between text-[10px] text-slate-500 mb-1">
            <span>Confidence</span>
            <span className={cluster.confidence < 3 ? 'text-yellow-400' : 'text-green-400'}>
              {cluster.confidence}/5
            </span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all duration-1000 ${
                cluster.confidence < 3 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${(cluster.confidence / 5) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Agents */}
      <div className="space-y-1.5">
        {cluster.agents.map(agent => (
          <AgentRow key={agent.role} agent={agent} />
        ))}
        {cluster.agents.length === 0 && cluster.status === 'pending' && (
          <p className="text-xs text-slate-600 italic">Waiting to start…</p>
        )}
      </div>
    </div>
  )
}

function AgentRow({ agent }) {
  const icons = {
    thinking: <Brain size={12} className="text-gold-400 animate-pulse" />,
    done: <CheckCircle size={12} className="text-green-400" />,
    voting: <Vote size={12} className="text-blue-400 animate-pulse" />,
    voted: <Vote size={12} className="text-purple-400" />,
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      {icons[agent.status] || <div className="w-3 h-3 rounded-full bg-slate-700" />}
      <span className="text-slate-400 truncate">{agent.role}</span>
    </div>
  )
}

function ScoreRing({ score, color, size = 48 }) {
  const radius = (size - 4) / 2
  const circumference = 2 * Math.PI * radius
  const numericScore = Number(score)
  const safeScore = Number.isFinite(numericScore) ? Math.min(10, Math.max(0, numericScore)) : 0
  const fill = (safeScore / 10) * circumference

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#1e293b" strokeWidth="3"
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${fill} ${circumference}`}
          strokeLinecap="round"
          className="transition-all duration-1000"
        />
      </svg>
      <span
        className="absolute inset-0 flex items-center justify-center text-xs font-bold"
        style={{ color }}
      >
        {safeScore.toFixed(1)}
      </span>
    </div>
  )
}

function DevilsAdvocateCard({ status, result }) {
  const gapValue = result?.gap_severity_score
  const sadValue = result?.sad_score
  const gapScore = gapValue == null || !Number.isFinite(Number(gapValue)) ? null : Math.min(10, Math.max(0, Number(gapValue)))
  const sadScore = sadValue == null || !Number.isFinite(Number(sadValue)) ? null : Math.min(5, Math.max(0, Number(sadValue)))
  const unaskedQuestions = Array.isArray(result?.unasked_questions) ? result.unasked_questions : []
  const biases = Array.isArray(result?.cognitive_biases_detected) ? result.cognitive_biases_detected : []
  const identifiedGaps = Array.isArray(result?.identified_gaps) ? result.identified_gaps : []

  return (
    <div className={`card p-4 border-2 ${
      status === 'complete'
        ? (gapScore > 6 || sadScore >= 4) ? 'border-red-500/50' : 'border-green-500/30'
        : 'border-slate-700'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">👿</span>
          <div>
            <h4 className="text-sm font-medium text-slate-100">Analista Adversarial</h4>
            <div className={`flex items-center gap-1 text-xs ${
              status === 'complete' ? 'text-green-400' : status === 'running' ? 'text-gold-400' : 'text-slate-500'
            }`}>
              {status === 'running' && <Loader size={10} className="animate-spin" />}
              <span>{status === 'complete' ? 'Auditoria completa' : status === 'running' ? 'Auditando…' : 'Aguardando'}</span>
            </div>
          </div>
        </div>

        {sadScore !== null && (
          <div className="text-right">
            <div className={`text-2xl font-bold ${sadScore >= 4 ? 'text-red-400' : sadScore >= 3 ? 'text-yellow-400' : 'text-green-400'}`}>
              SAD {sadScore.toFixed(1)}
            </div>
            <div className="text-[10px] text-slate-500">/5</div>
          </div>
        )}
      </div>

      {gapScore !== null && (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs text-slate-500">Severidade:</span>
          <div className={`text-sm font-bold ${gapScore > 6 ? 'text-red-400' : 'text-green-400'}`}>
            {gapScore.toFixed(1)}/10
          </div>
        </div>
      )}

      {biases.length > 0 && (
        <div className="mb-2">
          <p className="text-[10px] text-slate-500 mb-1">Vieses detectados:</p>
          <div className="flex flex-wrap gap-1">
            {biases.slice(0, 3).map((b, i) => (
              <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">{b}</span>
            ))}
          </div>
        </div>
      )}

      {identifiedGaps.length > 0 && (
        <div className="space-y-1">
          {identifiedGaps.filter(gap => gap && typeof gap === 'object').slice(0, 3).map((gap, i) => (
            <div key={i} className="flex items-start gap-1.5 text-xs">
              <AlertTriangle size={10} className="text-yellow-400 mt-0.5 flex-shrink-0" />
              <div>
                <span className="text-slate-400 line-clamp-1">{gap.description}</span>
                {gap.brazilian_context && (
                  <span className="text-[10px] text-yellow-600 block">{gap.brazilian_context}</span>
                )}
              </div>
            </div>
          ))}
          {identifiedGaps.length > 3 && (
            <p className="text-[10px] text-slate-500">+{identifiedGaps.length - 3} lacunas adicionais</p>
          )}
        </div>
      )}

      {unaskedQuestions.length > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-700/30">
          <p className="text-[10px] text-slate-500 mb-1">Perguntas não formuladas:</p>
          {unaskedQuestions.slice(0, 2).map((q, i) => (
            <p key={i} className="text-[10px] text-slate-400 italic">"{q}"</p>
          ))}
        </div>
      )}
    </div>
  )
}
