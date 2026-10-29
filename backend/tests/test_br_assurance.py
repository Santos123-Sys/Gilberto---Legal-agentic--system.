import unittest
from legal.assurance import assess_claims

class BrazilianAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.document=("CONTRATO FICTÍCIO. A cláusula 9 estabelece multa de 2%. "
                       "É vedado divulgar dados confidenciais.")
    def test_quote_and_unverified_legal_citation_distinct(self):
        report=assess_claims(self.document,[{"item":"Fee","agent":"foundation","round":1,
            "evidence_kind":"contract_quote","evidence":"multa de 2%",
            "legal_basis":"CC 421 fictional quotation"}])
        self.assertEqual(report["document_passages_located"],1)
        self.assertEqual(report["authority_claims_unverified"],1)
        self.assertEqual(report["source_checks"][0]["legal_authority"]["claim_status"],
                         "unverified_authority_claim")
        self.assertFalse(report["legal_conclusions_verified"])
    def test_absent_quote_not_passed(self):
        report=assess_claims(self.document,[{"item":"invented","evidence_kind":"contract_quote",
                                           "evidence":"multa de 20%"}])
        self.assertEqual(report["document_passages_not_found"],1)
        self.assertEqual(report["status"],"requires_qualified_brazilian_legal_review")
    def test_legacy_findings_not_automatically_verified(self):
        report=assess_claims(self.document,[{"item":"Law 1111","legal_basis":"Art 123"}])
        self.assertEqual(report["document_passages_located"],0)
        self.assertEqual(report["authority_claims_unverified"],1)
    def test_bounded_claims(self):
        report=assess_claims(self.document,[{"item":str(i)} for i in range(205)])
        self.assertEqual((report["claims_examined"],report["unreviewed_claims"]),(200,5))
    def test_model_confidence_never_certifies_law(self):
        report=assess_claims(self.document,[{"item":"invented precedent",
                    "confidence":"high","legal_basis":"STJ REsp X"}])
        self.assertFalse(report["legal_conclusions_verified"])
