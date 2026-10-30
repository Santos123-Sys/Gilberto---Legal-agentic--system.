"""Pause is a bounded new-dispatch barrier, not cancellation of in-flight requests."""
import asyncio
import unittest
from unittest.mock import patch
from config import settings
from agents.cluster_definitions import CLUSTERS
from engines.debate_engine_v3 import DebateEngineV3


class DispatchBarrierTests(unittest.IsolatedAsyncioTestCase):
    async def test_paused_engine_cannot_send_new_model_request(self):
        engine = DebateEngineV3("synthetic-review", 1, 1, "contract_review")
        engine._dispatch_allowed.clear()
        with (patch.object(settings, "LLM_MIN_REQUEST_INTERVAL_SECONDS", 0),
              patch("engines.debate_engine_v3._run_crew", return_value='{"score": 1}') as dispatch):
            pending = asyncio.create_task(engine._run_agent(CLUSTERS["foundation"]["agents"][0], "synthetic", cluster_id="foundation"))
            try:
                await asyncio.sleep(0.04)
                self.assertFalse(pending.done())
                dispatch.assert_not_called()
                self.assertEqual(engine.execution_metrics["model_calls"], 0)
                engine._dispatch_allowed.set()
                self.assertEqual(await asyncio.wait_for(pending, timeout=2), '{"score": 1}')
                dispatch.assert_called_once()
                self.assertEqual(engine.execution_metrics["model_calls"], 1)
            finally:
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)

    async def test_abort_when_paused_does_not_dispatch_after_gate_released(self):
        engine = DebateEngineV3("aborted-review", 1, 1, "contract_review")
        engine._dispatch_allowed.clear()
        with patch("engines.debate_engine_v3._run_crew", return_value="should-not-be-run") as dispatch:
            pending = asyncio.create_task(engine._run_agent(CLUSTERS["foundation"]["agents"][0], "synthetic", cluster_id="foundation"))
            await asyncio.sleep(0.02)
            engine._provider_aborted = True
            engine._dispatch_allowed.set()
            with self.assertRaisesRegex(Exception, "stopped after a timeout"):
                await pending
            dispatch.assert_not_called()
