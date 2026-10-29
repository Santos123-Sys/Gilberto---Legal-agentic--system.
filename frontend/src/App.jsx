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
import { AgentReviewConsole } from './components/AgentReviewConsole'
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
    cancellation_requested: { label: 'Cancellation requested', color: 'text-yellow-400', icon: <Loader size={12} className="animate-spin" /> },
    cancelled:          { label: 'Orchestration cancelled', color: 'text-yellow-400', icon: null },
    error:              { label: 'Error occurred', color: 'text-red-400', icon: <AlertCircle size={12} /> },
  }
  const cfg = STATUS_CFG[status] || STATUS_CFG.idle

  return (
    <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs min-w-0">
      {sessionId && (
        <span className="hidden sm:inline text-slate-600 font-mono">{sessionId.slice(0, 8)}…</span>
      )}
      {docName && <span className="text-slate-500 truncate max-w-40" title={docName}>{docName}</span>}
      <div role="status" className={`flex items-center gap-1.5 ${cfg.color} ml-auto`}>
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
  const isRunning = ['creating', 'uploading', 'running', 'cancellation_requested'].includes(session.status)
  const isAwaitingGate = session.status === 'awaiting_gate'
  const isAwaiting = session.status === 'awaiting_feedback'
  const isCompleted = session.status === 'completed'
  const isError = session.status === 'error'

  const showDebatePanel = !isIdle && !isPreview && !isRunning
  const showFeedback = isAwaiting
  const showSynthesis = (isAwaiting || isCompleted || isAwaitingGate || isError) && session.finalSynthesis

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] relative">
      <a href="#workspace-main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[100] focus:rounded-lg focus:bg-slate-100 focus:px-4 focus:py-3 focus:text-slate-950">
        Skip to legal workspace
      </a>
      {/* Background texture */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.015]"
        style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23d4a843' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")" }}
      />

      {/* ── Header ── */}
      <header className="border-b border-[var(--border)] bg-[var(--bg-secondary)]/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 min-h-16 py-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gold-500/20 border border-gold-500/40 flex items-center justify-center">
              <Scale size={16} className="text-gold-400" />
            </div>
            <div>
              <span className="font-display text-lg font-semibold text-gold-gradient">Gilberto</span>
              <span className="text-slate-500 text-xs ml-2 hidden sm:inline">AI Legal Agent v3</span>
            </div>
          </div>

          <div className="order-3 w-full min-w-0 sm:order-none sm:w-auto sm:flex-1 sm:mx-6">
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

          {session.status === 'running' && (
            <button type="button" onClick={() => session.setDispatchPaused(session.runControl !== 'pause_requested')}
              className="rounded-lg border border-blue-500/60 px-3 py-2 text-sm text-blue-300"
              aria-label={session.runControl === 'pause_requested' ? 'Resume agent dispatch' : 'Pause agent dispatch'}>
              {session.runControl === 'pause_requested' ? 'Resume dispatch' : 'Pause new requests'}
            </button>
          )}
          {['running', 'awaiting_gate'].includes(session.status) && (
            <button type="button" onClick={session.cancelAnalysis}
              className="rounded-lg border border-yellow-500/60 px-3 py-2 text-sm text-yellow-300">
              Cancel analysis
            </button>
          )}
          {!isIdle && !isRunning && (
            <button
              onClick={session.reset}
              className="ml-auto shrink-0 flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300 transition-colors px-3 py-2 rounded-lg hover:bg-slate-800/50"
            >
              <RotateCcw size={13} />
              New Analysis
            </button>
          )}
        </div>
      </header>

      {/* ── Main ── */}
      <main id="workspace-main" tabIndex={-1} className="max-w-7xl mx-auto px-4 sm:px-6 py-10">

        {/* Error banner */}
        {session.error && (
          <div className="mb-6 card border border-red-500/30 bg-red-500/5 p-4 flex items-start gap-3 animate-fade-in">
            <AlertCircle size={18} className="text-red-400 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium text-red-400">An error occurred</p>
              <p className="text-sm text-slate-300 mt-1" role="alert">{session.error}</p>
            </div>
          </div>
        )}

        {isError && session.config?.provider_mode !== 'backup' && (
          <section className="card border border-amber-500/30 p-4 mb-6 space-y-2" aria-label="Maritaca continuity options">
            <h2 className="text-base text-amber-300 font-medium">Provider failure recovery</h2>
            <p className="text-sm text-slate-300">A request might have completed or incurred charges even if its response was lost. Gilberto will not silently retry or transfer legal material to another AI vendor.</p>
            <p className="text-sm text-slate-300">To use an operator-approved backup model, select New Analysis, choose the backup inference destination, consent to the additional document transfer and upload the source again. Partial findings remain incomplete and must be reviewed.</p>
          </section>
        )}

        {isError && Object.keys(session.clusterResults).length > 0 && (
          <section className="card p-5 mb-6 space-y-4" aria-label="Retained specialist findings">
            <h2 className="font-display text-xl text-yellow-300">Partial findings — incomplete review</h2>
            <p className="text-sm text-slate-300">These workstream results were retained. They may include the previous revision and do not constitute a complete or accepted analysis.</p>
            {Object.entries(session.clusterResults).map(([id, result]) => (
              <details key={id}><summary className="cursor-pointer text-slate-200">{result.cluster_name || id}</summary>
                <p className="mt-2 text-sm text-slate-300 whitespace-pre-wrap break-words">{typeof result.summary === 'string' ? result.summary : 'See the analysis events for details.'}</p>
              </details>
            ))}
          </section>
        )}

        {session.status === 'cancelled' && (
          <section role="status" className="mb-6 rounded-lg border border-yellow-500/40 p-4 text-slate-200">
            <h2 className="font-medium">Analysis cancelled</h2>
            <p className="text-sm">New orchestration dispatch stopped. An in-flight provider request may still complete or incur charges.</p>
          </section>
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
              status={session.status}
            />
            <details className="card p-4">
              <summary className="cursor-pointer text-sm text-slate-300">Show specialist status and scores</summary>
              <div className="mt-4"><AgentClusterPanel events={session.events} activeClusters={session.config?.active_clusters} /></div>
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
              status={session.status}
            />
          </div>
        )}

        {session.status === 'running' && session.runControl === 'pause_requested' && (
          <section role="status" className="mb-6 rounded-lg border border-blue-500/50 bg-blue-500/5 p-4 text-sm text-slate-200">
            New AI dispatch is paused. Any request already sent to the model may finish or incur charges. Resume dispatch to continue, or cancel to stop orchestration.
          </section>
        )}

        {['running', 'awaiting_gate', 'awaiting_feedback', 'completed', 'error', 'cancelled'].includes(session.status) && (
          <div className="my-6">
            <AgentReviewConsole events={session.events} humanVotes={session.humanVotes}
              status={session.status} onVote={session.castHumanVote} />
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
                key={gate.gate_id || gate.gate_number}
                gate={gate}
                clusterSummary={gate.affected_cluster ? session.clusterResults[gate.affected_cluster] : null}
                daFindings={gate.gate_number === 2 && Array.isArray(session.devilAdvocate?.identified_gaps) ? session.devilAdvocate.identified_gaps : null}
                onDecision={(decision) => session.submitGateDecision(
                  gate.gate_number,
                  decision.decision,
                  decision.reasoning,
                  decision.override_score,
                  gate.gate_id
                )}
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
                URL.revokeObjectURL(url)
              }}
            />

            {/* Live cluster panel for completed analysis */}
            <AgentClusterPanel events={session.events} activeClusters={session.config?.active_clusters} />

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

