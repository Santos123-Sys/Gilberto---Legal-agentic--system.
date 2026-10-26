"""Bounded Maritaca chat completion transport. Never logs credentials or payloads."""
import httpx
from config import settings


class ProviderError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


class MaritacaClient:
    def call(self, messages):
        if not settings.MARITACA_API_KEY.strip():
            raise ProviderError('missing_key', 'Configure MARITACA_API_KEY in Railway before starting analysis.')
        try:
            with httpx.Client(timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(settings.MARITACA_BASE_URL.rstrip('/') + '/chat/completions',
                    headers={'Authorization': 'Key ' + settings.MARITACA_API_KEY.strip()},
                    json={'model': settings.MARITACA_MODEL, 'messages': messages,
                          'temperature': settings.TEMPERATURE, 'max_tokens': settings.MAX_TOKENS})
        except httpx.TimeoutException:
            raise ProviderError('timeout', 'Maritaca timed out. No automatic retry was sent.') from None
        except httpx.RequestError:
            raise ProviderError('connection', 'Cannot reach Maritaca. Check provider availability and network access.') from None
        errors = {
            400: ('invalid_request', 'Maritaca rejected the request. Check the configured model and supported parameters.'),
            401: ('authentication', 'Maritaca rejected the API credential. Update MARITACA_API_KEY in Railway.'),
            403: ('permission', 'Maritaca denied access. Check the key permissions and model entitlement.'),
            402: ('billing', 'Maritaca requires available account credits. Check provider billing.'),
            429: ('rate_limit', 'Maritaca rate limit reached. Wait before starting another analysis or check account limits.'),
        }
        if response.status_code in errors:
            raise ProviderError(*errors[response.status_code])
        if not response.is_success:
            raise ProviderError('provider_unavailable', 'Maritaca is unavailable. Saved findings are retained; try again later.')
        try:
            body = response.json()
            choice = body['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise ProviderError('truncated', 'Maritaca output was truncated. Increase MAX_TOKENS or reduce review scope.')
            content = choice['message']['content']
            if not isinstance(content, str) or not content.strip():
                raise ValueError()
        except (KeyError, IndexError, ValueError, TypeError):
            raise ProviderError('invalid_response', 'Maritaca returned an unreadable response; no completed review was certified.') from None
        return content
