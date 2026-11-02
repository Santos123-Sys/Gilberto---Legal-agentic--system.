import unittest
from legal.authority import classify_official_location, authority_claim_record

class BrazilianAuthorityProvenanceTests(unittest.TestCase):
    def test_known_official_domains_are_locations_not_authentication(self):
        samples = [
            "https://www.planalto.gov.br/ccivil_03/leis/2002/l10406compilada.htm",
            "https://scon.stj.jus.br/SCON/",
            "https://portal.stf.jus.br/jurisprudencia/",
            "https://conteudo.cvm.gov.br/legislacao/resolucoes.html",
            "https://www.gov.br/cade/pt-br/assuntos/servicos-digitais/busca-de-jurisprudencia",
        ]
        for address in samples:
            with self.subTest(address=address):
                checked=classify_official_location(address)
                self.assertEqual(checked["status"],"official_source_location_not_retrieved")
                self.assertFalse(checked["authority_verified"])

    def test_spoofed_domains_are_not_official(self):
        samples=[
            "http://www.planalto.gov.br/ccivil_03",
            "https://planalto.gov.br.evil.test/citation",
            "https://evil.test/?site=https://planalto.gov.br",
            "https://user:secret@www.planalto.gov.br/path",
            "https://www.gov.br.evil.com/cvm/",
            "https://www.gov.br/other/private",
            "javascript:alert(1)",
            "https://subdomain.planalto.gov.br/path",
            "https://scon.stj.jus.br:444/SCON/",
        ]
        for address in samples:
            with self.subTest(address=address):
                self.assertEqual(classify_official_location(address)["status"],
                                 "untrusted_location")
    def test_reference_with_known_official_url_stays_unverified(self):
        record=authority_claim_record("STJ fictional REsp 1234567",
                  "https://scon.stj.jus.br/SCON/",as_of_date="2026-10-29")
        self.assertTrue(record["must_retrieve_official_document"])
        self.assertEqual(record["claim_status"],"unverified_authority_claim")
        self.assertFalse(record["source_location"]["authority_verified"])
