import unittest
from unittest.mock import patch
import httpx
from provider import MaritacaClient
from config import settings

class ProviderTokenMeteringTests(unittest.TestCase):
    def invoke(self, client, payload):
        with patch.object(settings,"MARITACA_API_KEY","test-key"), patch("provider.httpx.Client") as transport:
            transport.return_value.__enter__.return_value.post.return_value = httpx.Response(200,json=payload)
            return client.call([{"role":"user","content":"synthetic only"}])

    def test_exact_provider_reported_usage(self):
        client=MaritacaClient()
        response={"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}],
                  "usage":{"prompt_tokens":123,"completion_tokens":45,"total_tokens":168}}
        self.assertEqual(self.invoke(client,response),"{}")
        self.invoke(client,response)
        usage=client.usage_snapshot()
        self.assertEqual(usage["prompt_tokens"],246)
        self.assertEqual(usage["completion_tokens"],90)
        self.assertEqual(usage["reported_calls"],2)
        self.assertEqual(usage["unreported_calls"],0)
        self.assertNotIn("messages",usage)

    def test_missing_or_invalid_usage_is_not_fabricated(self):
        client=MaritacaClient()
        self.invoke(client,{"choices":[{"message":{"content":"{}"}}]})
        self.invoke(client,{"choices":[{"message":{"content":"{}"}}],
                            "usage":{"prompt_tokens":-2,"completion_tokens":4}})
        snapshot=client.usage_snapshot()
        self.assertEqual(snapshot["unreported_calls"],2)
        self.assertEqual(snapshot["reported_calls"],0)
        self.assertEqual(snapshot["prompt_tokens"],0)
        self.assertEqual(snapshot["completion_tokens"],0)
