/** Unverified source provenance is explicit even for legacy/unlabeled results.
 * Model consensus, high confidence and user acceptance never imply legal signoff.
 */
export function legalAssuranceView(synthesis) {
  const audit = synthesis?.legal_assurance
  const scoped = audit?.scope === 'BRAZILIAN_LAW_ONLY'
  const assessed = Number.isInteger(audit?.material_claims_assessed)
    ? Math.max(0, audit.material_claims_assessed) : null
  const matched = Number.isInteger(audit?.contract_quotes_matched)
    ? Math.max(0, audit.contract_quotes_matched) : null
  return {
    status: 'LEGAL_REVIEW_REQUIRED',
    text: scoped ? 'Análise jurídica brasileira — rascunho não verificado.'
                 : 'Rascunho jurídico sem validação independente de autoridades legais.',
    detail: 'Cláusulas localizadas não comprovam interpretação jurídica. Verifique leis, precedentes, vigência e contexto em fontes oficiais e com advogado brasileiro qualificado.',
    claimsCount: assessed,
    contractMatches: matched,
    independentlyVerifiedCases: 0,
  }
}
