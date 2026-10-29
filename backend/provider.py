"""Bounded Maritaca chat completion transport. Never logs credentials or payloads."""
import httpx
import logging
import threading
from config import settings

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    def __init__(self, code, message, http_status=None):
        self.code = code
        # Safe, bounded diagnostic metadata only. Never persist response bodies,
        # provider request headers, credentials, or legal-document contents.
        self.http_status = http_status
        super().__init__(message)


class MaritacaClient:
    def __init__(self):
        self._usage_lock = threading.Lock()
        self._token_counters = {"prompt_tokens": 0, "completion_tokens": 0,
                                "reported_calls": 0, "unreported_calls": 0}

    def usage_snapshot(self):
        """Provider-supplied metering, not an invoice or exact price."""
        with self._usage_lock:
            return {**self._token_counters, "kind": "provider_reported_when_available"}

    def _record_usage(self, body):
        source = body.get("usage") if isinstance(body, dict) else None
        if not isinstance(source, dict):
            with self._usage_lock:
                self._token_counters["unreported_calls"] += 1
            return
        a, b = source.get("prompt_tokens"), source.get("completion_tokens")
        if (not isinstance(a, int) or isinstance(a, bool) or a < 0
                or not isinstance(b, int) or isinstance(b, bool) or b < 0):
            with self._usage_lock:
                self._token_counters["unreported_calls"] += 1
            return
        with self._usage_lock:
            self._token_counters["prompt_tokens"] += a
            self._token_counters["completion_tokens"] += b
            self._token_counters["reported_calls"] += 1

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
            400: ('invalid_request', 'Maritaca rejected the request (HTTP 400). Check model and parameters.'),
            401: ('authentication', 'Maritaca rejected the API credential (HTTP 401). Check MARITACA_API_KEY.'),
            402: ('billing', 'Maritaca reported insufficient account credits (HTTP 402). Check billing.'),
            403: ('permission', 'Maritaca denied access (HTTP 403). Check permissions and model entitlement.'),
            404: ('invalid_endpoint', 'Maritaca returned HTTP 404. Verify MARITACA_BASE_URL and the API endpoint.'),
            405: ('invalid_endpoint', 'Maritaca returned HTTP 405. Verify the configured API endpoint.'),
            408: ('upstream_timeout', 'Maritaca returned HTTP 408. Request completion is uncertain; no automatic retry was sent.'),
            409: ('request_conflict', 'Maritaca returned HTTP 409. Check the provider request configuration.'),
            422: ('invalid_request', 'Maritaca rejected the input (HTTP 422). Check model and supported parameters.'),
            429: ('rate_limit', 'Maritaca returned HTTP 429 (rate limit). Check provider limits before starting a new review.'),
        }
        status = response.status_code
        error = errors.get(status)
        if error is None and not response.is_success:
            if 300 <= status < 400:
                error = ('unexpected_redirect', 'Maritaca returned HTTP ' + str(status) +
                         '. Check MARITACA_BASE_URL; provider redirects are not followed.')
            elif 400 <= status < 500:
                error = ('provider_rejected_request', 'Maritaca rejected the request (HTTP ' +
                         str(status) + '). Check API configuration and account permissions.')
            elif 500 <= status < 600:
                error = ('provider_unavailable', 'Maritaca returned an upstream HTTP ' +
                         str(status) + ' error. Availability is uncertain; saved findings remain available. '
                         'No automatic retry was sent.')
            else:
                error = ('unexpected_http_status', 'Maritaca returned unexpected HTTP status ' +
                         str(status) + '. Review provider configuration.')
        if error is not None:
            code, message = error
            # Only categorical diagnostics: no contract text, raw provider body or key.
            logger.warning('Maritaca request failed: code=%s http_status=%d', code, status)
            raise ProviderError(code, message, http_status=status)
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
        self._record_usage(body)
        return content

# A second vendor may receive confidential legal documents only when BOTH the
# operator allowlists its HTTPS host and the session owner explicitly consents.
# Never retry an uncertain completion on another provider.
from ipaddress import ip_address
from urllib.parse import urlparse


def approved_backup_url():
    raw = settings.FALLBACK_LLM_BASE_URL.strip()
    allowed = {host.strip().lower() for host in settings.FALLBACK_LLM_ALLOWED_HOSTS.split(",") if host.strip()}
    if not raw or not allowed or not settings.FALLBACK_LLM_MODEL.strip() or not settings.FALLBACK_LLM_API_KEY.strip():
        return None
    try:
        parsed = urlparse(raw)
        host = parsed.hostname
        port = parsed.port
        if host is not None:
            ip_address(host)  # IP endpoints are prohibited, including RFC1918 and loopback.
            return None
    except ValueError:
        # Non-IP hostname is allowed; invalid port is still rejected below.
        try:
            parsed = urlparse(raw)
            host = parsed.hostname
            port = parsed.port
        except ValueError:
            return None
    if (parsed.scheme != "https" or not host or host.lower() not in allowed or
            port not in (None, 443) or parsed.username or parsed.password or
            parsed.query or parsed.fragment or parsed.params or
            parsed.path.rstrip("/") not in ("", "/v1", "/api") or
            raw != raw.strip() or raw.endswith("//")):
        return None
    # Explicit hostname validation also forbids host aliases and local domains.
    if host.lower() in ("localhost",) or host.lower().endswith((".localhost", ".local", ".internal")):
        return None
    return raw.rstrip("/") + "/chat/completions"


def backup_configured():
    return approved_backup_url() is not None


class BackupClient(MaritacaClient):
    """Operator-authorized OpenAI-compatible endpoint; one request, never replayed."""
    def call(self, messages):
        url = approved_backup_url()
        if not url:
            raise ProviderError("backup_not_configured",
                                "No approved backup model is configured for this workspace.")
        try:
            with httpx.Client(timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
                response = client.post(url, headers={
                    "Authorization": "Bearer " + settings.FALLBACK_LLM_API_KEY.strip(),
                    "Content-Type": "application/json",
                }, json={"model": settings.FALLBACK_LLM_MODEL, "messages": messages,
                         "temperature": settings.TEMPERATURE, "max_tokens": settings.MAX_TOKENS})
        except httpx.TimeoutException:
            raise ProviderError("timeout",
                                "Backup inference timed out. Completion and billing are uncertain; no retry was sent.") from None
        except httpx.RequestError:
            raise ProviderError("connection",
                                "Backup inference could not be reached; no retry was sent.") from None
        if not response.is_success:
            status = response.status_code
            if status == 429:
                code, detail = "rate_limit", "The approved backup provider rate-limited the request."
            elif status in (401, 403):
                code, detail = "authentication", "The approved backup provider rejected access."
            elif status == 402:
                code, detail = "billing", "The approved backup provider account has insufficient credit."
            elif 500 <= status < 600:
                code, detail = "provider_unavailable", "The approved backup provider is unavailable."
            else:
                code, detail = "provider_rejected_request", "The approved backup provider rejected the request."
            logger.warning("Backup inference failed: code=%s http_status=%d", code, status)
            raise ProviderError(code, detail + " No automatic retry was sent.", http_status=status)
        try:
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("truncated", "Backup output was truncated; this review is incomplete.")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError()
        except (ValueError, TypeError, IndexError, KeyError):
            raise ProviderError("invalid_response", "Backup inference returned an invalid response.") from None
        self._record_usage(body)
        return content
