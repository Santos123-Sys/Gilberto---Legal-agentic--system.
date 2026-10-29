import unittest
from legal.claims import assess_agent_claims


class AgentClaimAuditTests(unittest.TestCase):
    def test_paired_contract_evidence_does_not_certify_legal_basis(self):
        document = "CONTRATO FICTÍCIO. Cláusula 2. Multa será de 2%."
        parsed = {"key_findings":[
            {"item":"Multa","evidence":"Cláusula 2. Multa será de 2%.",
             "legal_basis":"Art. 421 do Código Civil (citação não autenticada)"}]}
        result = assess_agent_claims(parsed, document, "2026-10-29")
        self.assertEqual(result["jurisdiction"],"BR")
        self.assertEqual(result["source_verification_status"],"NOT_VERIFIED")
        self.assertEqual(result["findings"][0]["status"],
                         "quoted_contract_text_present_legal_basis_unverified")
        self.assertEqual(result["findings"][0]["legal_authority"]["claim_status"],
                         "unverified_authority_claim")
        self.assertTrue(result["review_required"])

    def test_fabricated_quote_cannot_pass_as_document_source(self):
        parsed={"key_findings":[{"item":"Fictitious","evidence":"A multa é de 200%",
                                 "legal_basis":"Lei falsa n. 99.999"}]}
        report=assess_agent_claims(parsed,"CONTRATO FICTÍCIO. Multa de 2%.")
        self.assertEqual(report["findings"][0]["status"],"unsupported_or_unlocated_claim")

    def test_uncited_or_empty_finding_is_human_review(self):
        report=assess_agent_claims({"key_findings":[{"item":"No source"}]},"CONTRATO FICTÍCIO")
        self.assertTrue(report["findings"][0]["requires_human_review"])
        self.assertEqual(report["findings"][0]["contract_quote"]["status"],"missing_quote")

    def test_empty_findings_are_not_falsely_certified(self):
        report=assess_agent_claims({"key_findings":[]},"No findings")
        self.assertTrue(report["review_required"])
        self.assertEqual(report["source_verification_status"],"NOT_VERIFIED")
