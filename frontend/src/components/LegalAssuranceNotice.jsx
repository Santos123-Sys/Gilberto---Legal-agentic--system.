import React from 'react'
import { legalAssuranceView } from '../auth/legalAssurance'

export function LegalAssuranceNotice({ synthesis }) {
  const status = legalAssuranceView(synthesis)
  return (
    <section role="alert" aria-label="Validação da análise jurídica" className="card p-4 border-2 border-amber-500/60 space-y-2">
      <h2 className="text-lg font-semibold text-amber-300">{status.text}</h2>
      <p className="text-sm text-slate-200">{status.detail}</p>
      <p className="text-xs text-slate-300">
        Status: {status.status}. Decisões judiciais verificadas independentemente: {status.independentlyVerifiedCases}.
      </p>
      {status.claimsCount !== null && (
        <p className="text-xs text-slate-300">
          Alegações analisadas quanto à evidência: {status.claimsCount}.
          Trechos contratuais localizados: {status.contractMatches ?? 'Não disponível'}.
        </p>
      )}
    </section>
  )
}
