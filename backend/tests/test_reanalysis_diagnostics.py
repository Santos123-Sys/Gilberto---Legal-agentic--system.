"""Synthetic tests for production re-analysis failure reporting; no paid requests."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from engines.debate_engine_v3 import (
    DebateEngineV3, WorkflowError, safe_workstream_failure,
)
from provider import ProviderError


class FailureClassificationTests(unittest.TestCase):
    def test_provider_codes_and_status_are_allowlisted(self):
        data = safe_workstream_failure(ProviderError(
            "rate_limit", "CONFIDENTIAL provider output and legal document", http_status=429
        ))
        self.assertEqual(data, {"category": "provider", "code": "rate_limit", "http_status": 429})
        self.assertNotIn("CONFIDENTIAL", str(data))
        self.assertEqual(safe_workstream_failure(ProviderError(
            "unknown_sensitive_code", "private", http_status=999
        )), {"category": "provider", "code": "provider_error", "http_status": None})

    def test_invalid_output_and_unexpected_exception_never_expose_body(self):
        self.assertEqual(safe_workstream_failure(ValueError("CLIENT DOCUMENT"))["code"],
                         "invalid_model_output")
        self.assertEqual(safe_workstream_failure(RuntimeError("SECRET TOKEN"))["code"],
                         "unexpected_failure")
        self.assertEqual(safe_workstream_failure(WorkflowError("PRIVATE", code="model_call_budget"))["code"],
                         "model_call_budget")

    def test_security_and_cost_denials_are_not_reported_as_interruptions(self):
        cases = {
            "policy_denied": "policy_denied",
            "cost_ceiling": "cost_ceiling",
            "cost_configuration": "cost_configuration",
        }
        for message, code in cases.items():
            with self.subTest(code=code):
                data = safe_workstream_failure(WorkflowError("texto livre CONFIDENCIAL", code=message))
                self.assertNotIn("CONFIDENCIAL", str(data))
                self.assertEqual(data, {"category": "policy", "code": code})
        self.assertEqual(safe_workstream_failure(WorkflowError("outra coisa"))["code"],
                         "workflow_interrupted")

    def test_unknown_or_injected_codes_never_reach_the_client(self):
        for code in ("<script>alert(1)</script>", "Cliente: João Silva", "", None, 42):
            with self.subTest(code=code):
                self.assertEqual(safe_workstream_failure(WorkflowError("x", code=code)),
                                 {"category": "execution", "code": "workflow_interrupted"})


class PolicyDenialCouplingTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_policy_denial_is_classified_as_policy_denied(self):
        # Couples the classifier to the exception the real capability policy
        # raises, so a reworded policy message cannot silently fall back to
        # the generic "workflow_interrupted" code.
        engine = DebateEngineV3("synthetic-policy", 1, 1, "contract_review")
        engine.current_round = 1
        with patch("engines.debate_engine_v3._run_crew") as provider:
            with self.assertRaises(WorkflowError) as raised:
                await engine._run_agent({"role": "unrostered", "goal": "unknown"},
                                        "synthetic", cluster_id="foundation")
            provider.assert_not_called()
        self.assertEqual(safe_workstream_failure(raised.exception),
                         {"category": "policy", "code": "policy_denied"})

    async def test_real_backup_consent_denial_is_classified_as_policy_denied(self):
        from agents.cluster_definitions import CLUSTERS
        engine = DebateEngineV3("synthetic-backup", 1, 1, "contract_review",
                                provider_mode="backup")
        engine.current_round = 1
        with patch("engines.debate_engine_v3._run_crew") as provider:
            with self.assertRaises(WorkflowError) as raised:
                await engine._run_agent(CLUSTERS["foundation"]["agents"][0],
                                        "synthetic", cluster_id="foundation")
            provider.assert_not_called()
        self.assertEqual(safe_workstream_failure(raised.exception)["code"], "policy_denied")


class ReanalysisFailureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = DebateEngineV3("fictional-case", 20, 2, "contract_review")
        self.engine.current_round = 1
        self.previous_foundation = {"parsed": {"summary": "Prior complete finding"}}
        self.previous_strategy = {"parsed": {"summary": "Prior complete strategy"}}
        self.engine.cluster_summaries = {
            "foundation": self.previous_foundation,
            "strategy": self.previous_strategy,
        }

    async def _run_failed(self, failure_f, failure_s):
        async def reanalyze(cid, _cluster, _document, _round):
            if cid == "foundation":
                if failure_f is not None:
                    raise failure_f
                return {"parsed": {"summary": "Uncommitted partial foundation"}}
            if failure_s is not None:
                raise failure_s
            return {"parsed": {"summary": "Uncommitted partial strategy"}}

        with patch.object(self.engine, "_run_agent", AsyncMock(
                return_value='{"target_cluster":"foundation","rationale":"review"}')), \
             patch.object(self.engine, "_run_single_cluster", side_effect=reanalyze) as execute, \
             patch.object(self.engine, "_run_devils_advocate", new_callable=AsyncMock) as da, \
             patch.object(self.engine, "_run_master_manager", new_callable=AsyncMock) as master:
            with self.assertRaisesRegex(WorkflowError, "Reanálise incompleta") as raised:
                await self.engine._execute_process_feedback("Recheck clause", "FICTIONAL CONTRACT")
            self.assertEqual(execute.call_count, 2)
            da.assert_not_awaited()
            master.assert_not_awaited()
            return str(raised.exception)

    async def test_two_failed_clusters_expose_safe_codes_no_raw_payload(self):
        msg = await self._run_failed(
            ProviderError("rate_limit", "PRIVATE key and document", http_status=429),
            ValueError("Secret extracted Brazilian contract content")
        )
        self.assertIn("foundation (rate_limit)", msg)
        self.assertIn("strategy (invalid_model_output)", msg)
        self.assertNotIn("PRIVATE", msg)
        self.assertNotIn("Secret extracted", msg)
        self.assertIs(self.engine.cluster_summaries["foundation"], self.previous_foundation)
        self.assertIs(self.engine.cluster_summaries["strategy"], self.previous_strategy)
        self.assertEqual(self.engine.execution_metrics["reanalysis_failures"][0]["http_status"], 429)
        events = []
        while not self.engine._event_queue.empty():
            events.append(self.engine._event_queue.get_nowait())
        failures = [e for e in events if e["type"] == "CLUSTER_FAILED"]
        self.assertEqual(len(failures), 2)
        self.assertEqual({e["cluster"] for e in failures}, {"foundation", "strategy"})
        self.assertFalse(any(e["type"] in ("ROUND_COMPLETE", "DEBATE_COMPLETE") for e in events))
        self.assertNotIn("PRIVATE", str(failures))

    async def test_successful_cluster_not_promoted_when_other_fails(self):
        msg = await self._run_failed(None, WorkflowError("SEGREDO DO CLIENTE", code="model_call_budget"))
        self.assertIn("strategy (model_call_budget)", msg)
        self.assertNotIn("SEGREDO DO CLIENTE", msg)
        self.assertIs(self.engine.cluster_summaries["foundation"], self.previous_foundation)
        self.assertIs(self.engine.cluster_summaries["strategy"], self.previous_strategy)

    async def test_policy_denial_during_reanalysis_is_visible_and_not_merged(self):
        msg = await self._run_failed(
            WorkflowError("Bloqueado", code="policy_denied"),
            None,
        )
        self.assertIn("foundation (policy_denied)", msg)
        self.assertIs(self.engine.cluster_summaries["foundation"], self.previous_foundation)
        self.assertIs(self.engine.cluster_summaries["strategy"], self.previous_strategy)
        failure = self.engine.execution_metrics["reanalysis_failures"][0]
        self.assertEqual((failure["category"], failure["code"]), ("policy", "policy_denied"))

    async def test_no_implicit_retry_after_provider_fault(self):
        await self._run_failed(ProviderError("provider_unavailable", "PRIVATE", 503),
                               ProviderError("provider_unavailable", "PRIVATE", 503))
        self.assertEqual(self.engine.execution_metrics["model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
