import unittest
from financial.planning import estimate_plan

class FinancialPreviewTests(unittest.TestCase):
    def test_cost_preview_labels_unknown_document_component(self):
        data=estimate_plan(12,4096,output_usd_per_million=4,input_usd_per_million=2,hard_cap_usd=1.5)
        self.assertEqual(data["planned_model_calls"],12)
        self.assertEqual(data["maximum_possible_output_tokens"],49152)
        self.assertEqual(data["maximum_output_component_usd"],0.196608)
        self.assertFalse(data["complete_cost_quote_available"])
        self.assertFalse(data["input_document_tokens_known"])

    def test_unconfigured_price_is_none_not_a_free_zero_charge(self):
        data=estimate_plan(47,4096)
        self.assertIsNone(data["maximum_output_component_usd"])
        self.assertFalse(data["priced_inputs_known"])

    def test_negative_or_noninteger_cost_inputs_rejected(self):
        for n in (-1,2.5,True):
            with self.assertRaises(ValueError):
                estimate_plan(n,4096)
