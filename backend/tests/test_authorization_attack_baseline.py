"""P0 attack contract. Each expected failure is a confirmed unimplemented control.

Do not count these cases as passed authorization tests. After enforcement, remove
expectedFailure and turn the tests into mandatory green release gates.
"""
import unittest
import httpx

import main


class BrokenAccessControlBaseline(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main.sessions.clear()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        )
        r = await self.client.post("/api/sessions", json={"num_rounds": 1})
        self.assertEqual(r.status_code, 200)
        self.sid = r.json()["session_id"]

    async def asyncTearDown(self):
        await self.client.aclose()

    @unittest.expectedFailure
    async def test_anonymous_creation_must_be_denied(self):
        r = await self.client.post("/api/sessions", json={"num_rounds": 1})
        self.assertEqual(r.status_code, 401)

    @unittest.expectedFailure
    async def test_anonymous_document_and_result_read_must_be_denied(self):
        for path in (f"/api/sessions/{self.sid}/status",
                     f"/api/sessions/{self.sid}/results",
                     f"/api/sessions/{self.sid}/gates"):
            with self.subTest(path=path):
                r = await self.client.get(path)
                self.assertIn(r.status_code, (401, 403, 404))

    @unittest.expectedFailure
    async def test_bogus_bearer_cannot_read_legal_results(self):
        r = await self.client.get(f"/api/sessions/{self.sid}/results",
                                  headers={"Authorization": "Bearer forged"})
        self.assertIn(r.status_code, (401, 403, 404))

    @unittest.expectedFailure
    async def test_user_supplied_identity_cannot_establish_ownership(self):
        r = await self.client.post("/api/sessions",
              json={"num_rounds": 1, "user_id": "spoofed-owner"})
        self.assertEqual(r.status_code, 200)
        saved = main.sessions[r.json()["session_id"]]
        self.assertIn("owner_issuer", saved)
        self.assertIn("owner_subject", saved)
        self.assertNotEqual(saved["owner_subject"], "spoofed-owner")

    @unittest.expectedFailure
    async def test_forged_reviewer_cannot_authorize_sensitive_gate(self):
        session = main.sessions[self.sid]
        gate = session["engine"].gate_evaluator.record_trigger({
            "gate_number": 1, "affected_cluster": "foundation"})
        session["pending_gates"] = [gate["gate_id"]]
        session["status"] = "awaiting_gate"
        r = await self.client.post(f"/api/sessions/{self.sid}/gate-decision",
            json={"session_id": self.sid, "gate_number": 1,
                  "gate_id": gate["gate_id"], "decision": "approve",
                  "human_review_id": "impersonated-lawyer",
                  "reasoning": "I reviewed the evidence."})
        self.assertIn(r.status_code, (401, 403, 404))

    @unittest.expectedFailure
    async def test_anonymous_event_stream_must_be_denied_before_subscribing(self):
        main.sessions[self.sid]["status"] = "completed"
        r = await self.client.get(f"/api/sessions/{self.sid}/stream")
        self.assertIn(r.status_code, (401, 403, 404))
