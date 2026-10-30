"""Observable Brazilian legal-evidence quality checks on agent output.

This is a conservative provenance check. It does not grade correctness,
verify statutory text, validate jurisprudence or replace lawyer review.
"""
from legal.evidence import verify_contract_quote
from legal.authority import authority_claim_record


def assess_agent_claims(parsed, document_text, as_of_date=None):
    findings = parsed.get("key_findings", [])
    result = []
    for position, finding in enumerate(findings[:200]):
        if not isinstance(finding, dict):
            result.append({"index": position, "status": "malformed_finding",
                           "requires_human_review": True})
            continue
        contract = verify_contract_quote(document_text, finding.get("evidence"))
        citation = str(finding.get("legal_basis") or "").strip()
        authority = authority_claim_record(citation, as_of_date=as_of_date) if citation else None
        # A matching contract excerpt can support what the contract literally says,
        # never the correctness of its legal effect or statutory applicability.
        status = ("quoted_contract_text_present_legal_basis_unverified"
                  if contract["status"] == "present_in_supplied_document"
                  else "unsupported_or_unlocated_claim")
        result.append({
            "index": position,
            "status": status,
            "contract_quote": contract,
            "legal_authority": authority,
            "requires_human_review": True,
        })
    return {
        "jurisdiction": "BR",
        "source_verification_status": "NOT_VERIFIED",
        "review_required": True,
        "material_findings_count": len(findings),
        "assessed_findings_count": len(result),
        "findings": result,
        "method": "Correspondência determinística com o texto fornecido; sem verificação em tempo real da legislação ou da jurisprudência",
    }
