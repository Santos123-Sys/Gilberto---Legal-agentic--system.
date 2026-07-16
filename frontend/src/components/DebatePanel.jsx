import { useRef, useEffect } from 'react'
import { AgentCard } from './AgentCard'
import { Activity, Zap, Shield, Scale } from 'lucide-react'

const EVENT_LABEL = {
  DEBATE_START: { icon: '🚀', label: 'Debate started', color: 'text-gold-400' },
  ROUND_START: { icon: '🔔', label: 'Round started', color: 'text-blue-400' },
  PHASE_START: { icon: '▶', label: 'Phase started', color: 'text-slate-400' },
  AGENT_THINKING: { icon: '💭', label: 'Agent analyzing', color: 'text-gold-300' },
  AGENT_ANALYSIS_COMPLETE: { icon: '✅', label: 'Analysis complete', color: 'text-green-400' },
  AGENT_VOTING: { icon: '🗳️', label: 'Peer review', color: 'text-blue-300' },
  AGENT_VOTE_CAST: { icon: '📊', label: 'Scores submitted', color: 'text-purple-400' },
  ROUND_COMPLETE: { icon: '🏁', label: 'Round complete', color: 'text-gold-400' },
  DEBATE_COMPLETE: { icon: '⚖️', label: 'Debate complete', color: 'text-green-300' },
  FEEDBACK_AGENT_CREATED: { icon: '🆕', label: 'Feedback agent created', color: 'text-cyan-400' },
  ERROR: { icon: '❌', label: 'Error', color: 'text-red-400' },
}

const PHASE_LABEL = { analysis: 'Analysis Phase', voting: 'Peer Review & Voting', aggregation: 'Synthesis & Aggregation' }

function RiskBadge({ level }) {
  if (!level) return null
  const cfg = {
    critical: 'risk-critical',
    high: 'risk-high',
    medium: 'risk-medium',
    low: 'risk-low',
  }[level.toLowerCase()] || 'risk-medium'
  return <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${cfg}`}>{level.toUpperCase()} RISK</span>
}

function RoundSummaryCard({ summary, roundNum }) {
  if (!summary) return null
  const isRaw = !!summary.raw_content

  return (
    <div className="card border border-gold-500/20 bg-gold-500/5 p-5 space-y-4 animate-slide-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Scale size={16} className="text-gold-400" />
          <span className="text-sm font-semibold text-gold-400">Round {roundNum} Summary</span>
        </div>
        {!isRaw && <RiskBadge level={summary.overall_risk_level} />}
      </div>

      {isRaw ? (
        <pre className="text-xs text-slate-400 whitespace-pre-wrap font-mono leading-relaxed overflow-auto max-h-48">
          {summary.raw_content}
        </pre>
      ) : (
        <div className="space-y-3">
          {summary.most_valuable_insight && (
            <div className="bg-slate-800/60 rounded-lg p-3">
              <p className="text-xs text-gold-400 font-medium mb-1">Key Insight</p>
              <p className="text-sm text-slate-300 leading-relaxed">{summary.most_valuable_insight}</p>
            </div>
          )}
          {summary.consensus_summary && (
            <div>
              <p className="text-xs text-slate-500 font-medium mb-1.5 flex items-center gap-1">
                <Shield size={11} /> Consensus
              </p>
              <p className="text-sm text-slate-400 leading-relaxed">{summary.consensus_summary}</p>
            </div>
          )}
          {summary.top_risks?.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 font-medium mb-1.5 flex items-center gap-1">
                <Zap size={11} /> Top Risks
              </p>
              <div className="space-y-1.5">
                {summary.top_risks.slice(0, 3).map((r, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-xs text-gold-500 font-mono mt-0.5">#{r.priority_rank || i + 1}</span>
                    <p className="text-xs text-slate-400 leading-snug">{r.risk}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
          {summary.open_disputes?.length > 0 && (
            <div className="border-t border-slate-700/50 pt-3">
              <p className="text-xs text-slate-500 font-medium mb-1">Open Disputes</p>
              <ul className="space-y-1">
                {summary.open_disputes.map((d, i) => (
                  <li key={i} className="text-xs text-orange-400/80 flex items-start gap-1.5">
                    <span className="mt-0.5">•</span>{d}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function DebatePanel({ agents, events, rounds, currentRound, currentPhase, numRounds }) {
  const feedRef = useRef(null)

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [events])

  const recentEvents = events.slice(-30)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      {/* Agent grid (left) */}
      <div className="lg:col-span-2 space-y-4">
        {/* Progress indicator */}
        <div className="card p-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Round Progress</span>
            <span className="text-gold-400 font-mono">{currentRound}/{numRounds}</span>
          </div>
          <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-gold-600 to-gold-400 rounded-full transition-all duration-1000"
              style={{ width: `${(currentRound / numRounds) * 100}%` }}
            />
          </div>
          {currentPhase && (
            <p className="text-xs text-gold-400 animate-pulse">
              ▶ {PHASE_LABEL[currentPhase] || currentPhase}
            </p>
          )}
        </div>

        {/* Agent cards */}
        <div className="space-y-2">
          {Object.entries(agents).map(([role, data]) => (
            <AgentCard key={role} role={role} agentData={data} />
          ))}
          {Object.keys(agents).length === 0 && (
            <div className="card p-6 text-center text-slate-500 text-sm">
              <Activity size={24} className="mx-auto mb-2 opacity-30" />
              Agents will appear here as they activate
            </div>
          )}
        </div>
      </div>

      {/* Right panel: event feed + summaries */}
      <div className="lg:col-span-3 space-y-4">
        {/* Live event feed */}
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity size={14} className="text-gold-400" />
            <span className="text-xs font-medium text-gold-400 uppercase tracking-widest">Live Activity</span>
            {events.length > 0 && (
              <span className="ml-auto text-xs text-slate-600 font-mono">{events.length} events</span>
            )}
          </div>
          <div ref={feedRef} className="h-48 overflow-y-auto space-y-1 scrollbar-thin">
            {recentEvents.map((evt, i) => {
              const cfg = EVENT_LABEL[evt.type] || { icon: '·', label: evt.type, color: 'text-slate-500' }
              return (
                <div key={i} className="flex items-start gap-2.5 py-1 border-b border-slate-800/50 last:border-0">
                  <span className="text-xs mt-0.5 flex-shrink-0">{cfg.icon}</span>
                  <div className="flex-1 min-w-0">
                    <span className={`text-xs ${cfg.color}`}>{cfg.label}</span>
                    {evt.agent && <span className="text-xs text-slate-500 ml-1">— {evt.agent}</span>}
                    {evt.round && <span className="text-xs text-slate-600 ml-1 font-mono">[R{evt.round}]</span>}
                  </div>
                  <span className="text-xs text-slate-700 font-mono flex-shrink-0">
                    {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''}
                  </span>
                </div>
              )
            })}
            {events.length === 0 && (
              <p className="text-xs text-slate-600 text-center py-6">Waiting for events…</p>
            )}
          </div>
        </div>

        {/* Round summaries */}
        <div className="space-y-4 overflow-y-auto max-h-[600px]">
          {rounds.map((round, i) => (
            <RoundSummaryCard
              key={i}
              summary={round?.summary?.parsed}
              roundNum={round?.round || i + 1}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
