import { Scale, RotateCcw, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import { SessionConfig } from './components/SessionConfig'
import { DebatePanel } from './components/DebatePanel'
import { FeedbackForm } from './components/FeedbackForm'
import { IntentPreview } from './components/IntentPreview'
import { AgentClusterPanel } from './components/AgentClusterPanel'
import { GateReviewPanel } from './components/GateReviewPanel'
import { SynthesisDashboard } from './components/SynthesisDashboard'
import { AuditTrail } from './components/AuditTrail'
import { AgenticProgress } from './components/AgenticProgress'
import { useAgenticSession } from './hooks/useAgenticSession'

// ─────────────────────────────────────────────
//  STATUS BAR
// ─────────────────────────────────────────────
function StatusBar({ status, sessionId, currentRound, numRounds, docName, pendingGates, connectionState }) {
  const STATUS_CFG = {
    idle:               { label: 'Ready', color: 'text-slate-500', icon: null },
    creating:           { label: 'Creating session…', color: 'text-gold-400', icon: <Loader size={12} className="animate-spin" /> },
    preview:            { label: 'Review plan…', color: 'text-blue-400', icon: null },
    uploading:          { label: 'Uploading document…', color: 'text-gold-400', icon: <Loader size={12} className="animate-spin" /> },
    running:            { label: `Round ${currentRound} of ${numRounds || '?'} — In progress`, color: 'text-blue-400', icon: <Loader size={12} className="animate-spin" /> },
    awaiting_gate:      { label: `Gate review needed (${pendingGates} pending)`, color: 'text-yellow-400', icon: <AlertCircle size={12} /> },
    awaiting_feedback:  { label: 'Analysis complete — Awaiting your feedback', color: 'text-gold-400', icon: null },
    completed:          { label: 'Analysis accepted & complete', color: 'text-green-400', icon: <CheckCircle size={12} /> },
    error:              { label: 'Error occurred', color: 'text-red-400', icon: <AlertCircle size={12} /> },
  }
  const cfg = STATUS_CFG[status] || STATUS_CFG.idle

  return (
    <div className="flex items-center gap-4 text-xs">
      {sessionId && (
        <span className="text-slate-600 font-mono">{sessionId.slice(0, 8)}…</span>
      )}
      {docName && <span className="text-slate-500 truncate max-w-40" title={docName}>{docName}</span>}
      <div className={`flex items-center gap-1.5 ${cfg.color} ml-auto`}>
        {cfg.icon}
        <span>{cfg.label}</span>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────
//  APP
// ─────────────────────────────────────────────
export default function App() {
  const session = useAgenticSession()

  const isIdle = session.status === 'idle'
  const isPreview = session.status === 'preview'
  const isRunning = ['creating', 'uploading', 'running'].includes(session.status)
  const isAwaitingGate = session.status === 'awaiting_gate'
  const isAwaiting = session.status === 'awaiting_feedback'
  const isCompleted = session.status === 'completed'
  const isError = session.status === 'error'

  const showDebatePanel = !isIdle && !isPreview && !isRunning
  const showFeedback = isAwaiting
  const showSynthesis = (isAwaiting || isCompleted || isAwaitingGate) && session.finalSynthesis

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] relative">
      {/* Background texture */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.015]"
        style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23d4a843' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")" }}
      />

      {/* ── Header ── */}
      <header className="border-b border-[var(--border)] bg-[var(--bg-secondary)]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gold-500/20 border border-gold-500/40 flex items-center justify-center">
              <Scale size={16} className="text-gold-400" />
            </div>
            <div>
              <span className="font-display text-lg font-semibold text-gold-gradient">Gilberto</span>
              <span className="text-slate-500 text-xs ml-2 hidden sm:inline">AI Legal Agent v3</span>
            </div>
          </div>

          <div className="flex-1 mx-6">
            <StatusBar
              status={session.status}
              sessionId={session.sessionId}
              currentRound={session.rounds.length + 1}
              numRounds={session.config?.num_rounds}
              docName={session.documentName}
              pendingGates={session.pendingGates.length}
              connectionState={session.connectionState}
            />
          </div>

          {!isIdle && !isRunning && (
            <button
              onClick={session.reset}
              className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors px-3 py-2 rounded-lg hover:bg-slate-800/50"
            >
              <RotateCcw size={13} />
              New Analysis
            </button>
          )}
        </div>
      </header>

      {/* ── Main ── */}
      <main className="max-w-7xl mx-auto px-6 py-10">

        {/* Error banner */}
        {isError && (
          <div className="mb-6 card border border-red-500/30 bg-red-500/5 p-4 flex items-start gap-3 animate-fade-in">
            <AlertCircle size={18} className="text-red-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-400">An error occurred</p>
              <p className="text-xs text-slate-400 mt-1">{session.error}</p>
            </div>
          </div>
        )}

        {/* Completed banner */}
        {isCompleted && (
          <div className="mb-6 card border border-green-500/30 bg-green-500/5 p-5 flex items-start gap-4 animate-fade-in">
            <CheckCircle size={24} className="text-green-400 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-display text-lg text-green-400">Analysis Accepted</h3>
              <p className="text-sm text-slate-400 mt-1">
                Your legal document analysis is complete. {session.rounds.length} round{session.rounds.length !== 1 ? 's' : ''} of agent debate were conducted.
              </p>
            </div>
          </div>
        )}

        {/* ── STAGE 1: Configure ── */}
        {isIdle && (
          <SessionConfig
            onStart={session.createSession}
            loading={isRunning}
          />
        )}

        {/* ── STAGE 2: Intent Preview ── */}
        {isPreview && session.config && (
          <IntentPreview
            config={session.config}
            onConfirm={() => session.confirmAndStart()}
            onEdit={session.reset}
          />
        )}

        {/* ── STAGE 3: Running — Live Cluster Panel ── */}
        {isRunning && (
          <div className="space-y-6">
            <AgenticProgress
              events={session.events}
              rounds={session.rounds}
              totalRounds={session.config?.num_rounds}
              connectionState={session.connectionState}
              lastEventAt={session.lastEventAt}
              onReconnect={session.reconnect}
            />
            <details className="card p-4">
              <summary className="cursor-pointer text-sm text-slate-300">Show specialist status and scores</summary>
              <div className="mt-4"><AgentClusterPanel events={session.events} /></div>
            </details>
          </div>
        )}

        {isError && session.events.length > 0 && (
          <div className="mb-6">
            <AgenticProgress
              events={session.events}
              rounds={session.rounds}
              totalRounds={session.config?.num_rounds}
              connectionState={session.connectionState}
              lastEventAt={session.lastEventAt}
              onReconnect={session.reconnect}
            />
          </div>
        )}

        {/* ── STAGE 4: Gate Review ── */}
        {isAwaitingGate && session.pendingGates.length > 0 && (
          <div className="space-y-6">
            <div className="text-center py-4">
              <AlertCircle size={32} className="text-yellow-400 mx-auto mb-4" />
              <h2 className="font-display text-xl text-slate-100">Human Review Required</h2>
              <p className="text-sm text-slate-400 mt-1">
                {session.pendingGates.length} gate{session.pendingGates.length !== 1 ? 's' : ''} triggered
              </p>
            </div>

            {session.pendingGates.map(gate => (
              <GateReviewPanel
                key={gate.gate_number}
                gate={gate}
                clusterSummary={gate.affected_cluster ? session.clusterResults[gate.affected_cluster] : null}
                daFindings={gate.gate_number === 2 && Array.isArray(session.devilAdvocate?.identified_gaps) ? session.devilAdvocate.identified_gaps : null}
                onDecision={(decision) => session.submitGateDecision(
                  gate.gate_number,
                  decision.decision,
                  decision.reasoning,
                  decision.override_score
                )}
                onClose={() => {}}
              />
            ))}
          </div>
        )}

        {/* ── STAGE 5: Synthesis Dashboard ── */}
        {showSynthesis && (
          <div className="space-y-6">
            <SynthesisDashboard
              synthesis={session.finalSynthesis}
              clusterResults={session.clusterResults}
              gates={session.gateRecords}
              onExport={() => {
                const data = {
                  synthesis: session.finalSynthesis,
                  clusters: session.clusterResults,
                  gates: session.gateRecords,
                  metrics: session.executionMetrics,
                }
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `gilberto-analysis-${session.sessionId}.json`
                a.click()
              }}
            />

            {/* Live cluster panel for completed analysis */}
            <AgentClusterPanel events={session.events} />

            {/* Audit trail */}
            <AuditTrail
              events={session.events}
              gates={session.gateRecords}
            />
          </div>
        )}

        {/* ── STAGE 6: Feedback ── */}
        {showFeedback && (
          <div className="mt-8">
            <FeedbackForm
              onSubmitFeedback={session.submitFeedback}
              onAccept={session.acceptResult}
              loading={isRunning}
              rounds={session.rounds}
            />
          </div>
        )}

        {!isIdle && !isPreview && !isRunning && !isError && !isAwaitingGate && !showSynthesis && !showFeedback && (
          <div className="card p-6 text-center max-w-2xl mx-auto">
            <Loader size={24} className="animate-spin text-gold-400 mx-auto mb-3" />
            <h2 className="font-display text-lg text-slate-100">Preparing the next review step</h2>
            <p className="text-sm text-slate-400 mt-2">The session is active, but its next result is not available yet. Progress updates will appear here.</p>
            <button type="button" onClick={session.reconnect} className="btn-secondary mt-4">Reconnect to analysis</button>
          </div>
        )}

        {/* Legacy debate panel (kept for compatibility) */}
        {showDebatePanel && !showSynthesis && (
          <DebatePanel
            events={session.events}
            rounds={session.rounds}
            currentRound={session.rounds.length + 1}
            totalRounds={session.config?.num_rounds}
          />
        )}
      </main>
    </div>
  )
}
