"""Serviço HTTP do br-eli-mcp para implantação separada (Railway).

Expõe o servidor MCP do pacote vendorizado por transporte *streamable-http*,
em modo sem estado, atrás de um token de portador compartilhado.

Decisões:
- Falha fechada: sem ``BR_ELI_SERVICE_TOKEN`` (com pelo menos 32 caracteres) o
  processo não inicia.
- ``/health`` é a única rota sem autenticação; não expõe dados.
- Nenhuma ferramenta é adicionada ou alterada: o conjunto de ferramentas é o do
  upstream, todas somente leitura.

Execução local: ``PYTHONPATH=src:service uvicorn app:app --port 8080``.
"""

from __future__ import annotations

import hmac
import os

from br_eli_mcp.server import mcp

_HEALTH_PATH = "/health"
_MIN_TOKEN_LENGTH = 32


def _load_token() -> str:
    token = os.environ.get("BR_ELI_SERVICE_TOKEN", "")
    if len(token) < _MIN_TOKEN_LENGTH:
        raise RuntimeError(
            "BR_ELI_SERVICE_TOKEN ausente ou curto demais "
            f"(mínimo {_MIN_TOKEN_LENGTH} caracteres); o serviço não inicia sem ele."
        )
    return token


class BearerAuthMiddleware:
    """Middleware ASGI que exige ``Authorization: Bearer <token>`` em tudo, exceto /health."""

    def __init__(self, app, token: str) -> None:
        self.app = app
        self._token = token.encode("utf-8")

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == _HEALTH_PATH and scope["method"] == "GET":
            await _json(send, 200, b'{"status":"ok"}')
            return
        presented = b""
        for name, value in scope.get("headers", []):
            if name == b"authorization" and value.startswith(b"Bearer "):
                presented = value[len(b"Bearer "):]
                break
        if not hmac.compare_digest(presented, self._token):
            await _json(send, 401, b'{"error":"unauthorized"}')
            return
        await self.app(scope, receive, send)


async def _json(send, status: int, body: bytes) -> None:
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


_token = _load_token()

_inner = mcp.http_app(
    path="/mcp",
    transport="streamable-http",
    json_response=True,
    stateless_http=True,
)

app = BearerAuthMiddleware(_inner, _token)
