import { useState, useCallback, useRef, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const ACTIVE_SESSION_KEY = 'gilberto.activeSession.v1'

function readSavedSession() {
  try { return JSON.parse(localStorage.getItem(ACTIVE_SESSION_KEY) || 'null') } catch { return null }
}

function clearSavedSession() {
  try { localStorage.removeItem(ACTIVE_SESSION_KEY) } catch { /* storage can be disabled */ }
}

function saveSession(value) {
  try { localStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(value)) } catch { /* storage can be disabled */ }
}

function messageFromError(err) {
  if (!navigator.onLine) return 'Sem conexão com a internet. Verifique sua conexão; a análise pode continuar no servidor.'
  return err?.message || 'Ocorreu um erro inesperado.'
}

function apiErrorMessage(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map(issue => {
      if (!issue || typeof issue !== 'object') return String(issue)
      const location = Array.isArray(issue.loc) ? issue.loc.filter(part => part !== 'body').join('.') : ''
      return [location, issue.msg || issue.message].filter(Boolean).join(': ')
    }).filter(Boolean)
    if (messages.length) return messages.join('; ')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.error || detail.detail || JSON.stringify(detail)
  }
  return fallback
}

function statusFromServer(status) {
  if (status === 'created') return 'preview'
  if (['running', 'awaiting_gate', 'awaiting_feedback', 'completed', 'error'].includes(status)) return status
  return 'error'
}

export function useAgenticSession() {
  const [sessionId, setSessionId] = useState(null)
  const [status, setStatus] = useState('idle')
  const [events, setEvents] = useState([])
  const [rounds, setRounds] = useState([])
  const [pendingGates, setPendingGates] = useState([])
  const [gateRecords, setGateRecords] = useState([])
  const [clusterResults, setClusterResults] = useState({})
  const [devilAdvocate, setDevilAdvocate] = useState(null)
  const [finalSynthesis, setFinalSynthesis] = useState(null)
  const [executionMetrics, setExecutionMetrics] = useState({})
  const [error, setError] = useState(null)
  const [config, setConfig] = useState(null)
  const [documentFile, setDocumentFile] = useState(null)
  const [documentName, setDocumentName] = useState(null)
  const [showIntentPreview, setShowIntentPreview] = useState(false)
  const [connectionState, setConnectionState] = useState('idle')
  const [lastEventAt, setLastEventAt] = useState(null)

  const eventSourceRef = useRef(null)
  const cursorRef = useRef(0)
  const connectStreamRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectAttemptsRef = useRef(0)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    }
  }, [])

  const createSession = useCallback(async (sessionConfig, file) => {
    const workflowType = sessionConfig.workflowType ?? sessionConfig.workflow_type
    const workflowTypes = {
      full_analysis: 'general',
      contract_review: 'contract_review',
      corporate_governance: 'governance',
      compliance_check: 'regulatory',
    }
    const apiConfig = {
      num_agents: Number(sessionConfig.numAgents ?? sessionConfig.num_agents ?? 3),
      num_rounds: Number(sessionConfig.numRounds ?? sessionConfig.num_rounds ?? 2),
      workflow_type: workflowTypes[workflowType] || workflowType || 'contract_review',
      jurisdiction: sessionConfig.jurisdiction || 'BR',
      urgency: sessionConfig.urgency || 'normal',
    }

    setStatus('creating')
    setConfig(apiConfig)
    setDocumentFile(file || null)
    setDocumentName(file?.name || null)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiConfig),
      })

      if (!res.ok) {
        const errorBody = await res.json().catch(() => ({}))
        throw new Error(apiErrorMessage(errorBody.detail, `HTTP ${res.status}`))
      }

      const data = await res.json()
      setSessionId(data.session_id)
      setShowIntentPreview(true)
      setStatus('preview')
      return data.session_id
    } catch (err) {
      setError(`Failed to create session: ${err.message}`)
      setStatus('error')
      return null
    }
  }, [])

  const confirmAndStart = useCallback(async (selectedFile = documentFile) => {
    if (!sessionId) {
      setError('Create an analysis session before starting the debate.')
      setStatus('error')
      return false
    }
    if (!(selectedFile instanceof Blob)) {
      setError('Select a contract file before starting the debate.')
      setStatus('error')
      return false
    }

    setStatus('uploading')
    setShowIntentPreview(false)
    setDocumentName(selectedFile.name || documentName)

    try {
      const formData = new FormData()
      formData.append('document', selectedFile)

      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/start`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(apiErrorMessage(err.detail, `HTTP ${res.status}`))
      }

      setStatus('running')
      connectStreamRef.current?.(sessionId, 0)
      return true
    } catch (err) {
      setError(`Failed to start: ${err.message}`)
      setStatus('error')
      return false
    }
  }, [sessionId, documentFile, documentName])

  const connectStream = useCallback((sid, cursor = cursorRef.current) => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    setConnectionState('connecting')
    const url = `${API_BASE}/api/sessions/${sid}/stream?cursor=${cursor}`
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onopen = () => {
      if (eventSourceRef.current !== es) return
      reconnectAttemptsRef.current = 0
      setConnectionState('connected')
    }
    es.onmessage = (msg) => {
      if (eventSourceRef.current !== es) return
      try {
        const event = JSON.parse(msg.data)
        if (event.type !== 'STREAM_END') {
          setEvents(prev => [...prev, event])
          setLastEventAt(event.timestamp || new Date().toISOString())
          cursorRef.current += 1
        }

        switch (event.type) {
          case 'CLUSTER_COMPLETE':
            setClusterResults(prev => ({
              ...prev,
              [event.cluster]: event.summary,
            }))
            break

          case 'DEVILS_ADVOCATE_COMPLETE':
            setDevilAdvocate({
              sad_score: event.sad_score,
              gap_severity_score: event.gap_severity_score,
              identified_gaps: event.identified_gaps,
              unstated_assumptions: event.unstated_assumptions,
              weak_points: event.weak_points,
              cognitive_biases_detected: event.cognitive_biases_detected,
              unasked_questions: event.unasked_questions,
              follow_up_actions: event.follow_up_actions,
            })
            break

          case 'MASTER_MANAGER_COMPLETE':
            setFinalSynthesis(event.summary)
            break

          case 'GATE_TRIGGERED':
            setPendingGates(prev => [...prev, {
              gate_number: event.gate_number,
              ...event.trigger,
              ...event.record,
            }])
            setStatus('awaiting_gate')
            break

          case 'GATE_RESOLVED':
            setPendingGates(prev => prev.filter(g => g.gate_number !== event.gate_number))
            break

          case 'ALL_GATES_RESOLVED':
            setPendingGates([])
            setStatus('awaiting_feedback')
            break

          case 'ROUND_COMPLETE':
            setRounds(prev => [...prev, {
              round: event.round,
              summary: event.summary,
              gates_triggered: event.gates_triggered,
            }])
            break

          case 'DEBATE_COMPLETE':
            setExecutionMetrics(event.execution_metrics || {})
            setGateRecords(event.gate_records || [])
            if (!event.gate_records?.length) {
              setStatus('awaiting_feedback')
            }
            break

          case 'ERROR':
            setError(event.message)
            setStatus('error')
            break

          case 'STREAM_END':
            es.close()
            if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
            setConnectionState('closed')
            break
        }
      } catch (e) {
        console.error('Failed to parse event:', e)
      }
    }

    es.onerror = () => {
      if (eventSourceRef.current !== es) return
      // Reopen with the latest cursor: native EventSource retries the original URL and
      // would replay duplicate events because this API does not emit Last-Event-ID values.
      es.close()
      setConnectionState('reconnecting')
      reconnectAttemptsRef.current += 1
      const delay = Math.min(10000, 1000 * (2 ** Math.min(reconnectAttemptsRef.current - 1, 4)))
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null
        connectStreamRef.current?.(sid, cursorRef.current)
      }, delay)
    }
  }, [])
  connectStreamRef.current = connectStream

  // Keep only the opaque session ID and configuration so a refresh can reconnect.
  useEffect(() => {
    if (!sessionId) {
      return
    }
    saveSession({ sessionId, config, documentName })
  }, [sessionId, config, documentName])

  // Restore an in-flight server session after refresh, then replay its event history.
  useEffect(() => {
    let cancelled = false
    const restore = async () => {
      const saved = readSavedSession()
      if (!saved?.sessionId) return

      try {
        const response = await fetch(`${API_BASE}/api/sessions/${saved.sessionId}/status`)
        if (!response.ok) throw new Error(`Sessão não disponível (HTTP ${response.status})`)
        const remote = await response.json()
        if (cancelled) return
        const restoredStatus = statusFromServer(remote.status)
        if (remote.status === 'created') {
          // The browser cannot restore the document bytes; do not pretend the preview is resumable.
          clearSavedSession()
          return
        }
        setSessionId(saved.sessionId)
        setConfig(saved.config || null)
        setDocumentName(remote.document_name || saved.documentName || null)
        setStatus(restoredStatus)
        setShowIntentPreview(false)
        if (['running', 'awaiting_gate', 'awaiting_feedback', 'completed', 'error'].includes(remote.status)) {
          connectStream(saved.sessionId, 0)
        }
      } catch (err) {
        if (cancelled) return
        clearSavedSession()
        setError(`Não foi possível retomar a análise: ${messageFromError(err)}`)
        setStatus('error')
      }
    }
    restore()
    return () => { cancelled = true }
  }, [connectStream])

  const submitGateDecision = useCallback(async (gateNumber, decision, reasoning, overrideScore) => {
    if (!sessionId) return false

    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/gate-decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          gate_number: gateNumber,
          human_review_id: 'web_user',
          decision,
          reasoning,
          override_score: overrideScore,
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const data = await res.json()

      // Update local state
      setPendingGates(prev => prev.filter(g => g.gate_number !== gateNumber))
      setGateRecords(prev => [...prev, {
        gate_number: gateNumber,
        status: decision === 'approve' ? 'approved' : decision === 'override' ? 'overridden' : 'reanalysis_requested',
        human_decision: { decision, reasoning, human_review_id: 'web_user' },
      }])

      if (data.remaining_pending?.length === 0) {
        setStatus('awaiting_feedback')
      }

      return true
    } catch (err) {
      setError(`Gate decision failed: ${err.message}`)
      return false
    }
  }, [sessionId])

  const submitFeedback = useCallback(async (feedback) => {
    if (!sessionId) return

    setStatus('running')

    try {
      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feedback }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      // Reconnect stream for new events
      connectStream(sessionId, cursorRef.current)
    } catch (err) {
      setError(`Feedback failed: ${err.message}`)
      setStatus('error')
    }
  }, [sessionId, events.length, connectStream])

  const acceptResult = useCallback(async () => {
    if (!sessionId) return

    try {
      await fetch(`${API_BASE}/api/sessions/${sessionId}/accept`, { method: 'POST' })
      setStatus('completed')
    } catch (err) {
      setError(`Accept failed: ${err.message}`)
    }
  }, [sessionId])

  const reset = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    clearSavedSession()
    setSessionId(null)
    setStatus('idle')
    setEvents([])
    setRounds([])
    setPendingGates([])
    setGateRecords([])
    setClusterResults({})
    setDevilAdvocate(null)
    setFinalSynthesis(null)
    setExecutionMetrics({})
    setError(null)
    setConfig(null)
    setDocumentFile(null)
    setDocumentName(null)
    setShowIntentPreview(false)
    cursorRef.current = 0
    setConnectionState('idle')
    setLastEventAt(null)
  }, [])

  return {
    sessionId,
    status,
    events,
    rounds,
    pendingGates,
    gateRecords,
    clusterResults,
    devilAdvocate,
    finalSynthesis,
    executionMetrics,
    error,
    config,
    documentName,
    showIntentPreview,
    connectionState,
    lastEventAt,
    reconnect: () => sessionId && connectStream(sessionId, cursorRef.current),
    createSession,
    confirmAndStart,
    submitGateDecision,
    submitFeedback,
    acceptResult,
    reset,
    setShowIntentPreview,
  }
}
