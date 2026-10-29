import { test as base, expect } from '@playwright/test'

/** Browser UI tests use an explicit fake OIDC round-trip and mock SSE frames.
 * This fake identity lives in Playwright ONLY. Production cannot enable it.
 * The real signed JWT/ownership tests run independently in the backend suite.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('https://id.example.test/authorize**', async route => {
      const url = new URL(route.request().url())
      const state = url.searchParams.get('state')
      const redirect = url.searchParams.get('redirect_uri')
      if (!state || !redirect) throw Error('PKCE state and callback required')
      const callback = new URL(redirect)
      callback.searchParams.set('code', 'one-time-fake-code')
      callback.searchParams.set('state', state)
      await route.fulfill({ status: 302, headers: { location: callback.toString() } })
    })
    await page.route('https://id.example.test/token', async route => {
      const headers = {
        'access-control-allow-origin': 'http://127.0.0.1:5173',
        'access-control-allow-methods': 'POST, OPTIONS',
        'access-control-allow-headers': 'content-type',
        'cache-control': 'no-store',
      }
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers })
        return
      }
      const payload = route.request().postData() || ''
      if (!payload.includes('grant_type=authorization_code') || !payload.includes('code_verifier=')) {
        throw Error('PKCE exchange required')
      }
      await route.fulfill({ status: 200, headers, json: {
        access_token: 'synthetic-browser-test-jwt', expires_in: 600, token_type: 'Bearer',
      } })
    })
    await page.addInitScript(() => {
      const original = window.fetch.bind(window)
      window.fetch = (resource, options = {}) => {
        const url = new URL(typeof resource === 'string' ? resource : resource.url, location.href)
        if (url.pathname.endsWith('/stream')) {
          if (!new Headers(options.headers).has('Authorization')) throw Error('Missing SSE authorization')
          let controller
          const stream = new ReadableStream({ start(c) { controller = c } })
          window.testStreams ||= []
          window.testStreams.push({
            url: url.toString(),
            onmessage({ data }) { controller.enqueue(new TextEncoder().encode('data: ' + data + '\n\n')) },
            close() { try { controller.close() } catch {} },
          })
          return Promise.resolve(new Response(stream, { status: 200, headers: { 'content-type': 'text/event-stream' } }))
        }
        return original(resource, options)
      }
    })
    const nativeGoto = page.goto.bind(page)
    page.goto = async (url, options) => {
      const result = await nativeGoto(url, options)
      if (url === '/' || url === 'http://127.0.0.1:5173/') {
        const signIn = page.getByRole('button', { name: 'Sign in', exact: true })
        await expect(signIn).toBeVisible()
        await signIn.click()
        try {
          await expect(page.locator('#doc-upload')).toBeVisible({ timeout: 5000 })
        } catch {
          throw new Error('Synthetic OIDC callback failed: ' + (await page.locator('body').innerText()).slice(0, 700))
        }
      }
      return result
    }
    await use(page)
  },
})
export { expect }
