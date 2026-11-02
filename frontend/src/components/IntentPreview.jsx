import React from 'react'
import { ClipboardCheck, ArrowRight, Edit, Shield, AlertTriangle, Award } from 'lucide-react'

const CLUSTERS = [
  { id: 'foundation', name: 'Fundamentos', icon: '🏛️', color: '#6366f1', agents: 4 },
  { id: 'financial_risk', name: 'Risco financeiro', icon: '💰', color: '#f59e0b', agents: 4 },
  { id: 'mitigation_exit', name: 'Mitigação e saída', icon: '🛡️', color: '#10b981', agents: 4 },
  { id: 'compliance', name: 'Conformidade', icon: '⚖️', color: '#8b5cf6', agents: 4 },
  { id: 'strategy', name: 'Estratégia', icon: '♟️', color: '#ec4899', agents: 4 },
]

const GATES = [
  { num: 1, name: 'Revisão por baixa confiança', trigger: 'Confiança de qualquer grupo < 3,0', icon: Shield },
  { num: 2, name: 'Lacunas apontadas pelo advogado do diabo', trigger: 'Gravidade das lacunas > 6,0', icon: AlertTriangle },
  { num: 3, name: 'Verificação de classificação Crítico', trigger: 'Classificação final = Crítico', icon: Award },
]

export function IntentPreview({ config, onConfirm, onEdit }) {
  return (
    <div className="card p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-gold-500/20 flex items-center justify-center">
          <ClipboardCheck size={20} className="text-gold-400" />
        </div>
        <div>
          <h2 className="font-display text-xl text-slate-100">Plano de análise</h2>
          <p className="text-sm text-slate-400">Revise o escopo antes que seu documento seja enviado ao provedor de IA configurado.</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Step 1: Parallel Clusters */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-blue-500/20 text-blue-400 flex items-center justify-center text-sm font-bold flex-shrink-0">1</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-2">Frentes especializadas configuradas</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {(config.active_clusters || []).map(c => (
                <div key={c.id} className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/50 border border-slate-700/50">
                  <span>{CLUSTERS.find(item => item.id === c.id)?.icon || '⚖️'}</span>
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
            <h3 className="text-sm font-medium text-slate-200 mb-1">O advogado do diabo auditará todos os resultados</h3>
            <p className="text-xs text-slate-400">Identifica lacunas de fundamentação, pressupostos não declarados e pontos fracos em todas as análises dos grupos</p>
          </div>
        </div>

        {/* Step 3: Master Manager */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 text-purple-400 flex items-center justify-center text-sm font-bold flex-shrink-0">3</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-1">O coordenador-geral sintetizará o resultado final</h3>
            <p className="text-xs text-slate-400">Aplica a fórmula ponderada do Passo 11, determina a classificação e avalia as condições das etapas de revisão</p>
          </div>
        </div>

        {/* Step 4: Human Gates */}
        <div className="flex gap-4">
          <div className="w-8 h-8 rounded-full bg-yellow-500/20 text-yellow-400 flex items-center justify-center text-sm font-bold flex-shrink-0">4</div>
          <div className="flex-1">
            <h3 className="text-sm font-medium text-slate-200 mb-2">Etapas de revisão humana (se acionadas)</h3>
            <div className="space-y-2">
              {GATES.map(g => (
                <div key={g.num} className="flex items-center gap-2 p-2 rounded bg-slate-800/30 border border-slate-700/30">
                  <g.icon size={14} className="text-yellow-400" />
                  <div>
                    <p className="text-xs font-medium text-slate-300">Etapa {g.num}: {g.name}</p>
                    <p className="text-[10px] text-slate-500">{g.trigger}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 p-4 rounded-lg border border-amber-500/30 text-sm text-slate-300">
        <p className="font-medium text-amber-300">Destino da inferência de IA: {config.provider_mode === 'backup' ? 'Reserva aprovado pelo operador' : 'Maritaca (principal)'}</p>
        <p className="mt-1">Esta revisão usa um único provedor selecionado. Em caso de indisponibilidade ou de tempo esgotado incerto, as requisições não são repetidas nem redirecionadas automaticamente. O trabalho parcial permanece incompleto e exige uma nova revisão expressamente autorizada.</p>
      </div>
      {/* Config summary */}
      <div className="mt-6 p-3 rounded-lg bg-slate-800/30 border border-slate-700/30">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
          <div><span className="text-slate-500">Fluxo:</span> <span className="text-slate-300">{config.workflow_type}</span></div>
          <div><span className="text-slate-500">Rodadas:</span> <span className="text-slate-300">{config.num_rounds}</span></div>
          <div><span className="text-slate-500">Jurisdição:</span> <span className="text-slate-300">{config.jurisdiction}</span></div>
          <div><span className="text-slate-500">Urgência:</span> <span className="text-slate-300">{config.urgency}</span></div>
        </div>
      </div>

      <p className="text-sm text-slate-300 mt-4">{config.num_agents} especialistas · requisições escalonadas · no máximo {config.model_call_budget} tarefas do modelo por sessão · até {config.max_feedback_rounds} revisões por comentário. Os resultados são minutas geradas por IA para revisão jurídica. As sessões ficam na memória do servidor e são perdidas ao reiniciá-lo.</p>

      <p className="text-sm text-slate-300 mt-3">Profundidade da revisão: {config.review_depth === 'focused' ? 'focada' : 'completa'} · {config.initial_model_calls ?? 'consulte a lista configurada'} chamadas iniciais ao provedor. As revisões consomem chamadas adicionais. Rascunhos focados têm menos revisores independentes; não se comprovou precisão jurídica equivalente.</p>
      {/* Actions */}
      <div className="flex gap-3 mt-6">
        <button
          onClick={() => onConfirm()}
          className="flex-1 btn-primary flex items-center justify-center gap-2"
        >
          Prosseguir com a análise <ArrowRight size={16} />
        </button>
        <button
          onClick={onEdit}
          className="btn-secondary flex items-center gap-2"
        >
          <Edit size={14} /> Editar
        </button>
      </div>
    </div>
  )
}

