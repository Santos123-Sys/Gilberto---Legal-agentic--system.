const BASE = import.meta.env.VITE_API_URL || ''

// ─────────────────────────────────────────────
//  Core fetch wrapper
// ─────────────────────────────────────────────
async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ─────────────────────────────────────────────
//  Session API
// ─────────────────────────────────────────────

export const api = {
  /** Create a new debate session */
  createSession: (numAgents, numRounds, workflowType) =>
    request('/api/sessions', {
      method: 'POST',
      body: JSON.stringify({
        num_agents: numAgents,
        num_rounds: numRounds,
        workflow_type: workflowType,
      }),
    }),

  /** Upload document and start debate */
  startSession: (sessionId, file) => {
    const form = new FormData()
    form.append('document', file)
    return fetch(`${BASE}/api/sessions/${sessionId}/start`, {
      method: 'POST',
      body: form,
    }).then(async (res) => {
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      return res.json()
    })
  },

  /** Get session status */
  getStatus: (sessionId) => request(`/api/sessions/${sessionId}/status`),

  /** Get full results */
  getResults: (sessionId) => request(`/api/sessions/${sessionId}/results`),

  /** Submit user feedback */
  submitFeedback: (sessionId, feedback) =>
    request(`/api/sessions/${sessionId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ feedback }),
    }),

  /** Accept final result */
  acceptResult: (sessionId) =>
    request(`/api/sessions/${sessionId}/accept`, { method: 'POST' }),

  /** Health check */
  health: () => request('/api/health'),
}

// ─────────────────────────────────────────────
//  SSE Stream helper
// ─────────────────────────────────────────────

/**
 * Opens a Server-Sent Events connection to the backend.
 * Calls onEvent(event) for every parsed event.
 * Returns a cleanup function.
 */
export function openDebateStream(sessionId, onEvent, cursor = 0) {
  const url = `${BASE}/api/sessions/${sessionId}/stream?cursor=${cursor}`
  const source = new EventSource(url)

  source.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data)
      onEvent(parsed)
      if (parsed.type === 'STREAM_END') {
        source.close()
      }
    } catch {
      // ignore malformed frames
    }
  }

  source.onerror = () => {
    // EventSource auto-reconnects; log silently
    console.warn('[SSE] Connection lost, retrying…')
  }

  return () => source.close()
}
