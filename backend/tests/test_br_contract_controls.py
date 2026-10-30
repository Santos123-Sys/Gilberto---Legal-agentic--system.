"""Verify synthetic BR control expectations without external model or legal sources."""
import unittest

from benchmarks.contract_controls import (
    PROBES, SYNTHETIC_CONTRACT, run_contract_controls,
)
from legal.claims import assess_agent_claims


class BrazilianSyntheticContractControlTests(unittest.TestCase):
    def test_five_probes_include_negative_control(self):
        self.assertEqual(len(PROBES), 5)
        self.assertEqual(len({probe["id"] for probe in PROBES}), len(PROBES))
        self.assertTrue(any(p["risk"].startswith("negative_control") for p in PROBES))
        self.assertIn("documento artificial", SYNTHETIC_CONTRACT)

    def test_all_control_states_match_expected_baseline(self):
        result = run_contract_controls()
        self.assertTrue(result["all_controls_passed"], result["results"])
        self.assertEqual(result["passed"], 5)
        self.assertIsNone(result["measured_model_legal_accuracy"])
        self.assertFalse(result["qualified_lawyer_ground_truth"])
        self.assertFalse(result["external_provider_invoked"])

    def test_unmatched_penalty_is_never_marked_as_present(self):
        probe = next(p for p in PROBES if p["id"] == "BR-CONTRACT-B")
        result = assess_agent_claims({"key_findings": [probe["finding"]]},
                                     SYNTHETIC_CONTRACT)
        finding = result["findings"][0]
        self.assertEqual(finding["contract_quote"]["status"], "not_found")
        self.assertEqual(finding["status"], "unsupported_or_unlocated_claim")

    def test_matching_text_cannot_certify_forum_or_signatory_authority(self):
        for identifier in ("BR-CONTRACT-C", "BR-CONTRACT-D"):
            probe = next(p for p in PROBES if p["id"] == identifier)
            result = assess_agent_claims({"key_findings": [probe["finding"]]},
                                         SYNTHETIC_CONTRACT)
            self.assertEqual(result["source_verification_status"], "NOT_VERIFIED")
            self.assertTrue(result["review_required"])
            self.assertTrue(result["findings"][0]["requires_human_review"])
            self.assertEqual(result["findings"][0]["legal_authority"]["claim_status"],
                             "unverified_authority_claim")


if __name__ == "__main__":
    unittest.main()
