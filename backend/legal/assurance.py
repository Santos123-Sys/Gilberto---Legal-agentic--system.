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
            "A presença da transcrição contratual não estabelece a interpretação nem a veracidade dos fatos.",
            "Texto legal, teses dos julgados, vigência temporal e pertinência jurisdicional não foram verificados de forma independente.",
            "A autoconfiança do modelo e a concordância entre agentes não constituem precisão jurídica empírica.",
            "Um advogado brasileiro habilitado deve revisar as conclusões relevantes antes de qualquer uso.",
        ],
    }
