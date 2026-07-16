import { Scale, RotateCcw, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import { SessionConfig } from './components/SessionConfig'
import { DebatePanel } from './components/DebatePanel'
import { FeedbackForm } from './components/FeedbackForm'
import { useDebateSession } from './hooks/useDebateSession'

// ─────────────────────────────────────────────
//  STATUS BAR
// ─────────────────────────────────────────────
function StatusBar({ status, sessionId, currentRound, numRounds, docName }) {
  const STATUS_CFG = {
    idle:               { label: 'Ready', color: 'text-slate-500', icon: null },
    creating:           { label: 'Creating session…', color: 'text-gold-400', icon: <Loader size={12} className="animate-spin" /> },
    uploading:          { label: 'Uploading document…', color: 'text-gold-400', icon: <Loader size={12} className="animate-spin" /> },
    running:            { label: `Round ${currentRound} of ${numRounds || '?'} — In progress`, color: 'text-blue-400', icon: <Loader size={12} className="animate-spin" /> },
    awaiting_feedback:  { label: 'Debate complete — Awaiting your feedback', color: 'text-gold-400', icon: null },
    completed:          { label: 'Analysis accepted & complete', color: 'text-green-400', icon: <CheckCircle size={12} /> },
    error:              { label: 'Error occurred', color: 'text-red-400', icon: <AlertCircle size={12} /> },
  }
  const cfg = STATUS_CFG[status] || STATUS_CFG.idle

  return (
    <div className="flex items-center gap-4 text-xs">
      {sessionId && (
        <span className="text-slate-600 font-mono">
          {sessionId.slice(0, 8)}…
        </span>
      )}
      {docName && (
        <span className="text-slate-500 font-mono">{docName}</span>
      )}
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
  const session = useDebateSession()

  const isIdle = session.status === 'idle'
  const isConfiguring = isIdle
  const isRunning = ['creating', 'uploading', 'running'].includes(session.status)
  const isAwaiting = session.status === 'awaiting_feedback'
  const isCompleted = session.status === 'completed'
  const isError = session.status === 'error'

  const showDebatePanel = !isIdle && !isConfiguring
  const showFeedback = isAwaiting || isCompleted

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
              <span className="text-slate-500 text-xs ml-2 hidden sm:inline">AI Legal Agent</span>
            </div>
          </div>

          <div className="flex-1 mx-6">
            <StatusBar
              status={session.status}
              sessionId={session.sessionId}
              currentRound={session.currentRound}
              numRounds={session.config?.numRounds}
              docName={null}
            />
          </div>

          {!isIdle && (
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
                Use the round summaries below for your legal review.
              </p>
            </div>
          </div>
        )}

        {/* ── STAGE 1: Configure ── */}
        {isConfiguring && (
          <SessionConfig
            onStart={session.createAndStart}
            loading={isRunning}
          />
        )}

        {/* ── STAGE 2 + 3: Debate panel ── */}
        {showDebatePanel && (
          <div className="space-y-8">
            <DebatePanel
              agents={session.agents}
              events={session.events}
              rounds={session.rounds}
              currentRound={session.currentRound}
              currentPhase={session.currentPhase}
              numRounds={session.config?.numRounds || 1}
            />

            {/* ── STAGE 3: Feedback (when awaiting or completed) ── */}
            {showFeedback && (
              <FeedbackForm
                onSubmitFeedback={session.submitFeedback}
                onAccept={session.acceptResult}
                loading={isRunning}
                rounds={session.rounds}
              />
            )}
          </div>
        )}
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-[var(--border)] mt-20 py-6">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between text-xs text-slate-600">
          <span>Gilberto Legal Agent · Powered by Maritaca AI Sabiá-4</span>
          <span>Built with CrewAI + FastAPI + React</span>
        </div>
      </footer>
    </div>
  )
}
