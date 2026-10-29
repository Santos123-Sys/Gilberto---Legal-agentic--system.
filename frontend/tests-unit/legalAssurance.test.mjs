import { test } from 'node:test'
import assert from 'node:assert/strict'
import { legalAssuranceView } from '../src/auth/legalAssurance.js'

test('legacy result without assurance never appears legally verified', () => {
  const result=legalAssuranceView({confidence:5,final_classification:'Aceitável'})
  assert.equal(result.status,'LEGAL_REVIEW_REQUIRED')
  assert.equal(result.independentlyVerifiedCases,0)
  assert.equal(result.claimsCount,null)
})

test('matching contract passages cannot promote legal research to verified', () => {
  const result=legalAssuranceView({legal_assurance:{
    scope:'BRAZILIAN_LAW_ONLY',material_claims_assessed:5,contract_quotes_matched:5,
    authority_holdings_verified:500,release_status:'VERIFIED',
  }})
  assert.equal(result.status,'LEGAL_REVIEW_REQUIRED')
  assert.equal(result.claimsCount,5)
  assert.equal(result.contractMatches,5)
  assert.equal(result.independentlyVerifiedCases,0)
})

test('Brazilian law wording is selected only when scope is known', () => {
  assert.match(legalAssuranceView({legal_assurance:{scope:'BRAZILIAN_LAW_ONLY'}}).text,/brasileira/)
  assert.match(legalAssuranceView({}).text,/sem validação/)
})
