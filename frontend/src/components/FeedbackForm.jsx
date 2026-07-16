import { useState } from 'react'
import { MessageSquare, Send, CheckCircle, RefreshCw, ChevronRight } from 'lucide-react'

const FEEDBACK_TEMPLATES = [
  "The agents overlooked the indemnification clause. Please analyze it in more depth.",
  "I disagree with the risk assessment on the payment terms. Please re-examine.",
  "Focus more on representation authority and who can bind the company.",
  "Are there any LGPD compliance issues that were not addressed?",
]

export function FeedbackForm({ onSubmitFeedback, onAccept, loading, rounds }) {
  const [feedback, setFeedback] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = () => {
    if (!feedback.trim() || loading) return
    setSubmitted(true)
    onSubmitFeedback(feedback.trim())
    setFeedback('')
    setTimeout(() => setSubmitted(false), 2000)
  }

  const latestRound = rounds[rounds.length - 1]
  const latestSummary = latestRound?.summary?.parsed

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Debate complete banner */}
      <div className="card border border-gold-500/30 bg-gold-500/5 p-5 flex items-start gap-4">
        <div className="text-3xl">⚖️</div>
        <div>
          <h3 className="font-display text-lg text-gold-400">Debate Complete</h3>
          <p className="text-sm text-slate-400 mt-1 leading-relaxed">
            {rounds.length} round{rounds.length !== 1 ? 's' : ''} of analysis finished.
            Review the findings below. You may submit feedback to trigger an additional debate round
            with a Feedback Advocate agent, or accept the current analysis as final.
          </p>
        </div>
      </div>

      {/* Latest summary highlight */}
      {latestSummary && !latestSummary.raw_content && (
        <div className="card p-5 space-y-4">
          <h4 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <CheckCircle size={14} className="text-green-400" />
            Final Analysis Summary
          </h4>
          {latestSummary.most_valuable_insight && (
            <div className="bg-slate-800/40 rounded-lg p-4 border-l-2 border-gold-500">
              <p className="text-xs text-gold-400 mb-1 font-medium">Most Valuable Insight</p>
              <p className="text-sm text-slate-300 leading-relaxed">{latestSummary.most_valuable_insight}</p>
            </div>
          )}
          {latestSummary.top_risks?.slice(0, 3).map((r, i) => (
            <div key={i} className="flex items-start gap-3 text-sm">
              <span className="font-mono text-gold-500 text-xs mt-0.5">#{r.priority_rank || i + 1}</span>
              <div>
                <p className="text-slate-300">{r.risk}</p>
                {r.recommended_action && (
                  <p className="text-xs text-slate-500 mt-0.5">→ {r.recommended_action}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Feedback input */}
      <div className="card p-5 space-y-4">
        <label className="flex items-center gap-2 text-sm font-medium text-gold-400">
          <MessageSquare size={15} />
          Submit Feedback for Next Round
        </label>

        {/* Quick templates */}
        <div className="space-y-1">
          <p className="text-xs text-slate-500 mb-2">Quick templates:</p>
          <div className="flex flex-wrap gap-2">
            {FEEDBACK_TEMPLATES.map((t, i) => (
              <button
                key={i}
                onClick={() => setFeedback(t)}
                className="text-xs px-3 py-1.5 rounded-full border border-slate-600 text-slate-400 hover:border-gold-500/50 hover:text-gold-400 transition-colors"
              >
                {t.split(' ').slice(0, 5).join(' ')}…
              </button>
            ))}
          </div>
        </div>

        <textarea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="Describe what the agents missed, what you disagree with, or what specific area needs deeper analysis…"
          rows={4}
          className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-3 text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-gold-500/50 resize-none transition-colors"
        />

        <div className="flex items-center gap-3">
          <button
            onClick={handleSubmit}
            disabled={!feedback.trim() || loading || submitted}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all
              disabled:opacity-40 disabled:cursor-not-allowed
              enabled:bg-blue-600 enabled:hover:bg-blue-500 enabled:text-white enabled:active:scale-95"
          >
            {loading ? (
              <><RefreshCw size={14} className="animate-spin" /> Running…</>
            ) : submitted ? (
              <><CheckCircle size={14} /> Submitted</>
            ) : (
              <><Send size={14} /> Submit & Re-Debate</>
            )}
          </button>

          <button
            onClick={onAccept}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all
              disabled:opacity-40 disabled:cursor-not-allowed
              enabled:bg-gold-500 enabled:hover:bg-gold-400 enabled:text-slate-950 enabled:active:scale-95"
          >
            Accept Final Analysis <ChevronRight size={14} />
          </button>
        </div>
        <p className="text-xs text-slate-600">
          Submitting feedback creates a new Feedback Advocate agent and starts an additional debate round.
        </p>
      </div>
    </div>
  )
}
