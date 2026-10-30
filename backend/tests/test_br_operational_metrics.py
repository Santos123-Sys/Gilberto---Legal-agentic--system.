import unittest
from operational.metrics import summarize_sessions

class OperationalObservabilityTests(unittest.TestCase):
    def test_aggregates_only_safe_counts_without_documents_or_subjects(self):
        records=[
            {"id":"secret-user-A","document_text":"CONFIDENTIAL INSTRUMENT",
             "status":"completed","execution_metrics":{"total_latency_ms":100,"model_calls":5}},
            {"id":"secret-user-B","document_name":"sensitive.pdf",
             "status":"error","error":"raw private error",
             "execution_metrics":{"total_latency_ms":500,"model_calls":2}},
            {"status":"cancelled","execution_metrics":{"model_calls":1}},
        ]
        result=summarize_sessions(records)
        self.assertEqual(result["sample_size"],3)
        self.assertEqual(result["states"]["error"],1)
        self.assertEqual(result["model_calls_reported"],8)
        self.assertEqual(result["p50_latency_ms"],100)
        self.assertEqual(result["p95_latency_ms"],500)
        self.assertFalse(result["history_complete"])
        self.assertFalse(result["availability_measured"])
        self.assertNotIn("CONFIDENTIAL",str(result))
        self.assertNotIn("secret-user-A",str(result))
        self.assertNotIn("sensitive.pdf",str(result))
    def test_empty_metrics_do_not_invent_availability(self):
        result=summarize_sessions([])
        self.assertEqual(result["sample_size"],0)
        self.assertIsNone(result["p95_latency_ms"])
        self.assertFalse(result["availability_measured"])
