"""Synthetic, nonconfidential Brazilian commercial-contract control checks.

IMPORTANT: These are deterministic implementation tests, NOT model evaluation,
lawyer adjudication, judicial verification, or estimates of legal accuracy.
"""
from legal.claims import assess_agent_claims

SYNTHETIC_CONTRACT = (
    "CONTRATO DE PRESTAÇÃO DE SERVIÇOS FICTÍCIO. "
    "Cláusula 1. CONTRATANTE: Empresa Alfa Ltda. "
    "Cláusula 2. A multa por atraso é de 2% sobre a parcela vencida. "
    "Cláusula 3. Assina por Alfa o Sr. Exemplo, Diretor. "
    "Cláusula 4. As partes elegem o foro da Comarca de São Paulo/SP. "
    "Anexos societários e procurações não foram fornecidos. "
    "Este é um documento artificial sem pessoas, clientes ou processos reais."
)

PROBES = (
    {
        "id": "BR-CONTRACT-A",
        "risk": "invented_stj_precedent",
        "finding": {
            "item": "Synthetic case citation",
            "evidence": "Cláusula 2. A multa por atraso é de 2% sobre a parcela vencida.",
            "legal_basis": "REsp 9.999.999/DF, precedente fictício não verificado",
        },
        "expected_quote": "present_in_supplied_document",
        "authority_unverified": True,
    },
    {
        "id": "BR-CONTRACT-B",
        "risk": "incorrect_penalty_20_vs_2_percent",
        "finding": {
            "item": "Invented contractual fine",
            "evidence": "Cláusula 2. A multa por atraso é de 20% sobre a parcela vencida.",
            "legal_basis": "",
        },
        "expected_quote": "not_found",
        "authority_unverified": False,
    },
    {
        "id": "BR-CONTRACT-C",
        "risk": "unproven_signatory_authority",
        "finding": {
            "item": "Signatory is allegedly authorized",
            "evidence": "Cláusula 3. Assina por Alfa o Sr. Exemplo, Diretor.",
            "legal_basis": "Poderes representativos não demonstrados",
        },
        "expected_quote": "present_in_supplied_document",
        "authority_unverified": True,
    },
    {
        "id": "BR-CONTRACT-D",
        "risk": "forum_enforceability_not_established_by_clause",
        "finding": {
            "item": "Forum selection supposedly enforceable",
            "evidence": "Cláusula 4. As partes elegem o foro da Comarca de São Paulo/SP.",
            "legal_basis": "Art. 63 do CPC, aplicabilidade não verificada",
        },
        "expected_quote": "present_in_supplied_document",
        "authority_unverified": True,
    },
    {
        "id": "BR-CONTRACT-E",
        "risk": "negative_control_literal_penalty_extraction",
        "finding": {
            "item": "Literal penalty extraction only",
            "evidence": "Cláusula 2. A multa por atraso é de 2% sobre a parcela vencida.",
            "legal_basis": "",
        },
        "expected_quote": "present_in_supplied_document",
        "authority_unverified": False,
    },
)


def run_contract_controls():
    """Evaluate hard-coded expected controls, preserving legal-review uncertainty."""
    outcomes = []
    for probe in PROBES:
        audit = assess_agent_claims({"key_findings": [probe["finding"]]},
                                    SYNTHETIC_CONTRACT, as_of_date="2026-10-30")
        finding = audit["findings"][0]
        observed_quote = finding["contract_quote"]["status"]
        observed_authority = finding["legal_authority"]
        authority_unverified = bool(
            observed_authority and
            observed_authority["claim_status"] == "unverified_authority_claim"
        )
        passed = (observed_quote == probe["expected_quote"] and
                  authority_unverified == probe["authority_unverified"] and
                  finding["requires_human_review"] is True and
                  audit["source_verification_status"] == "NOT_VERIFIED")
        outcomes.append({
            "id": probe["id"], "risk": probe["risk"],
            "expected_quote": probe["expected_quote"],
            "observed_quote": observed_quote,
            "authority_unverified": authority_unverified,
            "human_review_required": finding["requires_human_review"],
            "passed": passed,
        })
    return {
        "jurisdiction": "BR",
        "kind": "deterministic_synthetic_control_check",
        "probes": len(outcomes),
        "passed": sum(x["passed"] for x in outcomes),
        "all_controls_passed": all(x["passed"] for x in outcomes),
        "results": outcomes,
        "measured_model_legal_accuracy": None,
        "independently_reviewed_jurisprudence": False,
        "qualified_lawyer_ground_truth": False,
        "external_provider_invoked": False,
        "limitations": (
            "Checks quotation presence and unverified authority flags only. "
            "No model dry run, precedent existence search, authority applicability "
            "or independent Brazilian-law expert scoring."
        ),
    }
