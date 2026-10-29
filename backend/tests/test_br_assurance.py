import unittest
from legal.assurance import synthesis_assurance

class BrazilianSynthesisAssuranceTests(unittest.TestCase):
    def test_empty_evidence_never_means_legally_verified(self):
        result=synthesis_assurance([])
        self.assertEqual(result["release_status"],"DRAFT_REQUIRES_QUALIFIED_BRAZILIAN_LEGAL_REVIEW")
        self.assertTrue(result["professional_legal_review_required"])
        self.assertEqual(result["authority_holdings_verified"],0)
        self.assertIsNone(result["reasoning_rubric_expert_score"])

    def test_matched_document_quote_does_not_certify_authority(self):
        result=synthesis_assurance([{"findings":[
            {"status":"quoted_contract_text_present_legal_basis_unverified"},
            {"status":"unsupported_or_unlocated_claim"}]}])
        self.assertEqual(result["material_claims_assessed"],2)
        self.assertEqual(result["contract_quotes_matched"],1)
        self.assertEqual(result["claims_without_matching_document_quote"],1)
        self.assertTrue(result["professional_legal_review_required"])
