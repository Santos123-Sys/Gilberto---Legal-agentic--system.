"""
br_eli_client.py — Cliente fino do serviço br-eli-mcp (HTTP, somente leitura)
═══════════════════════════════════════════════════════════════════════════
O serviço roda em implantação separada (ver third_party/br_eli_mcp/service).
Este módulo só fala o protocolo MCP sobre HTTP (JSON-RPC ``tools/call``) e não
importa nenhuma dependência do pacote vendorizado.

Garantias:
- Apenas ferramentas da lista ``ALLOWED_TOOLS`` (todas somente leitura) podem ser chamadas.
- URL obrigatoriamente HTTPS, exceto ``localhost`` para desenvolvimento.
- Token de portador enviado apenas ao host configurado; nunca registrado.
- Sem novas tentativas automáticas: uma falha é devolvida ao chamador.
- Resposta limitada em tamanho antes de ser decodificada.
"""

from __future__ import annotations

import json
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx

ALLOWED_TOOLS: frozenset[str] = frozenset({
    "br_search_proposicoes",
    "br_get_proposicao",
    "br_get_norma",
    "br_get_norma_index",
    "br_get_norma_texto",
    "br_search_processos",
    "br_get_processo",
    "br_search_case_stj",
    "br_get_case_stj",
    "br_get_case_carf",
    "br_search_case_tst",
    "br_get_case_tst",
    "br_search_case_tcu",
    "br_get_case_tcu",
    "br_coverage",
})

_PROTOCOL_VERSION = "2025-06-18"
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


class BrEliError(RuntimeError):
    """Falha ao consultar o serviço br-eli-mcp."""


def _validate_base_url(url: str) -> str:
    url = url.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return url
    if parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS:
        return url
    raise BrEliError("BR_ELI_SERVICE_URL deve ser HTTPS (HTTP só para localhost).")


class BrEliClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 5_000_000,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not token or len(token) < 32:
            raise BrEliError("Token do serviço br-eli ausente ou curto demais.")
        self._url = _validate_base_url(base_url) + "/mcp"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        self._max_bytes = max_response_bytes
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport)
        self._next_id = 0

    def close(self) -> None:
        self._client.close()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in ALLOWED_TOOLS:
            raise BrEliError(f"Ferramenta não permitida: {name}")
        self._next_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        try:
            with self._client.stream("POST", self._url, headers=self._headers,
                                     json=payload) as resp:
                if resp.status_code != 200:
                    raise BrEliError(f"Serviço br-eli respondeu HTTP {resp.status_code}.")
                raw = self._read_limited(resp)
        except httpx.HTTPError as exc:
            raise BrEliError(f"Falha de rede ao consultar br-eli: {type(exc).__name__}.") from exc

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BrEliError("Resposta inválida do serviço br-eli.") from exc
        if "error" in body:
            raise BrEliError("O serviço br-eli devolveu erro de protocolo.")
        result = body.get("result", {})
        if result.get("isError"):
            raise BrEliError("A ferramenta br-eli devolveu erro.")
        texts = [c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"]
        if not texts:
            raise BrEliError("Resposta vazia do serviço br-eli.")
        try:
            return json.loads(texts[0])
        except json.JSONDecodeError as exc:
            raise BrEliError("Conteúdo da ferramenta não é JSON.") from exc

    def _read_limited(self, resp: httpx.Response) -> bytes:
        buf = bytearray()
        for chunk in resp.iter_bytes():
            buf.extend(chunk)
            if len(buf) > self._max_bytes:
                raise BrEliError("Resposta do serviço br-eli excede o limite de tamanho.")
        return bytes(buf)
