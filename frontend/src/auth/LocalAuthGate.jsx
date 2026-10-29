import { useEffect, useState } from 'react'
import { bootstrapAdmin, bootstrapAvailable, changeLocalPassword, getLocalUser, signInLocal, signOutLocal } from './localIdentity'

export function LocalAuthGate({ children }) {
  const [status, setStatus] = useState('checking')
  const [bootstrapOpen, setBootstrapOpen] = useState(false)
  const [bootstrapToken, setBootstrapToken] = useState('')
  const [bootstrapConfirm, setBootstrapConfirm] = useState('')
  const [user, setUser] = useState(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  useEffect(() => {
    let active = true
    getLocalUser().then(account => {
      if (!active) return
      setUser(account)
      setStatus(account ? 'authenticated' : 'unauthenticated')
      if (!account) {
        bootstrapAvailable().then(enabled => { if (active) setBootstrapOpen(enabled) })
          .catch(() => {})
      }
    }).catch(error => {
      if (!active) return
      setMessage(error.message)
      setStatus('unavailable')
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const expired = () => {
      setUser(null)
      setStatus('unauthenticated')
      setMessage('Your session expired or was revoked. Sign in again.')
      localStorage.removeItem('gilberto.activeSession.v1')
    }
    window.addEventListener('gilberto:local-session-expired', expired)
    return () => window.removeEventListener('gilberto:local-session-expired', expired)
  }, [])

  const signIn = async event => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      const account = await signInLocal(email, password)
      setUser(account)
      setPassword('')
      setStatus('authenticated')
    } catch (error) {
      setMessage(error.message)
      setStatus('unauthenticated')
    } finally {
      setBusy(false)
    }
  }

  const createFirstAdmin = async event => {
    event.preventDefault()
    if (password !== bootstrapConfirm) {
      setMessage('Password confirmation does not match.')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      const account = await bootstrapAdmin(email, password, bootstrapToken)
      setUser(account)
      setBootstrapOpen(false)
      setBootstrapToken('')
      setBootstrapConfirm('')
      setPassword('')
      setStatus('authenticated')
    } catch (error) {
      setMessage(error.message)
    } finally { setBusy(false) }
  }

  const signOut = async () => {
    setBusy(true)
    setMessage('')
    try {
      await signOutLocal()
      setUser(null)
      setStatus('unauthenticated')
      setSettingsOpen(false)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (error) {
      setMessage(error.message)
    } finally {
      setBusy(false)
    }
  }

  const changePassword = async event => {
    event.preventDefault()
    if (newPassword !== confirmPassword) {
      setMessage('New password and confirmation do not match.')
      return
    }
    setBusy(true)
    setMessage('')
    try {
      await changeLocalPassword(currentPassword, newPassword)
      setMessage('Password changed. All other devices have been signed out.')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (error) {
      setMessage(error.message)
    } finally { setBusy(false) }
  }

  if (status === 'checking') return <main aria-busy="true" className="p-8 text-slate-200">
    Checking your secure session…
  </main>
  if (status !== 'authenticated') return (
    <main id="workspace-main" tabIndex={-1} className="mx-auto max-w-md p-6 sm:p-10 space-y-5 text-slate-200">
      <h1 className="text-2xl font-semibold">Gilberto — Secure sign-in</h1>
      <p className="text-sm text-slate-400">
        Administrator-issued accounts only. Sign in before accessing legal documents.
      </p>
      {message && <p role="alert" className="text-red-400">{message}</p>}
      <form onSubmit={bootstrapOpen ? createFirstAdmin : signIn} className="space-y-4">
        {bootstrapOpen && <p role="status" className="text-yellow-300 text-sm">
          First administrator setup — enter your one-time staging setup token.
        </p>}
        <label htmlFor="identity-email" className="block text-sm">Email</label>
        <input id="identity-email" type="email" autoComplete="username" required maxLength={254}
          value={email} onChange={e => setEmail(e.target.value)}
          className="w-full rounded-md border border-slate-600 bg-slate-900 p-3" />
        <label htmlFor="identity-password" className="block text-sm">Password</label>
        <input id="identity-password" type="password" autoComplete="current-password"
          required value={password} onChange={e => setPassword(e.target.value)}
          className="w-full rounded-md border border-slate-600 bg-slate-900 p-3" />
        {bootstrapOpen && <>
          <label htmlFor="bootstrap-confirm" className="block text-sm">Confirm administrator password</label>
          <input id="bootstrap-confirm" type="password" autoComplete="new-password"
            value={bootstrapConfirm} onChange={e => setBootstrapConfirm(e.target.value)}
            required minLength={12} className="w-full rounded-md border border-slate-600 bg-slate-900 p-3" />
          <label htmlFor="bootstrap-token" className="block text-sm">One-time setup token</label>
          <input id="bootstrap-token" type="password" autoComplete="off" required
            value={bootstrapToken} onChange={e => setBootstrapToken(e.target.value)}
            className="w-full rounded-md border border-slate-600 bg-slate-900 p-3" />
        </>}
        <button type="submit" disabled={busy} className="rounded-lg bg-gold-500 px-5 py-3 text-slate-950 disabled:opacity-50">
          {busy ? 'Processing…' : bootstrapOpen ? 'Create first administrator' : 'Sign in'}
        </button>
      </form>
      {status === 'unavailable' && <p className="text-sm text-yellow-300">
        Identity backend is unavailable; account access is not permitted.
      </p>}
    </main>
  )
  return <>
    {children}
    <div className="fixed right-2 bottom-2 z-[100] flex gap-2 items-center rounded-lg border border-slate-700 bg-slate-950 p-2">
      <span className="hidden sm:inline text-xs text-slate-400">{user?.email}</span>
      <button type="button" onClick={() => setSettingsOpen(x => !x)}
        className="rounded border border-slate-600 px-3 py-2 text-xs text-slate-200">Account</button>
      <button type="button" disabled={busy} onClick={signOut}
        className="rounded border border-slate-600 px-3 py-2 text-xs text-slate-200">Sign out</button>
    </div>
    {settingsOpen && (
      <section aria-label="Account settings" className="fixed bottom-16 right-2 z-[100] w-[min(22rem,calc(100vw-1rem))] rounded-lg border border-slate-600 bg-slate-950 p-4 text-slate-200 shadow-xl">
        <h2 className="mb-3 text-lg font-medium">Change password</h2>
        {message && <p role="status" className="mb-2 text-sm">{message}</p>}
        <form onSubmit={changePassword} className="space-y-3">
          <label htmlFor="current-password" className="block text-sm">Current password</label>
          <input id="current-password" type="password" autoComplete="current-password" required
            value={currentPassword} onChange={e => setCurrentPassword(e.target.value)}
            className="w-full rounded border border-slate-600 bg-slate-900 p-2" />
          <label htmlFor="new-password" className="block text-sm">New password (12+ characters)</label>
          <input id="new-password" type="password" autoComplete="new-password" minLength={12} required
            value={newPassword} onChange={e => setNewPassword(e.target.value)}
            className="w-full rounded border border-slate-600 bg-slate-900 p-2" />
          <label htmlFor="confirm-password" className="block text-sm">Confirm new password</label>
          <input id="confirm-password" type="password" autoComplete="new-password" minLength={12} required
            value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)}
            className="w-full rounded border border-slate-600 bg-slate-900 p-2" />
          <button type="submit" disabled={busy} className="rounded bg-gold-500 px-4 py-2 text-slate-950 disabled:opacity-50">
            Update password
          </button>
        </form>
      </section>
    )}
  </>
}
