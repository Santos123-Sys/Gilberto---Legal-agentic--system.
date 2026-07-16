import { useState, useCallback, useRef, useEffect } from 'react'
import { api, openDebateStream } from '../services/api'

const INITIAL_STATE = {
  sessionId: null,
  status: 'idle',       // idle | creating | uploading | running | awaiting_feedback | completed | error
  config: null,
  events: [],
  rounds: [],
  agents: {},           // { agentRole: { status, lastContent } }
  currentRound: 0,
  currentPhase: null,   // analysis | voting | aggregation
  latestSummary: null,
  error: null,
}

export function useDebateSession() {
  const [state, setState] = useState(INITIAL_STATE)
  const streamCleanupRef = useRef(null)
  const eventCursorRef = useRef(0)

  // ── State helpers ──────────────────────────

  const patch = useCallback((updates) => {
    setState((prev) => ({ ...prev, ...updates }))
  }, [])

  const addEvent = useCallback((event) => {
    setState((prev) => ({ ...prev, events: [...prev.events, event] }))
  }, [])

  // ── SSE event handler ──────────────────────

  const handleEvent = useCallback((event) => {
    addEvent(event)
    eventCursorRef.current += 1

    switch (event.type) {
      case 'DEBATE_START':
        patch({ status: 'running', currentRound: 0 })
        break

      case 'ROUND_START':
        patch({ currentRound: event.round, currentPhase: null })
        break

      case 'PHASE_START':
        patch({ currentPhase: event.phase })
        break

      case 'AGENT_THINKING':
        setState((prev) => ({
          ...prev,
          agents: {
            ...prev.agents,
            [event.agent]: { status: 'thinking', lastContent: null },
          },
        }))
        break

      case 'AGENT_ANALYSIS_COMPLETE':
        setState((prev) => ({
          ...prev,
          agents: {
            ...prev.agents,
            [event.agent]: { status: 'done', lastContent: event.content, parsed: event.parsed },
          },
        }))
        break

      case 'AGENT_VOTING':
        setState((prev) => ({
          ...prev,
          agents: {
            ...prev.agents,
            [event.agent]: { ...prev.agents[event.agent], status: 'voting' },
          },
        }))
        break

      case 'AGENT_VOTE_CAST':
        setState((prev) => ({
          ...prev,
          agents: {
            ...prev.agents,
            [event.voter]: { ...prev.agents[event.voter], status: 'voted', scores: event.scores },
          },
        }))
        break

      case 'ROUND_COMPLETE':
        setState((prev) => ({
          ...prev,
          rounds: [...prev.rounds, event.round_data],
          latestSummary: event.summary,
          currentPhase: null,
          agents: Object.fromEntries(
            Object.entries(prev.agents).map(([k, v]) => [k, { ...v, status: 'idle' }])
          ),
        }))
        break

      case 'DEBATE_COMPLETE':
        patch({ status: 'awaiting_feedback' })
        break

      case 'FEEDBACK_AGENT_CREATED':
        setState((prev) => ({
          ...prev,
          agents: {
            ...prev.agents,
            [event.agent]: { status: 'new', lastContent: null },
          },
        }))
        break

      case 'STREAM_END':
        break

      case 'ERROR':
        patch({ status: 'error', error: event.message })
        break

      default:
        break
    }
  }, [addEvent, patch])

  // ── Public actions ─────────────────────────

  const createAndStart = useCallback(async (config, file) => {
    try {
      patch({ status: 'creating', error: null })

      // 1. Create session
      const session = await api.createSession(
        config.numAgents,
        config.numRounds,
        config.workflowType
      )
      patch({ sessionId: session.session_id, config, status: 'uploading' })

      // 2. Upload document + start
      await api.startSession(session.session_id, file)
      patch({ status: 'running' })

      // 3. Open SSE stream
      if (streamCleanupRef.current) streamCleanupRef.current()
      streamCleanupRef.current = openDebateStream(
        session.session_id,
        handleEvent,
        0
      )
    } catch (err) {
      patch({ status: 'error', error: err.message })
    }
  }, [patch, handleEvent])

  const submitFeedback = useCallback(async (feedback) => {
    const { sessionId } = state
    if (!sessionId) return
    try {
      patch({ status: 'running' })
      await api.submitFeedback(sessionId, feedback)
    } catch (err) {
      patch({ status: 'error', error: err.message })
    }
  }, [state, patch])

  const acceptResult = useCallback(async () => {
    const { sessionId } = state
    if (!sessionId) return
    try {
      await api.acceptResult(sessionId)
      patch({ status: 'completed' })
      if (streamCleanupRef.current) streamCleanupRef.current()
    } catch (err) {
      patch({ status: 'error', error: err.message })
    }
  }, [state, patch])

  const reset = useCallback(() => {
    if (streamCleanupRef.current) streamCleanupRef.current()
    eventCursorRef.current = 0
    setState(INITIAL_STATE)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamCleanupRef.current) streamCleanupRef.current()
    }
  }, [])

  return {
    ...state,
    createAndStart,
    submitFeedback,
    acceptResult,
    reset,
  }
}
