import { useState } from 'react'
import { Users, RefreshCw, Layers, ChevronRight } from 'lucide-react'

const WORKFLOW_OPTIONS = [
  { value: 'full_analysis', label: 'Full Analysis', description: 'Comprehensive risk, compliance, governance and strategy review' },
  { value: 'contract_review', label: 'Contract Review', description: 'Detailed clause-by-clause contract analysis' },
  { value: 'corporate_governance', label: 'Corporate Governance', description: 'Authority, representation, and structural review' },
  { value: 'compliance_check', label: 'Compliance Check', description: 'Brazilian law and regulatory compliance audit' },
]

export function SessionConfig({ onStart, loading }) {
  const [numAgents, setNumAgents] = useState(3)
  const [numRounds, setNumRounds] = useState(2)
  const [workflowType, setWorkflowType] = useState('full_analysis')
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  const handleSubmit = () => {
    if (!file) return
    onStart({ numAgents, numRounds, workflowType }, file)
  }

  const AGENT_ROLES_PREVIEW = [
    'Legal Risk Analyst',
    'Brazilian Compliance Advisor',
    'Negotiation Strategist',
    'Corporate Governance Expert',
    "Devil's Advocate",
  ].slice(0, numAgents)

  return (
    <div className="animate-fade-in space-y-8">
      {/* Header */}
      <div className="text-center space-y-3">
        <h2 className="font-display text-3xl text-gold-400">Configure Your Analysis</h2>
        <p className="text-slate-400 max-w-lg mx-auto text-sm leading-relaxed">
          Define how many legal specialists will debate your document and how many rounds the discussion will run.
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

          {/* Agent count */}
          <div className="card p-5 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-gold-400">
              <Users size={16} />
              Number of Agents — <span className="text-white">{numAgents}</span>
            </label>
            <input
              type="range" min={2} max={5} value={numAgents}
              onChange={(e) => setNumAgents(Number(e.target.value))}
              className="w-full accent-gold-500 cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-500">
              <span>2 (faster)</span><span>5 (deeper)</span>
            </div>
          </div>

          {/* Round count */}
          <div className="card p-5 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium text-gold-400">
              <RefreshCw size={16} />
              Debate Rounds — <span className="text-white">{numRounds}</span>
            </label>
            <input
              type="range" min={1} max={5} value={numRounds}
              onChange={(e) => setNumRounds(Number(e.target.value))}
              className="w-full accent-gold-500 cursor-pointer"
            />
            <div className="flex justify-between text-xs text-slate-500">
              <span>1 (quick)</span><span>5 (thorough)</span>
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
              accept=".txt,.pdf,.docx"
              className="hidden"
              onChange={(e) => setFile(e.target.files[0])}
            />
            <label htmlFor="doc-upload" className="cursor-pointer text-center space-y-3">
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

          {/* Agent lineup preview */}
          <div className="card p-5 space-y-3">
            <p className="text-xs font-medium text-gold-400 uppercase tracking-widest">Agent Lineup</p>
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
            disabled={!file || loading}
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
