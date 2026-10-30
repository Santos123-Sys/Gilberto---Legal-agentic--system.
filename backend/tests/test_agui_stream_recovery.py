"""Fixture-only auth, replay and final-acceptance verification of AG-UI SSE."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
import main
from config import settings
from security.oidc import Principal


class ProtectedAguiReleaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        environment = patch.dict(os.environ, SESSION_DB_PATH=temp.name + "/checkpoints.sqlite3")
        environment.start()
        self.addCleanup(environment.stop)
        mode = patch.object(settings, "AUTH_MODE", "oidc")
        mode.start()
        self.addCleanup(mode.stop)
        main.sessions.clear()
        main.app.dependency_overrides[main.current_principal] = lambda: Principal(issuer="fixture", subject="lawyer-1")
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)
        response = await self.client.post("/api/sessions", json={"num_rounds": 1})
        self.assertEqual(response.status_code, 200, response.text)
        self.sid = response.json()["session_id"]
        self.session = main.sessions[self.sid]

    async def test_human_acceptance_is_only_native_success_and_idempotent(self):
        path = "/api/sessions/" + self.sid
        capabilities = await self.client.get(path + "/ag-ui/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertFalse(capabilities.json()["supports_run_agent_post"])
        self.assertTrue(capabilities.json()["journal_cursor_authoritative"])

        self.session["status"] = "awaiting_feedback"
        self.session["engine"].master_summaries = [{"parsed": {"final_score": 5, "final_classification": "Relevante"}}]
        first = await self.client.post(path + "/accept")
        second = await self.client.post(path + "/accept")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual([e["type"] for e in self.session["events"]].count("FINAL_ACCEPTED"), 1)

        data = await self.client.get(path + "/stream?protocol=ag-ui")
        self.assertEqual(data.status_code, 200)
        rows = [json.loads(row[6:]) for row in data.text.splitlines() if row.startswith("data: ")]
        self.assertEqual(rows[0]["type"], "STATE_SNAPSHOT")
        self.assertEqual([r["type"] for r in rows].count("RUN_FINISHED"), 1)
        self.assertIn("id: 1", data.text)
        data_replay = await self.client.get(path + "/stream?protocol=ag-ui&cursor=1")
        self.assertNotIn("id: 1", data_replay.text)
        self.assertEqual((await self.client.get(path + "/stream?protocol=ag-ui&cursor=200")).status_code, 409)
        main.app.dependency_overrides[main.current_principal] = lambda: Principal(issuer="fixture", subject="other-lawyer")
        self.assertEqual((await self.client.get(path + "/ag-ui/capabilities")).status_code, 404)
        self.assertEqual((await self.client.get(path + "/stream?protocol=ag-ui")).status_code, 404)
