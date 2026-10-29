import unittest
from unittest.mock import patch
from config import settings
from engines.debate_engine_v3 import DebateEngineV3, WorkflowError

AGENT={"role":"Synthetic","goal":"testing","backstory":"fiction only"}

class FinancialBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_budget_rejects_second_paid_call_before_dispatch(self):
        engine=DebateEngineV3("synthetic-cost",20,1,"general")
        with patch.object(settings,"MAX_REVIEW_ESTIMATED_USD",2.5), \
             patch.object(settings,"LLM_INPUT_PRICE_USD_PER_1M",1000000.0), \
             patch.object(settings,"LLM_OUTPUT_PRICE_USD_PER_1M",1000000.0), \
             patch.object(settings,"MAX_TOKENS",1), \
             patch.object(settings,"LLM_MIN_REQUEST_INTERVAL_SECONDS",0), \
             patch("engines.debate_engine_v3._run_crew",return_value='{"ok":true}') as dispatch:
            await engine._run_agent(AGENT,"a")
            self.assertEqual(engine.execution_metrics["model_calls"],1)
            self.assertEqual(engine.execution_metrics["reserved_upper_bound_usd"],2.0)
            with self.assertRaisesRegex(WorkflowError,"ceiling"):
                await engine._run_agent(AGENT,"b")
            self.assertEqual(dispatch.call_count,1)

    async def test_missing_price_is_not_silently_treated_as_zero_cost(self):
        engine=DebateEngineV3("missing-pricing",20,1,"general")
        with patch.object(settings,"MAX_REVIEW_ESTIMATED_USD",10), \
             patch.object(settings,"LLM_INPUT_PRICE_USD_PER_1M",0), \
             patch.object(settings,"LLM_OUTPUT_PRICE_USD_PER_1M",1), \
             patch.object(settings,"LLM_MIN_REQUEST_INTERVAL_SECONDS",0), \
             patch("engines.debate_engine_v3._run_crew") as dispatch:
            with self.assertRaisesRegex(WorkflowError,"without both model price"):
                await engine._run_agent(AGENT,"a")
            dispatch.assert_not_called()

    async def test_no_price_or_cap_does_not_claim_billing_accuracy(self):
        engine=DebateEngineV3("unpriced",20,1,"general")
        self.assertIn("not billed",engine.execution_metrics["cost_measurement"])
