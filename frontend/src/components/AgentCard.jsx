import { Brain, CheckCircle, Vote, Sparkles } from 'lucide-react'

const ROLE_ICONS = {
  'Legal Risk Analyst': '⚖️',
  'Brazilian Compliance Advisor': '📋',
  'Negotiation Strategist': '🤝',
  'Corporate Governance Expert': '🏛️',
  "Devil's Advocate": '👿',
  'Senior Legal Partner & Debate Orchestrator': '👑',
  'User Feedback Advocate': '💬',
}

const STATUS_CONFIG = {
  thinking: {
    label: 'Analyzing…',
    color: 'text-gold-400',
    bg: 'border-gold-500/40 bg-gold-500/5',
    dot: 'bg-gold-400 agent-active',
    icon: <Brain size={12} className="animate-pulse" />,
  },
  done: {
    label: 'Analysis complete',
    color: 'text-green-400',
    bg: 'border-green-500/20 bg-green-500/5',
    dot: 'bg-green-400',
    icon: <CheckCircle size={12} />,
  },
  voting: {
    label: 'Reviewing peers…',
    color: 'text-blue-400',
    bg: 'border-blue-500/20 bg-blue-500/5',
    dot: 'bg-blue-400 animate-pulse',
    icon: <Vote size={12} />,
  },
  voted: {
    label: 'Voted',
    color: 'text-purple-400',
    bg: 'border-purple-500/20 bg-purple-500/5',
    dot: 'bg-purple-400',
    icon: <Vote size={12} />,
  },
  new: {
    label: 'New agent (from feedback)',
    color: 'text-cyan-400',
    bg: 'border-cyan-500/30 bg-cyan-500/5',
    dot: 'bg-cyan-400',
    icon: <Sparkles size={12} />,
  },
  idle: {
    label: 'Standby',
    color: 'text-slate-500',
    bg: 'border-slate-700 bg-transparent',
    dot: 'bg-slate-600',
    icon: null,
  },
}

function safeParseFindings(parsed) {
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return []
  if (parsed.raw_content) return []
  const findings = Array.isArray(parsed.key_findings) ? parsed.key_findings : []
  return findings.filter(f => f && typeof f === 'object').slice(0, 3).map(f => ({
    ...f,
    severity: typeof f.severity === 'string' ? f.severity : 'medium',
    finding: typeof f.finding === 'string' ? f.finding : f.finding == null ? 'Finding details are unavailable.' : JSON.stringify(f.finding),
  }))
}

export function AgentCard({ role, agentData }) {
  const statusKey = agentData?.status || 'idle'
  const config = STATUS_CONFIG[statusKey] || STATUS_CONFIG.idle
  const safeRole = typeof role === 'string' ? role : 'Legal specialist'
  const icon = ROLE_ICONS[safeRole] || ROLE_ICONS[Object.keys(ROLE_ICONS).find(k => safeRole.includes(k.split(' ')[0]))] || '🤖'
  const findings = safeParseFindings(agentData?.parsed)

  return (
    <div className={`card border p-4 space-y-3 animate-slide-up transition-all duration-500 ${config.bg}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl leading-none">{icon}</span>
          <div>
            <p className="text-sm font-medium text-slate-100 leading-tight">{safeRole}</p>
            <div className={`flex items-center gap-1.5 mt-1 text-xs ${config.color}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
              <span>{config.label}</span>
              {config.icon}
            </div>
          </div>
        </div>
      </div>

      {/* Key findings (when analysis done) */}
      {statusKey === 'done' && findings.length > 0 && (
        <div className="space-y-1.5 border-t border-slate-700/50 pt-3">
          {findings.map((f, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className={`text-xs px-1.5 py-0.5 rounded font-mono mt-0.5 flex-shrink-0 risk-${f.severity || 'medium'}`}>
                {(f.severity || 'med').toUpperCase()}
              </span>
              <p className="text-xs text-slate-400 leading-snug">{f.finding}</p>
            </div>
          ))}
        </div>
      )}

      {/* Thinking animation */}
      {statusKey === 'thinking' && (
        <div className="flex gap-1 pt-1">
          {[0, 1, 2].map(i => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-gold-400"
              style={{ animation: `thinking 1.5s ease-in-out ${i * 0.2}s infinite` }}
            />
          ))}
        </div>
      )}
    </div>
  )
}
