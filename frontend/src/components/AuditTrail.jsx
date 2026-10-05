import React, { useMemo, useState } from 'react'
import { Activity, Shield, UserCheck, AlertTriangle, Circle, Filter } from 'lucide-react'

const TYPE_CONFIG = {
  event: { icon: Activity, color: '#3b82f6', label: 'System' },
  gate: { icon: Shield, color: '#f59e0b', label: 'Gate' },
  decision: { icon: UserCheck, color: '#10b981', label: 'Decision' },
  error: { icon: AlertTriangle, color: '#ef4444', label: 'Error' },
}

export function AuditTrail({ events, gates, className = '' }) {
  const [filter, setFilter] = useState('all')

  const items = useMemo(() => {
    const all = [
      ...events.map(e => ({ ...e, _type: 'event', _time: e.timestamp })),
      ...gates.map(g => ({ ...g, _type: 'gate', _time: g.timestamp_triggered })),
    ].sort((a, b) => new Date(a._time) - new Date(b._time))
    return all
  }, [events, gates])

  const filtered = filter === 'all' ? items : items.filter(i => i._type === filter)

  return (
    <div className={`card p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-lg text-slate-100">Action Audit Trail</h3>
        <div className="flex items-center gap-1">
          <Filter size={14} className="text-slate-500" />
          {['all', 'event', 'gate'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                filter === f ? 'bg-gold-500/20 text-gold-400' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="relative">
        {filtered.map((item, i) => (
          <TimelineItem
            key={i}
            item={item}
            isLast={i === filtered.length - 1}
          />
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-slate-500 italic">No events recorded yet.</p>
        )}
      </div>
    </div>
  )
}

function TimelineItem({ item, isLast }) {
  const config = TYPE_CONFIG[item._type] || TYPE_CONFIG.event

  const label = useMemo(() => {
    if (item._type === 'gate') return `Gate ${item.gate_number} ${item.status}`
    if (item._type === 'event') {
      const labels = {
        DEBATE_START: 'Analysis started',
        CLUSTER_START: `Cluster started: ${item.cluster_name || item.cluster}`,
        CLUSTER_COMPLETE: `Cluster complete: ${item.cluster_name || item.cluster}`,
        AGENT_THINKING: `${item.agent} analyzing`,
        AGENT_ANALYSIS_COMPLETE: `${item.agent} completed analysis`,
        DEVILS_ADVOCATE_START: 'Devil\'s Advocate audit started',
        DEVILS_ADVOCATE_COMPLETE: `Devil\'s Advocate found ${item.identified_gaps?.length || 0} gaps`,
        MASTER_MANAGER_START: 'Master Manager synthesis started',
        MASTER_MANAGER_COMPLETE: 'Final synthesis complete',
        GATE_TRIGGERED: `Gate ${item.gate_number} triggered`,
        GATE_RESOLVED: `Gate ${item.gate_number} resolved: ${item.decision}`,
        ROUND_COMPLETE: `Round ${item.round} complete`,
        DEBATE_COMPLETE: 'Analysis complete',
        ERROR: `Error: ${item.message?.slice(0, 80)}`,
      }
      return labels[item.type] || item.type
    }
    return 'Unknown'
  }, [item])

  const time = new Date(item._time).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })

  return (
    <div className={`flex gap-3 ${isLast ? '' : 'pb-3'}`}>
      <div className="flex flex-col items-center">
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: `${config.color}20` }}
        >
          <config.icon size={12} style={{ color: config.color }} />
        </div>
        {!isLast && <div className="w-px flex-1 bg-slate-700/50 mt-1" />}
      </div>
      <div className="flex-1 min-w-0 pb-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-slate-200 truncate">{label}</span>
          <span className="text-xs text-slate-500 flex-shrink-0">{time}</span>
        </div>
        {item.description && (
          <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{item.description}</p>
        )}
      </div>
    </div>
  )
}
