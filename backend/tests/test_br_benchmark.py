import json
from pathlib import Path
import tempfile
import unittest
from benchmarks.validate import validate_corpus

class BRBenchmarkGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.path=Path(__file__).resolve().parents[1]/"benchmarks"/"cases.json"
    def test_synthetic_control_corpus_never_passes_as_legal_accuracy(self):
        result=validate_corpus(self.path)
        self.assertGreaterEqual(result["synthetic_cases"],10)
        self.assertIsNone(result["expert_verified_legal_accuracy"])
        self.assertIsNone(result["baseline_vs_new_legal_accuracy_ratio"])
    def test_cannot_fake_human_review_status_or_gold_answer(self):
        data=json.loads(self.path.read_text(encoding="utf-8"))
        data["cases"][0]["lawyer_review_status"]="approved"
        data["cases"][0]["gold_legal_answer"]="fabricated"
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.json"
            p.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_corpus(p)
    def test_cannot_remove_adversarial_category(self):
        data=json.loads(self.path.read_text(encoding="utf-8"))
        data["cases"]=[c for c in data["cases"] if c["category"]!="prompt_injection"]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"bad.json"
            p.write_text(json.dumps(data),encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_corpus(p)
