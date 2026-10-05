import React from 'react'
import { Award, AlertTriangle, CheckSquare, Download, Share2, Shield } from 'lucide-react'
import { ConfidenceSignal } from './ConfidenceSignal'

export function SynthesisDashboard({ synthesis, clusterResults, gates, onExport }) {
  if (!synthesis) return null

  return (
    <div className="space-y-6">
      {/* Executive Summary */}
      <div className="card p-6 border-gold-500/30">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-gold-500/20 flex items-center justify-center">
            <Award size={20} className="text-gold-400" />
          </div>
          <div className="flex-1">
            <h2 className="font-display text-xl text-slate-100">Executive Summary</h2>
          </div>
          <ConfidenceSignal
            score={synthesis.final_score || 0}
            confidence={synthesis.confidence || 3}
            classification={synthesis.final_classification || 'Relevante'}
            size="sm"
          />
        </div>
        <p className="text-slate-200 leading-relaxed">{synthesis.executive_summary}</p>
      </div>

      {/* Devil's Advocate Results */}
      {synthesis.devil_advocate && (
        <div className={`card p-6 border-2 ${
          synthesis.devil_advocate.sad_score >= 4 ? 'border-red-500/30' : 'border-green-500/20'
        }`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">👿</span>
              <div>
                <h3 className="font-display text-lg text-slate-100">Análise do Analista Adversarial</h3>
                <p className="text-sm text-slate-400">Auditoria de lacunas no contexto jurídico brasileiro</p>
              </div>
            </div>
            <div className="text-right">
              <div className={`text-3xl font-bold ${
                synthesis.devil_advocate.sad_score >= 4 ? 'text-red-400' :
                synthesis.devil_advocate.sad_score >= 3 ? 'text-yellow-400' : 'text-green-400'
              }`}>
                SAD {synthesis.devil_advocate.sad_score?.toFixed(1) || '—'}
              </div>
              <div className="text-xs text-slate-500">/5</div>
            </div>
          </div>

          {synthesis.devil_advocate.overall_assessment && (
            <p className="text-sm text-slate-300 mb-4 italic">{synthesis.devil_advocate.overall_assessment}</p>
          )}

          {synthesis.devil_advocate.unasked_questions?.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-medium text-slate-400 mb-2">PERGUNTAS NÃO FORMULADAS</h4>
              <div className="space-y-1">
                {synthesis.devil_advocate.unasked_questions.map((q, i) => (
                  <p key={i} className="text-sm text-slate-300 italic">"{q}"</p>
                ))}
              </div>
            </div>
          )}

          {synthesis.devil_advocate.follow_up_actions?.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-slate-400 mb-2">FOLLOW-UP ACTIONS</h4>
              <div className="space-y-2">
                {synthesis.devil_advocate.follow_up_actions.map((action, i) => (
                  <div key={i} className="flex items-start gap-2 p-2 rounded bg-slate-800/30">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded flex-shrink-0 ${
                      action.priority === 'HIGH' ? 'bg-red-500/20 text-red-400' :
                      action.priority === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-green-500/20 text-green-400'
                    }`}>
                      {action.priority}
                    </span>
                    <div>
                      <p className="text-sm text-slate-200">{action.action}</p>
                      <p className="text-[10px] text-slate-500">Responsável: {action.responsible_cluster}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Cluster Breakdown */}
      {clusterResults && Object.keys(clusterResults).length > 0 && (
        <div>
          <h3 className="font-display text-lg text-slate-100 mb-4">Cluster Analysis Breakdown</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(clusterResults).map(([id, result]) => (
              <ClusterResultCard key={id} id={id} result={result} />
            ))}
          </div>
        </div>
      )}

      {/* Critical Actions */}
      {synthesis.critical_actions?.length > 0 && (
        <div className="card p-6 border-red-500/20">
          <h3 className="font-display text-lg text-slate-100 mb-4 flex items-center gap-2">
            <AlertTriangle size={18} className="text-red-400" />
            Critical Actions Required
          </h3>
          <ol className="space-y-3">
            {synthesis.critical_actions.map((action, i) => (
              <li key={i} className="flex gap-3">
                <span className="w-6 h-6 rounded-full bg-red-500/20 text-red-400 text-xs flex items-center justify-center flex-shrink-0 font-bold">
                  {i + 1}
                </span>
                <span className="text-sm text-slate-200">{action}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Approval Checklist */}
      {synthesis.approval_checklist?.length > 0 && (
        <div className="card p-6 border-green-500/20">
          <h3 className="font-display text-lg text-slate-100 mb-4 flex items-center gap-2">
            <CheckSquare size={18} className="text-green-400" />
            Approval Checklist
          </h3>
          <div className="space-y-2">
            {synthesis.approval_checklist.map((item, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <div className="w-4 h-4 rounded border border-green-500/50 mt-0.5 flex-shrink-0" />
                <span className="text-slate-300">{item}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Gate Records */}
      {gates?.length > 0 && (
        <div className="card p-6 border-yellow-500/20">
          <h3 className="font-display text-lg text-slate-100 mb-4 flex items-center gap-2">
            <Shield size={18} className="text-yellow-400" />
            Human Review Gates
          </h3>
          <div className="space-y-3">
            {gates.map((gate, i) => (
              <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                  gate.status === 'approved' ? 'bg-green-500/20 text-green-400' :
                  gate.status === 'overridden' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-slate-700 text-slate-400'
                }`}>
                  {gate.gate_number}
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-200">
                    Gate {gate.gate_number}: {gate.trigger?.trigger_type || gate.trigger_type}
                  </p>
                  <p className="text-xs text-slate-500">
                    {gate.status} — {gate.human_decision?.human_review_id || 'System'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Export */}
      <div className="flex gap-3">
        <button onClick={onExport} className="btn-primary flex items-center gap-2">
          <Download size={16} /> Export Full Report
        </button>
        <button className="btn-secondary flex items-center gap-2">
          <Share2 size={16} /> Share Results
        </button>
      </div>
    </div>
  )
}

function ClusterResultCard({ id, result }) {
  const colors = {
    foundation: '#6366f1',
    financial_risk: '#f59e0b',
    mitigation_exit: '#10b981',
    compliance: '#8b5cf6',
    strategy: '#ec4899',
  }

  const names = {
    foundation: 'Foundation',
    financial_risk: 'Financial Risk',
    mitigation_exit: 'Mitigation & Exit',
    compliance: 'Compliance',
    strategy: 'Strategy',
  }

  const color = colors[id] || '#64748b'

  return (
    <div className="card p-4" style={{ borderTopColor: color, borderTopWidth: 3 }}>
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-medium text-slate-200">{names[id] || id}</h4>
        <span
          className="text-lg font-bold"
          style={{ color }}
        >
          {result.aggregated_score?.toFixed(1) || '—'}
        </span>
      </div>

      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 bg-slate-700 rounded-full h-1.5">
          <div
            className="h-1.5 rounded-full"
            style={{
              width: `${((result.confidence_aggregate || 0) / 5) * 100}%`,
              backgroundColor: result.confidence_aggregate < 3 ? '#f59e0b' : '#10b981',
            }}
          />
        </div>
        <span className="text-xs text-slate-500">{result.confidence_aggregate}/5</span>
      </div>

      <span className={`inline-block px-2 py-0.5 rounded text-xs ${
        result.classification === 'Crítico' ? 'bg-red-500/20 text-red-400' :
        result.classification === 'Relevante' ? 'bg-yellow-500/20 text-yellow-400' :
        'bg-green-500/20 text-green-400'
      }`}>
        {result.classification}
      </span>

      {result.key_findings?.length > 0 && (
        <ul className="mt-2 space-y-1">
          {result.key_findings.slice(0, 2).map((f, i) => (
            <li key={i} className="text-xs text-slate-400 line-clamp-1">• {f}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
