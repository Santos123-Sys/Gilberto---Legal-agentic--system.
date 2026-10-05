import React, { useState } from 'react'
import { Shield, AlertTriangle, Award, CheckCircle, Edit, RefreshCw, X } from 'lucide-react'

const GATE_CONFIG = {
  1: { name: 'Low Confidence Review', icon: Shield, color: 'yellow', description: 'One or more clusters have low confidence in their analysis' },
  2: { name: 'Devil\'s Advocate Gaps', icon: AlertTriangle, color: 'red', description: 'Critical reasoning gaps were identified in the analysis' },
  3: { name: 'Crítico Verification', icon: Award, color: 'purple', description: 'Final classification is Crítico — requires senior review' },
}

export function GateReviewPanel({ gate, clusterSummary, daFindings, onDecision, onClose }) {
  const [decision, setDecision] = useState(null)
  const [reasoning, setReasoning] = useState('')
  const [overrideScore, setOverrideScore] = useState(5.0)
  const [submitting, setSubmitting] = useState(false)

  const config = GATE_CONFIG[gate.gate_number] || GATE_CONFIG[1]

  const handleSubmit = async () => {
    if (!decision || !reasoning.trim()) return
    setSubmitting(true)
    await onDecision({
      gate_number: gate.gate_number,
      decision,
      reasoning,
      override_score: decision === 'override' ? overrideScore : undefined,
    })
    setSubmitting(false)
  }

  return (
    <div className={`card p-6 border-2 border-${config.color}-500/30 max-w-2xl mx-auto`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg bg-${config.color}-500/20 flex items-center justify-center`}>
            <config.icon size={20} className={`text-${config.color}-400`} />
          </div>
          <div>
            <h3 className="font-display text-lg text-slate-100">Gate {gate.gate_number}: {config.name}</h3>
            <p className="text-sm text-slate-400">{config.description}</p>
          </div>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
          <X size={18} />
        </button>
      </div>

      {/* Trigger details */}
      <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 mb-4">
        <h4 className="text-xs font-medium text-slate-400 mb-2">TRIGGER DETAILS</h4>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-slate-500">Type:</span>
            <span className="text-slate-300 ml-1">{gate.trigger?.trigger_type || gate.trigger_type}</span>
          </div>
          <div>
            <span className="text-slate-500">Value:</span>
            <span className="text-slate-300 ml-1">{gate.trigger?.trigger_value || gate.trigger_value}</span>
          </div>
          <div>
            <span className="text-slate-500">Threshold:</span>
            <span className="text-slate-300 ml-1">{gate.trigger?.threshold || gate.threshold}</span>
          </div>
          {gate.affected_cluster && (
            <div>
              <span className="text-slate-500">Cluster:</span>
              <span className="text-slate-300 ml-1">{gate.affected_cluster}</span>
            </div>
          )}
        </div>
        <p className="text-sm text-slate-300 mt-2">{gate.trigger?.description || gate.description}</p>
      </div>

      {/* Cluster summary under review */}
      {clusterSummary && (
        <div className="p-3 rounded-lg bg-slate-800/30 border border-slate-700/30 mb-4">
          <h4 className="text-xs font-medium text-slate-400 mb-2">CLUSTER SUMMARY UNDER REVIEW</h4>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-300">Score: <strong>{clusterSummary.aggregated_score}</strong></span>
            <span className="text-slate-300">Confidence: <strong>{clusterSummary.confidence_aggregate}</strong></span>
            <span className={`px-2 py-0.5 rounded text-xs ${
              clusterSummary.classification === 'Crítico' ? 'bg-red-500/20 text-red-400' :
              clusterSummary.classification === 'Relevante' ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-green-500/20 text-green-400'
            }`}>
              {clusterSummary.classification}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-2 line-clamp-3">{clusterSummary.summary}</p>
        </div>
      )}

      {/* DA findings for Gate 2 */}
      {daFindings && daFindings.length > 0 && (
        <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 mb-4">
          <h4 className="text-xs font-medium text-red-400 mb-2">DEVIL'S ADVOCATE FINDINGS</h4>
          <div className="space-y-2">
            {daFindings.slice(0, 5).map((gap, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <AlertTriangle size={12} className="text-red-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-slate-300">{gap.description}</p>
                  <p className="text-xs text-slate-500">{gap.severity} — {gap.recommended_action}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Decision buttons */}
      <div className="mb-4">
        <h4 className="text-xs font-medium text-slate-400 mb-2">YOUR DECISION</h4>
        <div className="grid grid-cols-3 gap-2">
          <DecisionButton
            selected={decision === 'approve'}
            onClick={() => setDecision('approve')}
            icon={<CheckCircle size={16} />}
            label="Approve"
            color="green"
          />
          <DecisionButton
            selected={decision === 'override'}
            onClick={() => setDecision('override')}
            icon={<Edit size={16} />}
            label="Override"
            color="yellow"
          />
          <DecisionButton
            selected={decision === 'request_reanalysis'}
            onClick={() => setDecision('request_reanalysis')}
            icon={<RefreshCw size={16} />}
            label="Re-analyze"
            color="red"
          />
        </div>
      </div>

      {/* Override score slider */}
      {decision === 'override' && (
        <div className="mb-4 p-3 rounded-lg bg-yellow-500/5 border border-yellow-500/20">
          <label className="block text-xs font-medium text-slate-400 mb-2">
            Override Score: <span className="text-yellow-400 font-bold">{overrideScore.toFixed(1)}</span>
          </label>
          <input
            type="range" min="0" max="10" step="0.1"
            value={overrideScore}
            onChange={e => setOverrideScore(parseFloat(e.target.value))}
            className="w-full accent-yellow-500"
          />
          <div className="flex justify-between text-[10px] text-slate-500 mt-1">
            <span>0 (No risk)</span>
            <span>5 (Relevant)</span>
            <span>10 (Critical)</span>
          </div>
        </div>
      )}

      {/* Reasoning */}
      <div className="mb-4">
        <label className="block text-xs font-medium text-slate-400 mb-2">
          EXPERT REASONING <span className="text-red-400">*</span>
        </label>
        <textarea
          value={reasoning}
          onChange={e => setReasoning(e.target.value)}
          placeholder="Explain your decision in detail. This will be recorded in the audit trail."
          className="w-full h-28 bg-slate-800 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-gold-500/50 resize-none"
        />
      </div>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={!decision || !reasoning.trim() || submitting}
        className={`w-full py-3 rounded-lg font-medium transition-all ${
          decision && reasoning.trim()
            ? 'bg-gold-500 text-slate-900 hover:bg-gold-400'
            : 'bg-slate-700 text-slate-500 cursor-not-allowed'
        }`}
      >
        {submitting ? 'Submitting…' : 'Submit Decision'}
      </button>
    </div>
  )
}

function DecisionButton({ selected, onClick, icon, label, color }) {
  return (
    <button
      onClick={onClick}
      className={`flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 transition-all ${
        selected
          ? `border-${color}-500 bg-${color}-500/10 text-${color}-400`
          : 'border-slate-700 text-slate-500 hover:border-slate-600'
      }`}
    >
      {icon}
      <span className="text-xs font-medium">{label}</span>
    </button>
  )
}
