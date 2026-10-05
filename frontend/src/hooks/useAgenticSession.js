import { useState, useCallback, useRef, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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
  const [showIntentPreview, setShowIntentPreview] = useState(false)

  const eventSourceRef = useRef(null)
  const cursorRef = useRef(0)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
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
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/api/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiConfig),
      })

      if (!res.ok) {
        const errorBody = await res.json().catch(() => ({}))
        throw new Error(errorBody.detail || `HTTP ${res.status}`)
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
    if (!selectedFile) {
      setError('Select a contract file before starting the debate.')
      setStatus('error')
      return false
    }

    setStatus('uploading')
    setShowIntentPreview(false)

    try {
      const formData = new FormData()
      formData.append('document', selectedFile)

      const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/start`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      setStatus('running')
      connectStream(sessionId)
      return true
    } catch (err) {
      setError(`Failed to start: ${err.message}`)
      setStatus('error')
      return false
    }
  }, [sessionId, documentFile])

  const connectStream = useCallback((sid) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const url = `${API_BASE}/api/sessions/${sid}/stream?cursor=${cursorRef.current}`
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data)
        setEvents(prev => [...prev, event])
        cursorRef.current += 1

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
            break
        }
      } catch (e) {
        console.error('Failed to parse event:', e)
      }
    }

    es.onerror = () => {
      // EventSource auto-reconnects, but if session is done, close
      if (status === 'completed' || status === 'error') {
        es.close()
      }
    }
  }, [status])

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
      cursorRef.current = events.length
      connectStream(sessionId)
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
    setShowIntentPreview(false)
    cursorRef.current = 0
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
    showIntentPreview,
    createSession,
    confirmAndStart,
    submitGateDecision,
    submitFeedback,
    acceptResult,
    reset,
    setShowIntentPreview,
  }
}
