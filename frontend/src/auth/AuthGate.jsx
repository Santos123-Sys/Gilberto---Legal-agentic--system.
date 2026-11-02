import { useEffect, useState } from 'react'
import { LocalAuthGate } from './LocalAuthGate'
import { finishLogin, hasPendingCallback, hasAccessToken, isAuthConfigured, logout, startLogin } from './oidc'

/** No legal workspace is mounted before a token is obtained via PKCE. */
export function AuthGate({ children }) {
  return import.meta.env.VITE_AUTH_MODE === 'local'
    ? <LocalAuthGate>{children}</LocalAuthGate>
    : <OidcAuthGate>{children}</OidcAuthGate>
}

function OidcAuthGate({ children }) {
  const [status, setStatus] = useState('checking')
  const [message, setMessage] = useState('')
  useEffect(() => {
    let active = true
    const callback = new URL(location.href).searchParams
    if (callback.has('code') || callback.has('state') || callback.has('error') || hasPendingCallback()) {
      finishLogin().then(() => { if (active) setStatus('authenticated') })
        .catch(error => { if (active) { setMessage(error.message); setStatus('error') } })
    } else setStatus(hasAccessToken() ? 'authenticated' : 'unauthenticated')
    return () => { active = false }
  }, [])

  if (status === 'checking') return <main aria-busy="true" className="p-8 text-slate-200">Verificando o acesso…</main>
  if (status !== 'authenticated') return (
    <main id="workspace-main" tabIndex={-1} className="mx-auto max-w-md p-8 space-y-5 text-slate-200">
      <h1 className="text-xl font-semibold">Acesso seguro ao Gilberto</h1>
      <p>Autentique-se antes de acessar sessões ou documentos jurídicos confidenciais.</p>
      {message && <p role="alert" className="text-red-400">{message}</p>}
      {isAuthConfigured() ? (
        <button type="button" className="rounded-lg bg-gold-500 px-5 py-3 text-slate-950"
          onClick={() => { startLogin().catch(err => { setMessage(err.message); setStatus('error') }) }}>Entrar</button>
      ) : <p role="alert">Um administrador precisa configurar o provedor de identidade OIDC.</p>}
    </main>
  )
  return <>
    {children}
    <div className="fixed right-2 bottom-2 z-[100]">
      <button type="button" className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200"
        onClick={() => { logout(); setStatus('unauthenticated') }}>Sair</button>
    </div>
  </>
}
