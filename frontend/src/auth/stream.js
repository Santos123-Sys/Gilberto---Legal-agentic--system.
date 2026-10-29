import { authorizedFetch } from './client'

/** Fetch-based authenticated SSE with exact cursor replay and AbortController.
 * Native EventSource cannot supply Authorization headers.
 */
export class AuthenticatedEventStream {
  constructor(url) {
    this.url = url
    this.closed = false
    this.controller = new AbortController()
    this.consume()
  }
  close() {
    this.closed = true
    this.controller.abort()
  }
  async consume() {
    try {
      const response = await authorizedFetch(this.url, {
        signal: this.controller.signal,
        headers: { Accept: 'text/event-stream' },
      })
      if (!response.ok || !response.body ||
          !response.headers.get('content-type')?.startsWith('text/event-stream')) {
        throw new Error('Authenticated event history could not be opened.')
      }
      if (this.closed) return
      this.onopen?.()
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (!this.closed) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n')
        let index
        while ((index = buffer.indexOf('\n\n')) >= 0) {
          const frame = buffer.slice(0, index)
          buffer = buffer.slice(index + 2)
          const payload = frame.split('\n').filter(line => line.startsWith('data:'))
            .map(line => line.slice(5).trimStart()).join('\n')
          if (payload && !this.closed) this.onmessage?.({ data: payload })
        }
        if (buffer.length > 2_000_000) throw new Error('Progress frame exceeds safety limit.')
      }
      if (!this.closed) this.onerror?.(new Error('Progress stream disconnected.'))
    } catch (error) {
      if (!this.closed && error.name !== 'AbortError') this.onerror?.(error)
    }
  }
}
