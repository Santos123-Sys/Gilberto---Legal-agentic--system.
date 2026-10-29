"""P0 release gates: authentication must be operational before Railway marks ready.

Use synthetic credentials and isolated temporary SQLite databases only.
These checks cannot replace live two-account staging verification.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

import httpx
import main
from config import settings
from security import local_identity


class LocalAuthReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name
        patches = (
            patch.dict(os.environ, {
                "IDENTITY_DB_PATH": self.folder + "/identity.sqlite3",
                "SESSION_DB_PATH": self.folder + "/session.sqlite3",
            }),
            patch.object(settings, "AUTH_MODE", "local"),
            patch.object(settings, "LOCAL_AUTH_PROXY_SECRET", "X" * 48),
            patch.object(settings, "LOCAL_AUTH_APP_ORIGIN", "https://gilberto-staging.example.test"),
            patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", True),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="https://gilberto-staging.example.test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_local_mode_is_ready_when_proxy_origin_and_storage_are_valid(self):
        response = await self.client.get("/api/ready")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"status": "ready"})
        # First-administrator setup is permitted while ready; no default account.
        self.assertFalse(local_identity.has_bootstrapped())

    async def test_missing_weak_proxy_secret_never_reports_ready(self):
        for invalid in ("", "too-short"):
            with self.subTest(secret=invalid), patch.object(settings, "LOCAL_AUTH_PROXY_SECRET", invalid):
                response = await self.client.get("/api/ready")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("X" * 48, response.text)
                # Auth routes must agree with the readiness gate.
                denied = await self.client.get("/api/auth/bootstrap-status")
                self.assertEqual(denied.status_code, 503)

    async def test_origin_and_cookie_configuration_fail_closed(self):
        bad = (
            ("", True),
            ("http://gilberto-staging.example.test", True),
            ("https://gilberto-staging.example.test/api", True),
            ("https://gilberto-staging.example.test/", True),
            ("https://gilberto-staging.example.test?token=x", True),
            ("https://user:password@gilberto-staging.example.test", True),
            ("https://gilberto-staging.example.test:99999", True),
            ("https://gilberto-staging.example.test", False),
            ("http://attacker.example.test", False),
        )
        for origin, secure in bad:
            with self.subTest(origin=origin, secure=secure), \\
                 patch.object(settings, "LOCAL_AUTH_APP_ORIGIN", origin), \\
                 patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", secure):
                self.assertEqual((await self.client.get("/api/ready")).status_code, 503)
                self.assertEqual((await self.client.get("/api/auth/me",
                    headers={"X-Gilberto-Proxy-Auth": "X" * 48})).status_code, 503)

    async def test_http_loopback_is_allowed_only_for_development(self):
        with patch.object(settings, "LOCAL_AUTH_APP_ORIGIN", "http://127.0.0.1:5173"), \\
             patch.object(settings, "LOCAL_AUTH_COOKIE_SECURE", False):
            response = await self.client.get("/api/ready")
        self.assertEqual(response.status_code, 200, response.text)

    async def test_inaccessible_identity_database_does_not_look_ready(self):
        with patch.object(local_identity, "connect", side_effect=OSError("private path")):
            response = await self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private path", response.text)

    async def test_inaccessible_checkpoint_database_does_not_look_ready(self):
        with patch.object(main.session_store, "is_ready", side_effect=OSError("private checkpoint")):
            response = await self.client.get("/api/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private checkpoint", response.text)
