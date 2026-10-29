"""Backup continuity: only operator-approved hosts, per-review consent and no replay."""
import unittest
from unittest.mock import patch
import httpx
from config import settings
from provider import BackupClient, ProviderError, approved_backup_url, backup_configured
from engines.debate_engine_v3 import DebateEngineV3
from models.schemas import SessionCreateRequest
import main


class BackupProviderSafetyTests(unittest.TestCase):
    def setUp(self):
        patches = (
            patch.object(settings, "FALLBACK_LLM_BASE_URL", "https://llm.example.test/v1"),
            patch.object(settings, "FALLBACK_LLM_ALLOWED_HOSTS", "llm.example.test"),
            patch.object(settings, "FALLBACK_LLM_MODEL", "operator-approved-model"),
            patch.object(settings, "FALLBACK_LLM_API_KEY", "backup-fixture-secret"),
        )
        for item in patches:
            item.start()
            self.addCleanup(item.stop)

    def test_requires_exact_operator_host_approval_and_https(self):
        self.assertEqual(approved_backup_url(), "https://llm.example.test/v1/chat/completions")
        for address in ("http://llm.example.test/v1", "https://127.0.0.1/v1",
                        "https://evil.example.test/v1", "https://llm.example.test.evil/v1",
                        "https://llm.example.test:8080/v1", "https://a@llm.example.test/v1",
                        "https://llm.example.test/v1?x=1", "https://localhost/v1",
                        "https://llm.example.test/other"):
            with self.subTest(address=address), patch.object(settings, "FALLBACK_LLM_BASE_URL", address):
                self.assertFalse(backup_configured(), address)

    def test_backup_one_request_and_no_secret_or_document_logging(self):
        body = {"choices": [{"message": {"content": '{"score": 3}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        with patch("provider.httpx.Client") as client:
            call = client.return_value.__enter__.return_value.post
            call.return_value = httpx.Response(200, json=body)
            backup = BackupClient()
            self.assertEqual(backup.call([{"role": "user", "content": "confidential-fixture"}]), '{"score": 3}')
            call.assert_called_once()
            self.assertEqual(call.call_args.kwargs["headers"]["Authorization"], "Bearer backup-fixture-secret")
            self.assertEqual(call.call_args.kwargs["json"]["model"], "operator-approved-model")
            self.assertEqual(backup.usage_snapshot()["reported_calls"], 1)

    def test_outage_does_not_call_maritaca_or_replay(self):
        with patch("provider.httpx.Client") as client:
            post = client.return_value.__enter__.return_value.post
            post.return_value = httpx.Response(503, text="secret or confidential-fixture")
            with self.assertLogs("provider", level="WARNING") as logged:
                with self.assertRaises(ProviderError) as raised:
                    BackupClient().call([{"role": "user", "content": "confidential-fixture"}])
            self.assertEqual(raised.exception.code, "provider_unavailable")
            self.assertEqual(post.call_count, 1)
            self.assertNotIn("confidential-fixture", str(raised.exception))
            self.assertNotIn("secret", " ".join(logged.output))
            self.assertNotIn("confidential-fixture", " ".join(logged.output))

    def test_unconfigured_backup_is_fail_closed(self):
        with patch.object(settings, "FALLBACK_LLM_ALLOWED_HOSTS", ""):
            with patch("provider.httpx.Client") as client:
                with self.assertRaises(ProviderError):
                    BackupClient().call([])
                client.assert_not_called()


class BackupSessionSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_fallback_without_separate_owner_consent_and_configuration(self):
        p = main.Principal("https://issuer.example.test", "owner")
        with patch.object(settings, "FALLBACK_LLM_BASE_URL", "https://llm.example.test/v1"), \
             patch.object(settings, "FALLBACK_LLM_ALLOWED_HOSTS", "llm.example.test"), \
             patch.object(settings, "FALLBACK_LLM_MODEL", "approved"), \
             patch.object(settings, "FALLBACK_LLM_API_KEY", "private"):
            with self.assertRaises(main.HTTPException) as denied:
                await main.create_session(SessionCreateRequest(provider_mode="backup"), p)
            self.assertEqual(denied.exception.status_code, 422)
            result = await main.create_session(
                SessionCreateRequest(provider_mode="backup", backup_consent=True), p)
            self.assertEqual(result.config["provider_mode"], "backup")
            self.assertEqual(main.sessions[result.session_id]["engine"].provider_mode, "backup")
        with self.assertRaises(main.HTTPException) as denied:
            await main.create_session(SessionCreateRequest(provider_mode="backup", backup_consent=True), p)
        self.assertEqual(denied.exception.status_code, 503)

    async def test_primary_remains_default(self):
        p = main.Principal("https://issuer.example.test", "owner")
        result = await main.create_session(SessionCreateRequest(), p)
        self.assertEqual(result.config["provider_mode"], "primary")
        self.assertEqual(main.sessions[result.session_id]["engine"].provider_mode, "primary")

    async def test_engine_backup_is_bound_for_whole_review(self):
        engine = DebateEngineV3("one", 5, 1, "contract_review", provider_mode="backup")
        self.assertIsInstance(engine.llm, BackupClient)
        self.assertEqual(engine.provider_mode, "backup")
