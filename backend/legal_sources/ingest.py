"""
ingest.py — Ingestão de dispositivos legais no repositório de evidências
═══════════════════════════════════════════════════════════════════════
Busca o texto de artigos de uma norma pelo serviço br-eli-mcp e o grava como
``SourceVersion`` (uma ``LegalSource`` por dispositivo, identificada pelo
``lex_uri``). A ingestão é limitada e idempotente: o mesmo texto não gera nova
versão (hash do conteúdo).

Decisões de integridade:
- ``effective_from``/``effective_to`` ficam em branco. A data de assinatura da
  norma não é a data de início de vigência, e o serviço não verifica se o texto
  continua em vigor; a recuperação reporta ``vigencia_nao_informada``.
- Só são buscados sufixos presentes no índice da norma (nada é adivinhado).
- O texto é guardado como recebido; nenhuma conferência de autoridade é feita.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .br_eli_client import BrEliClient, BrEliError

MAX_DISPOSITIVOS_POR_CHAMADA = 60
MAX_TEXTO_DISPOSITIVO = 50_000
_URN_RE = re.compile(r"^urn:lex:br:[A-Za-z0-9._:;,\-]{1,200}$")
_SUFIXO_RE = re.compile(r"^art[A-Za-z0-9_\-]{0,40}$")


def _contar_versoes(repo, legal_source_id: str) -> int:
    from sqlalchemy import func, select

    from evidence.models import SourceVersion

    return repo.session.execute(
        select(func.count()).select_from(SourceVersion).where(
            SourceVersion.tenant_id == repo.tenant_id,
            SourceVersion.legal_source_id == legal_source_id)
    ).scalar_one()


class IngestError(ValueError):
    """Pedido de ingestão inválido."""


@dataclass
class IngestResult:
    urn: str
    gravados: int = 0
    ja_existentes: int = 0
    falhas: list[str] = field(default_factory=list)


def validar_urn(urn: str) -> str:
    if not isinstance(urn, str) or not _URN_RE.match(urn):
        raise IngestError("URN inválida: use o formato urn:lex:br:...")
    return urn


def ingerir_dispositivos(repo, client: BrEliClient, urn: str, *,
                         dispositivos: list[str] | None = None,
                         limite: int = 30) -> IngestResult:
    """Grava até ``limite`` artigos da norma ``urn`` como versões de fonte."""
    validar_urn(urn)
    if not 1 <= limite <= MAX_DISPOSITIVOS_POR_CHAMADA:
        raise IngestError(f"limite deve estar entre 1 e {MAX_DISPOSITIVOS_POR_CHAMADA}")

    norma = client.call_tool("br_get_norma", {"urn": urn})
    indice = client.call_tool("br_get_norma_index", {"urn": urn})
    nomes = {item.get("suffix"): item.get("name") for item in indice.get("items", [])
             if isinstance(item, dict) and _SUFIXO_RE.match(str(item.get("suffix", "")))}

    if dispositivos is None:
        escolhidos = list(nomes)[:limite]
    else:
        if len(dispositivos) > limite:
            raise IngestError("mais dispositivos do que o limite informado")
        desconhecidos = [d for d in dispositivos if d not in nomes]
        if desconhecidos:
            raise IngestError("dispositivo ausente do índice da norma")
        escolhidos = list(dict.fromkeys(dispositivos))

    autoridade = (norma.get("norma_nome") or "Norma federal")[:200]
    recuperado_em = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    resultado = IngestResult(urn=urn)

    for sufixo in escolhidos:
        try:
            dado = client.call_tool("br_get_norma_texto", {"urn": urn, "dispositivo": sufixo})
        except BrEliError:
            resultado.falhas.append(sufixo)
            continue
        texto = (dado.get("text") or "").strip()
        if not texto or len(texto) > MAX_TEXTO_DISPOSITIVO:
            resultado.falhas.append(sufixo)
            continue
        fonte = repo.register_legal_source(
            source_type="statute",
            authority=autoridade,
            identifier=str(dado.get("lex_uri") or f"{urn}!{sufixo}")[:300],
            title=str(dado.get("human_readable_citation") or nomes.get(sufixo) or sufixo)[:500],
            official_url=str(dado.get("source_url") or "")[:1000],
        )
        antes = _contar_versoes(repo, fonte.id)
        repo.add_source_version(
            fonte.id, texto,
            version_label=f"normas.leg.br; recuperado em {recuperado_em}; vigencia nao verificada",
        )
        if _contar_versoes(repo, fonte.id) > antes:
            resultado.gravados += 1
        else:
            resultado.ja_existentes += 1
    return resultado
