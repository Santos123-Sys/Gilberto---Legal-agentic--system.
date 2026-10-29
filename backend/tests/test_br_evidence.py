import unittest
from legal.evidence import document_digest, verify_contract_quote, assess_quoted_evidence


class ContractEvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.document = ("CONTRATO FICTÍCIO\nCláusula 7. A multa por atraso será de "
                         "2% sobre o valor da parcela.\nCláusula 8. A contratada não "
                         "poderá divulgar informações confidenciais.")

    def test_exact_quote_and_whitespace_are_anchored_to_document(self):
        quote="Cláusula 7. A multa por atraso será de 2% sobre o valor da parcela."
        result=verify_contract_quote(self.document, quote.replace(" multa ","  multa\n"))
        self.assertEqual(result["status"],"present_in_supplied_document")
        self.assertEqual(result["document_sha256"],document_digest(self.document))
        self.assertEqual(len(result["quote_sha256"]),64)

    def test_critical_negation_and_amount_mismatch_fail(self):
        for quote in ("A contratada poderá divulgar informações confidenciais.",
                      "A multa por atraso será de 20% sobre o valor da parcela.",
                      "Cláusula 9. A multa por atraso será de 2%",
                      "O juízo federal condenou as partes."):
            with self.subTest(quote=quote):
                self.assertEqual(verify_contract_quote(self.document, quote)["status"],
                                 "not_found")

    def test_citation_or_model_assertion_is_never_treated_as_document_evidence(self):
        result=assess_quoted_evidence(self.document, [
            {"kind":"law","quote":"Lei 10.406/2002 art. 421"},
            {"kind":"contract_quote","quote":"A multa por atraso será de 2% sobre o valor da parcela."},
            {"kind":"contract_quote","quote":"FAKE contract provision"}])
        self.assertEqual([x["status"] for x in result],
                         ["not_contract_quote","present_in_supplied_document","not_found"])

    def test_empty_and_unreasonably_long_quote_does_not_pass(self):
        self.assertEqual(verify_contract_quote(self.document,"")["status"],"missing_quote")
        self.assertEqual(verify_contract_quote(self.document,"x"*4001)["status"],"quote_too_long")

    def test_quote_presence_does_not_assert_ocr_legal_validity(self):
        result=verify_contract_quote(self.document,"Cláusula 8.")
        self.assertEqual(result["status"],"present_in_supplied_document")
        self.assertIn("not legal authority",result["limitations"])
