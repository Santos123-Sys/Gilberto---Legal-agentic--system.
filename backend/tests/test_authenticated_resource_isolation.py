"""P0 real-route authorization suite: no expected failures and no LLM calls."""
import asyncio
import time
import unittest
from unittest.mock import patch

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

import main
from config import settings


class AuthenticatedResourceIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        main.app.dependency_overrides.pop(main.current_principal, None)
        main.sessions.clear()
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public = self.key.public_key()
        self.patchers = [
            patch.object(settings, "OIDC_ISSUER", "https://id.example.test/"),
            patch.object(settings, "OIDC_AUDIENCE", "gilberto-api"),
            patch.object(settings, "OIDC_JWKS_URL", "https://id.example.test/jwks"),
            patch.object(main, "_trusted_key_resolver", return_value=lambda _: self.public),
        ]
        for item in self.patchers:
            item.start()
            self.addCleanup(item.stop)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)
        self.owner = self.token("lawyer-a")
        self.other = self.token("lawyer-b")
        response = await self.client.post("/api/sessions", json={"num_rounds": 1},
                                          headers=self.authorization(self.owner))
        self.assertEqual(response.status_code, 200, response.text)
        self.sid = response.json()["session_id"]
        self.session = main.sessions[self.sid]

    def authorization(self, token):
        return {"Authorization": f"Bearer {token}"}

    def token(self, subject, *, issuer="https://id.example.test/", audience="gilberto-api",
              exp=None, signing_key=None):
        payload = {"iss": issuer, "sub": subject, "aud": audience,
                   "exp": exp or int(time.time()) + 300, "iat": int(time.time())}
        return jwt.encode(payload, signing_key or self.key, algorithm="RS256",
                          headers={"kid": "fixed-key"})

    async def test_requires_token_and_checks_signature_audience_expiry(self):
        unauthorized = (None, "Bearer arbitrary", self.token("owner", issuer="https://evil.test/"),
                        self.token("owner", audience="other-api"),
                        self.token("owner", exp=int(time.time()) - 1000),
                        self.token("owner", signing_key=rsa.generate_private_key(
                            public_exponent=65537, key_size=2048)))
        for token in unauthorized:
            headers = {"Authorization": token} if token and token.startswith("Bearer ") else (
                self.authorization(token) if token else {})
            with self.subTest(token=str(token)[:12]):
                response = await self.client.get(f"/api/sessions/{self.sid}/status",
                                                  headers=headers)
                self.assertEqual(response.status_code, 401)

    async def test_unowned_legacy_and_cross_user_are_hidden(self):
        other_headers = self.authorization(self.other)
        own_headers = self.authorization(self.owner)
        self.session["status"] = "completed"  # SSE must reach its terminal frame.
        for route in ("status", "results", "gates", "stream?cursor=0"):
            own = await self.client.get(f"/api/sessions/{self.sid}/{route}", headers=own_headers)
            self.assertEqual(own.status_code, 200, route)
            denied = await self.client.get(f"/api/sessions/{self.sid}/{route}", headers=other_headers)
            self.assertEqual(denied.status_code, 404, route)
        self.session.pop("owner_issuer")
        self.session.pop("owner_subject")
        denied = await self.client.get(f"/api/sessions/{self.sid}/results", headers=own_headers)
        self.assertEqual(denied.status_code, 404)

    async def test_authorize_all_state_mutations_before_work(self):
        headers = self.authorization(self.other)
        sid = self.sid
        for path, kwargs in (
            (f"/api/sessions/{sid}/start", {"files": {"document": ("contract.txt", b"Test")}}),
            (f"/api/sessions/{sid}/feedback", {"json": {"feedback": "Please review clause"}}),
            (f"/api/sessions/{sid}/accept", {}),
            (f"/api/sessions/{sid}/gate-decision", {"json": {
                "session_id": sid, "gate_number": 1, "gate_id": "unknown",
                "decision": "approve", "human_review_id": "lawyer-a",
                "reasoning": "Reviewed personally"}}),
        ):
            with self.subTest(path=path):
                resp = await self.client.post(path, headers=headers, **kwargs)
                self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.session["status"], "created")
        self.assertIsNone(self.session["task"])

    async def test_caller_user_id_is_ignored(self):
        resp = await self.client.post("/api/sessions",
            json={"num_rounds": 1, "user_id": "lawyer-b"},
            headers=self.authorization(self.owner))
        self.assertEqual(resp.status_code, 200)
        obj = main.sessions[resp.json()["session_id"]]
        self.assertEqual(obj["owner_subject"], "lawyer-a")
        self.assertNotIn("user_id", obj["config"])

    async def test_reviewer_identity_derives_from_token(self):
        from gates.human_feedback import GateEvaluator
        record = self.session["engine"].gate_evaluator.record_trigger(
            {"gate_number": 1, "affected_cluster": "foundation"})
        self.session["pending_gates"] = [record["gate_id"]]
        self.session["status"] = "awaiting_gate"
        resp = await self.client.post(f"/api/sessions/{self.sid}/gate-decision",
            headers=self.authorization(self.owner), json={
                "session_id": self.sid, "gate_number": 1, "gate_id": record["gate_id"],
                "decision": "approve", "human_review_id": "forged-supervisor",
                "reasoning": "I have reviewed"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["record"]["human_decision"]["human_review_id"], "lawyer-a")

    async def test_unconfigured_provider_fails_closed(self):
        with patch.object(settings, "OIDC_ISSUER", ""):
            resp = await self.client.get(f"/api/sessions/{self.sid}/status",
                    headers=self.authorization(self.owner))
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn("sessions.sqlite", resp.text)
