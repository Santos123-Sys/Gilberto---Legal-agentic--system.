"""Testes do cliente HTTP do serviço br-eli-mcp (offline, com transporte simulado)."""

import json
import os
import unittest

import httpx

from legal_sources import ALLOWED_TOOLS, BrEliClient, BrEliError

TOKEN = "t" * 40
BASE = "https://brel.example.test"


def _ok(text_payload):
    body = {"jsonrpc": "2.0", "id": 1,
            "result": {"content": [{"type": "text", "text": json.dumps(text_payload)}],
                       "isError": False}}
    return httpx.Response(200, json=body)


class BrEliClientTests(unittest.TestCase):
    def _client(self, handler, **kw):
        return BrEliClient(BASE, TOKEN, transport=httpx.MockTransport(handler), **kw)

    def test_sends_bearer_token_and_jsonrpc_tools_call(self):
        seen = {}

        def handler(request):
            seen["auth"] = request.headers["authorization"]
            seen["body"] = json.loads(request.content)
            seen["url"] = str(request.url)
            return _ok({"status": "ok"})

        c = self._client(handler)
        self.assertEqual(c.call_tool("br_coverage", {}), {"status": "ok"})
        self.assertEqual(seen["auth"], f"Bearer {TOKEN}")
        self.assertEqual(seen["url"], BASE + "/mcp")
        self.assertEqual(seen["body"]["method"], "tools/call")
        self.assertEqual(seen["body"]["params"]["name"], "br_coverage")

    def test_refuses_tools_outside_allowlist_without_network(self):
        calls = []
        c = self._client(lambda r: calls.append(r) or _ok({}))
        with self.assertRaises(BrEliError):
            c.call_tool("br_nao_existe", {})
        self.assertEqual(calls, [])

    def test_allowlist_is_read_only_names_only(self):
        self.assertTrue(all(n.startswith("br_") for n in ALLOWED_TOOLS))
        self.assertNotIn("br_write", " ".join(ALLOWED_TOOLS))

    def test_rejects_plain_http_for_remote_host(self):
        with self.assertRaises(BrEliError):
            BrEliClient("http://brel.example.test", TOKEN)

    def test_allows_http_only_for_localhost(self):
        c = BrEliClient("http://localhost:8080", TOKEN,
                        transport=httpx.MockTransport(lambda r: _ok({})))
        c.close()

    def test_rejects_short_token(self):
        with self.assertRaises(BrEliError):
            BrEliClient(BASE, "curto")

    def test_http_error_status_raises_without_retry(self):
        calls = []

        def handler(request):
            calls.append(1)
            return httpx.Response(503)

        with self.assertRaises(BrEliError):
            self._client(handler).call_tool("br_coverage", {})
        self.assertEqual(len(calls), 1)

    def test_tool_error_flag_is_surfaced(self):
        body = {"jsonrpc": "2.0", "id": 1,
                "result": {"content": [{"type": "text", "text": "x"}], "isError": True}}
        with self.assertRaises(BrEliError):
            self._client(lambda r: httpx.Response(200, json=body)).call_tool("br_coverage", {})

    def test_oversized_response_is_refused(self):
        big = {"jsonrpc": "2.0", "id": 1, "result": {"content": [
            {"type": "text", "text": "a" * 2000}], "isError": False}}
        c = self._client(lambda r: httpx.Response(200, json=big), max_response_bytes=500)
        with self.assertRaises(BrEliError):
            c.call_tool("br_coverage", {})

    def test_network_failure_is_wrapped(self):
        def handler(request):
            raise httpx.ConnectError("boom", request=request)

        with self.assertRaises(BrEliError):
            self._client(handler).call_tool("br_coverage", {})


@unittest.skipUnless(os.environ.get("BR_ELI_LIVE_URL"),
                     "defina BR_ELI_LIVE_URL e BR_ELI_LIVE_TOKEN para o teste ao vivo")
class BrEliLiveTests(unittest.TestCase):
    def test_coverage_against_running_service(self):
        c = BrEliClient(os.environ["BR_ELI_LIVE_URL"], os.environ["BR_ELI_LIVE_TOKEN"])
        try:
            data = c.call_tool("br_coverage", {})
        finally:
            c.close()
        self.assertEqual(data.get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
