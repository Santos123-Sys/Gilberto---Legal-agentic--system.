import React from 'react'
import { ClipboardCheck, ArrowRight, Edit, Shield, AlertTriangle, Award } from 'lucide-react'

const CLUSTERS = [
  { id: 'foundation', name: 'Foundation', icon: '🏛️', color: '#6366f1', agents: 4 },
  { id: 'financial_risk', name: 'Financial Risk', icon: '💰', color: '#f59e0b', agents: 4 },
  { id: 'mitigation_exit', name: 'Mitigation & Exit', icon: '🛡️', color: '#10b981', agents: 4 },
  { id: 'compliance', name: 'Compliance', icon: '⚖️', color: '#8b5cf6', agents: 4 },
  { id: 'strategy', name: 'Strategy', icon: '♟️', color: '#ec4899', agents: 4 },
]

const GATES = [
  { num: 1, name: 'Low Confidence Review', trigger: 'Any cluster confidence < 3.0', icon: Shield },
  { num: 2, name: 'Devil\'s Advocate Gaps', trigger: 'Gap severity score > 6.0', icon: AlertTriangle },
  { num: 3, name: 'Crítico Verification', trigger: 'Final classification = Crítico', icon: Award },
]

export function IntentPreview({ config, onConfirm, onEdit }) {
  return (
    <div className="card p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-gold-500/20 flex items-center justify-center">
          <ClipboardCheck size={20} className="text-gold-400" />
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-100">Analysis Plan</h2>
          <p className="text-sm text-slate-400">Review the execution plan before proceeding</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Step 1: Parallel Clusters */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-sm font-bold flex-shrink-0">1</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-2">5 clusters will analyze in parallel</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {CLUSTERS.map(c => (
                <div key={c.id} className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
                  <span>{c.icon}</span>
                  <div>
                    <p className="text-xs font-medium text-slate-300">{c.name}</p>
                    <p className="text-[10px] text-slate-500">{c.agents} agents</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Step 2: Devil's Advocate */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-red-500/20 text-red-400 flex items-center justify-center text-sm font-bold flex-shrink-0">2</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-1">Devil's Advocate will audit all outputs</h3>
            <p className="text-xs text-slate-400">Identifies reasoning gaps, unstated assumptions, and weak points across all cluster analyses</p>
          </div>
        </div>

        {/* Step 3: Master Manager */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-sm font-bold flex-shrink-0">3</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-1">Master Manager will synthesize final result</h3>
            <p className="text-xs text-slate-400">Applies Passo 11 weighted formula, determines classification, evaluates gate conditions</p>
          </div>
        </div>

        {/* Step 4: Human Gates */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-yellow-500/20 text-yellow-400 flex items-center justify-center text-sm font-bold flex-shrink-0">4</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-2">Human review gates (if triggered)</h3>
            <div className="space-y-2">
              {GATES.map(g => (
                <div key={g.num} className="flex items-center gap-2 p-2 rounded bg-slate-800/30 border border-slate-700/30">
                  <g.icon size={14} className="text-yellow-400" />
                  <div>
                    <p className="text-xs font-medium text-slate-300">Gate {g.num}: {g.name}</p>
                    <p className="text-[10px] text-slate-500">{g.trigger}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Config summary */}
      <div className="mt-6 p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
          <div><span className="text-slate-500">Workflow:</span> <span className="text-slate-300">{config.workflow_type}</span></div>
          <div><span className="text-slate-500">Rounds:</span> <span className="text-slate-300">{config.num_rounds}</span></div>
          <div><span className="text-slate-500">Jurisdiction:</span> <span className="text-slate-300">{config.jurisdiction}</span></div>
          <div><span className="text-slate-500">Urgency:</span> <span className="text-slate-300">{config.urgency}</span></div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mt-6">
        <button
          onClick={() => onConfirm()}
          className="flex-1 btn-primary flex items-center justify-center gap-2"
        >
          Proceed with Analysis <ArrowRight size={16} />
        </button>
        <button
          onClick={onEdit}
          className="btn-secondary flex items-center gap-2"
        >
          <Edit size={14} /> Edit
        </button>
      </div>
    </div>
  )
}
