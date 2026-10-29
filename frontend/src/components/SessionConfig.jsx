import { useState, useEffect } from 'react'
import { authorizedFetch } from '../auth/client'
import { Users, RefreshCw, Layers, ChevronRight } from 'lucide-react'

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024
const ALLOWED_FILE_TYPES = /\.(txt|md|pdf|docx)$/i

const WORKFLOW_OPTIONS = [
  { value: 'full_analysis', label: 'Full Analysis', description: 'Comprehensive risk, compliance, governance and strategy review' },
  { value: 'contract_review', label: 'Contract Review', description: 'Detailed clause-by-clause contract analysis' },
  { value: 'corporate_governance', label: 'Corporate Governance', description: 'Authority, representation, and structural review' },
  { value: 'compliance_check', label: 'Compliance Check', description: 'Brazilian law and regulatory compliance audit' },
]

export function SessionConfig({ onStart, loading }) {
  const [reviewDepth, setReviewDepth] = useState('full')
  const [numRounds, setNumRounds] = useState(1)
  const [workflowType, setWorkflowType] = useState('full_analysis')
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [backupConfigured, setBackupConfigured] = useState(false)
  const [providerMode, setProviderMode] = useState('primary')
  const [backupConsent, setBackupConsent] = useState(false)
  useEffect(() => {
    let active = true
    const base = import.meta.env.VITE_AUTH_MODE === 'local' ? '' : (import.meta.env.VITE_API_URL || 'http://localhost:8000')
    authorizedFetch(`${base}/api/health`).then(response => response.ok ? response.json() : null)
      .then(data => { if (active) setBackupConfigured(data?.backup_provider?.configured === true) })
      .catch(() => { if (active) setBackupConfigured(false) })
    return () => { active = false }
  }, [])


  const selectFile = (candidate) => {
    if (!candidate) return
    if (!ALLOWED_FILE_TYPES.test(candidate.name || '')) {
      setFile(null)
      setFileError('Unsupported file type. Select a .txt, .md, .pdf, or .docx document.')
    } else if (candidate.size > MAX_UPLOAD_BYTES) {
      setFile(null)
      setFileError('Document exceeds the 10 MB upload limit. Select a smaller file.')
    } else {
      setFile(candidate)
      setFileError('')
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    selectFile(e.dataTransfer.files[0])
  }

  const handleSubmit = () => {
    if (!file) return
    if (providerMode === 'backup' && (!backupConfigured || !backupConsent)) return
    onStart({ numRounds, workflowType, reviewDepth, providerMode,
              backupConsent: providerMode === 'backup' && backupConsent }, file)
  }

  const AGENT_ROLES_PREVIEW = [
    'Legal Risk Analyst',
    'Brazilian Compliance Advisor',
    'Negotiation Strategist',
    'Corporate Governance Expert',
    "Devil's Advocate",
  ]

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header */}
      <div className="text-center space-y-3">
        <h2 className="font-display text-3xl text-gold-400">Configure Your Analysis</h2>
        <p className="text-slate-400 max-w-lg mx-auto text-sm leading-relaxed">
          Choose your review workflow and number of rounds. The server selects the configured specialist teams; model requests are staggered to respect provider limits.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left col: Controls */}
        <div className="space-y-5">

          {/* Workflow type */}
          <div className="card p-5 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-gold-400">
              <Layers size={16} />
              Analysis Workflow
            </label>
            <div className="grid grid-cols-1 gap-2">
              {WORKFLOW_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setWorkflowType(opt.value)}
                  className={`text-left px-4 py-3 rounded-lg border transition-all duration-200 ${
                    workflowType === opt.value
                      ? 'border-gold-500 bg-gold-500/10 text-gold-300'
                      : 'border-slate-700 bg-slate-800/30 text-slate-400 hover:border-slate-500'
                  }`}
                >
                  <div className="text-sm font-medium">{opt.label}</div>
                  <div className="text-xs opacity-70 mt-0.5">{opt.description}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="card p-5 space-y-3">
            <label htmlFor="review-depth" className="block text-sm text-gold-400">Review depth</label>
            <select id="review-depth" value={reviewDepth} onChange={e => setReviewDepth(e.target.value)} className="w-full bg-slate-800 text-slate-200 rounded p-3">
              <option value="full">Full specialist review — 47 calls per round</option>
              <option value="focused">Focused draft — 12 calls per round</option>
            </select>
            <p className="text-sm text-slate-400">Both cover the five configured workstreams. Focused drafts use one reviewer per workstream and have less independent scrutiny. Call counts shown assume all five workstreams are enabled; the next screen shows the actual plan.</p>
          </div>
          {/* Explicit legal-document transfer consent for alternate inference. */}
          <fieldset className="card p-5 space-y-3">
            <legend className="text-sm font-medium text-gold-400 px-1">AI provider and continuity</legend>
            <label htmlFor="provider-mode" className="text-xs text-slate-300 block">Inference destination</label>
            <select id="provider-mode" aria-label="Inference provider" value={providerMode}
              onChange={event => { setProviderMode(event.target.value); setBackupConsent(false) }}
              className="w-full bg-slate-800 text-slate-200 rounded p-3">
              <option value="primary">Maritaca (primary)</option>
              {backupConfigured && <option value="backup">Operator-approved backup provider</option>}
            </select>
            {!backupConfigured && <p className="text-xs text-slate-400">No approved backup endpoint is configured. Maritaca failures stop dispatch and retain saved findings.</p>}
            {providerMode === 'backup' && <label className="flex items-start gap-2 text-sm text-slate-300">
              <input type="checkbox" checked={backupConsent} onChange={event => setBackupConsent(event.target.checked)} aria-label="Authorize backup provider transfer" className="mt-1" />
              I authorize this legal document and its derived prompts to be processed by the operator-approved backup AI provider. I understand this starts a separate review and may incur additional charges.
            </label>}
            <p className="text-xs text-amber-300">No silent automatic fallback or retry occurs after an uncertain provider response. An incomplete review is never certified as complete.</p>
          </fieldset>
          {/* Round count */}
          <div className="card p-5 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-gold-400">
              <RefreshCw size={16} />
              Debate Rounds — <span className="text-white">{numRounds}</span>
            </label>
            <input
              aria-label="Debate rounds" type="range" min={1} max={3} value={numRounds}
              onChange={(e) => setNumRounds(Number(e.target.value))}
              className="w-full accent-gold-500 cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-500">
              <span>1 (quick)</span><span>3 (thorough)</span>
            </div>
          </div>
        </div>

        {/* Right col: Upload + Preview */}
        <div className="space-y-5">
          {/* File drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`card p-8 flex flex-col items-center justify-center gap-4 cursor-pointer transition-all duration-200 min-h-[200px] ${
              dragging ? 'border-gold-500 bg-gold-500/5' : 'hover:border-slate-500'
            } ${file ? 'border-green-500/40 bg-green-500/5' : ''}`}
          >
            <input
              type="file"
              id="doc-upload"
              accept=".txt,.md,.pdf,.docx"
              className="sr-only"
              onChange={(e) => selectFile(e.target.files[0])}
            />
            <label htmlFor="doc-upload" tabIndex={0} role="button" onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('doc-upload').click() } }} className="cursor-pointer text-center space-y-3">
              <div className="text-4xl">{file ? '📄' : '📁'}</div>
              {file ? (
                <>
                  <p className="text-green-400 font-medium text-sm">{file.name}</p>
                  <p className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB · Click to change</p>
                </>
              ) : (
                <>
                  <p className="text-slate-300 text-sm font-medium">Drop your legal document here</p>
                  <p className="text-xs text-slate-500">or click to browse · .txt, .pdf, .docx</p>
                </>
              )}
            </label>
          </div>

          {fileError && <p role="alert" className="text-red-400 text-sm">{fileError}</p>}

          {/* Agent lineup preview */}
          <div className="card p-5 space-y-3">
            <p className="text-xs font-medium text-gold-400 uppercase tracking-widest">Review coverage</p>
            <div className="space-y-2">
              {AGENT_ROLES_PREVIEW.map((role, i) => (
                <div key={role} className="flex items-center gap-3 py-1.5">
                  <div className="w-6 h-6 rounded-full bg-gold-500/20 border border-gold-500/40 flex items-center justify-center text-xs text-gold-400 font-mono font-bold">
                    {i + 1}
                  </div>
                  <span className="text-sm text-slate-300">{role}</span>
                </div>
              ))}
              <div className="flex items-center gap-3 py-1.5 opacity-50">
                <div className="w-6 h-6 rounded-full border border-dashed border-slate-600 flex items-center justify-center text-xs text-slate-500">
                  +
                </div>
                <span className="text-xs text-slate-500">Manager Agent (always present)</span>
              </div>
            </div>
          </div>

          {/* Start button */}
          <button
            onClick={handleSubmit}
            disabled={!file || loading || (providerMode === 'backup' && (!backupConfigured || !backupConsent))}
            className="w-full py-4 rounded-xl font-semibold text-sm tracking-wide transition-all duration-200 flex items-center justify-center gap-2
              disabled:opacity-40 disabled:cursor-not-allowed
              enabled:bg-gold-500 enabled:text-slate-950 enabled:hover:bg-gold-400 enabled:active:scale-95"
          >
            {loading ? (
              <><RefreshCw size={16} className="animate-spin" /> Starting debate…</>
            ) : (
              <>Start Debate <ChevronRight size={16} /></>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

