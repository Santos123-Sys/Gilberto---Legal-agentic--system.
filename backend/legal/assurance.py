"""Final Brazilian legal synthesis release-assurance metadata (not a truth score)."""
def synthesis_assurance(agent_reports):
    reports=list(agent_reports)
    claims=[item for report in reports for item in report.get("findings",[])]
    matched=sum(item.get("status")=="quoted_contract_text_present_legal_basis_unverified" for item in claims)
    return {
        "scope":"BRAZILIAN_LAW_ONLY",
        "source_verification_status":"NOT_INDEPENDENTLY_VERIFIED",
        "professional_legal_review_required":True,
        "release_status":"DRAFT_REQUIRES_QUALIFIED_BRAZILIAN_LEGAL_REVIEW",
        "specialist_reports_received":len(reports),
        "material_claims_assessed":len(claims),
        "contract_quotes_matched":matched,
        "claims_without_matching_document_quote":len(claims)-matched,
        "authority_holdings_verified":0,
        "reasoning_rubric_expert_score":None,
        "warnings":[
            "Contract-quote presence does not establish interpretation or factual truth.",
            "Statutory text, case holdings, temporal validity and jurisdictional relevance not independently verified.",
            "Model self-confidence and multi-agent agreement are not empirical legal accuracy.",
            "Qualified Brazilian lawyer must review material conclusions before reliance.",
        ],
    }
