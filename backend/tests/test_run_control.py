"""Synthetic execution controls: no paid provider calls or legal assertions."""
import asyncio
import copy
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import httpx
import main
import run_control
import session_store
from config import settings
from engines.debate_engine_v3 import DebateEngineV3
from security.oidc import Principal


class RunControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, SESSION_DB_PATH=self.temp.name + "/sessions.db")
        env.start()
        self.addCleanup(env.stop)
        auth_mode = patch.object(settings, "AUTH_MODE", "oidc")
        auth_mode.start()
        self.addCleanup(auth_mode.stop)
        main.sessions.clear()
        main.app.dependency_overrides[main.current_principal] = lambda: Principal(
            issuer="https://test.invalid", subject="owner")
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)
        created = await self.client.post("/api/sessions", json={"num_rounds": 1})
        self.sid = created.json()["session_id"]
        self.session = main.sessions[self.sid]
        self.engine = self.session["engine"]
        self.url = f"/api/sessions/{self.sid}"

    async def test_pause_acknowledgement_waits_for_inflight_boundary(self):
        self.session["status"] = "running"
        self.engine._active_provider_calls = 1
        paused = await self.client.post(self.url + "/pause")
        self.assertEqual(paused.json()["execution_state"], "PAUSE_REQUESTED")
        self.assertTrue(paused.json()["provider_in_flight_possible"])
        self.assertFalse(self.engine._dispatch_allowed.is_set())
        self.engine._active_provider_calls = 0
        main._acknowledge_pause(self.session)
        state = (await self.client.get(self.url + "/status")).json()
        self.assertEqual(state["execution_state"], "PAUSED")
        self.assertTrue(state["resume_supported"])
        self.assertEqual(sum(e["type"] == "RUN_PAUSED" for e in self.session["events"]), 1)
        main._acknowledge_pause(self.session)
        self.assertEqual(sum(e["type"] == "RUN_PAUSED" for e in self.session["events"]), 1)
        restored = session_store.load(self.sid, DebateEngineV3)
        self.assertEqual(restored["execution_state"], "INTERRUPTED")
        self.assertFalse(run_control.response(restored)["resume_supported"])
        self.assertIsNotNone(restored["last_checkpoint_at"])

    async def test_resume_before_inflight_completion_reports_truthful_uncertainty(self):
        self.session["status"] = "running"
        self.engine._active_provider_calls = 1
        await self.client.post(self.url + "/pause")
        resumed = await self.client.post(self.url + "/resume")
        self.assertEqual(resumed.json()["execution_state"], "RUNNING")
        self.assertTrue(resumed.json()["provider_in_flight_possible"])
        self.assertTrue(self.engine._dispatch_allowed.is_set())
        self.assertIn("RESUMING", [e["execution_state"] for e in self.session["events"]])

    async def test_stale_concurrent_commands_and_idempotent_stop(self):
        self.session["status"] = "running"
        state = (await self.client.get(self.url + "/status")).json()
        version = state["control_version"]
        responses = await asyncio.gather(*[
            self.client.post(self.url + f"/pause?expected_version={version}") for _ in range(2)])
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409])
        stale_resume = await self.client.post(self.url + f"/resume?expected_version={version}")
        self.assertEqual(stale_resume.status_code, 409)
        stopped = await self.client.post(self.url + "/cancel")
        self.assertEqual(stopped.json()["execution_state"], "STOPPED")
        repeat = await self.client.post(self.url + f"/cancel?expected_version={version}")
        self.assertEqual(repeat.status_code, 200)
        states = [e["execution_state"] for e in self.session["events"]]
        self.assertEqual(states[-3:], ["STOP_REQUESTED", "STOPPING", "STOPPED"])
        self.assertEqual((await self.client.post(self.url + "/resume")).status_code, 409)
        self.assertTrue((await self.client.get(self.url + "/results")).json()["partial"])

    async def test_human_gate_is_not_a_manual_pause(self):
        self.session.update(status="awaiting_gate", run_control="pause_requested", pause_acknowledged=True)
        state = (await self.client.get(self.url + "/status")).json()
        self.assertEqual(state["execution_state"], "AWAITING_HUMAN_REVIEW")
        self.assertFalse(state["resume_supported"])
        self.assertEqual((await self.client.post(self.url + "/resume")).status_code, 409)

    async def test_cross_user_cannot_pause_resume_or_stop(self):
        self.session["status"] = "running"
        main.app.dependency_overrides[main.current_principal] = lambda: Principal(
            issuer="https://test.invalid", subject="other-user")
        for command in ("pause", "resume", "cancel"):
            self.assertEqual((await self.client.post(self.url + "/" + command)).status_code, 404)
        self.assertEqual(self.session["run_control"], "running")
        self.assertTrue(self.engine._dispatch_allowed.is_set())

    async def test_stop_drains_coroutines_and_rejects_late_thread_result(self):
        started = threading.Event()
        release = threading.Event()
        child_finished = asyncio.Event()

        def provider(*_):
            started.set()
            release.wait(timeout=3)
            return "late synthetic output"

        async def execute(_):
            try:
                await self.engine._run_agent(main.CLUSTERS["foundation"]["agents"][0], "synthetic", cluster_id="foundation")
                self.engine.master_summaries.append({"parsed": {"late": True}})
            finally:
                await asyncio.sleep(0.01)
                child_finished.set()

        self.session["status"] = "running"
        with patch.object(self.engine, "_execute_debate", side_effect=execute), patch(
                "engines.debate_engine_v3._run_crew", side_effect=provider):
            task = asyncio.create_task(main._run_analysis_bg(self.sid, "synthetic"))
            self.session["task"] = task
            try:
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                await self.client.post(self.url + "/cancel")
                await asyncio.gather(task, return_exceptions=True)
                self.assertTrue(child_finished.is_set())
                self.assertEqual(self.session["execution_state"], "STOPPED")
                checkpoint = copy.deepcopy(self.engine.get_metrics())
                release.set()
                await asyncio.sleep(0.03)
                self.assertEqual(self.engine.get_metrics(), checkpoint)
                self.assertEqual(self.engine.master_summaries, [])
                self.assertEqual(self.engine._active_provider_calls, 0)
                self.assertEqual(sum(e["type"] == "CANCELLED" for e in self.session["events"]), 1)
            finally:
                release.set()
                if not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
