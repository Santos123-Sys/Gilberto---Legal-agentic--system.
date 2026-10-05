import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export class AppErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Gilberto interface error', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <main className="min-h-screen bg-[var(--bg-primary)] text-slate-100 px-5 py-16">
          <section role="alert" className="card border border-red-500/30 p-6 max-w-2xl mx-auto">
            <div className="flex items-start gap-3">
              <AlertTriangle className="text-red-400 mt-1 shrink-0" size={20} />
              <div>
                <h1 className="font-display text-xl">The analysis screen hit a display error</h1>
                <p className="text-sm text-slate-400 mt-2">Your analysis may still be running. Reload to reconnect to the saved session, or start a new analysis if the session is no longer available.</p>
                <details className="mt-4 text-xs text-slate-500">
                  <summary className="cursor-pointer hover:text-slate-300">Technical details</summary>
                  <pre className="whitespace-pre-wrap break-words mt-2 rounded bg-slate-950/60 p-3">{this.state.error?.message || 'Unknown interface error'}</pre>
                </details>
                <button type="button" onClick={() => window.location.reload()} className="btn-primary inline-flex items-center gap-2 mt-5">
                  <RefreshCw size={14} /> Reload and reconnect
                </button>
              </div>
            </div>
          </section>
        </main>
      )
    }
    return this.props.children
  }
}
