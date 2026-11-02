"""Constrói um LexicalIndex a partir das versões de fontes jurídicas do locatário. Somente leitura."""
from __future__ import annotations

from sqlalchemy import select

from evidence.models import LegalSource, SourceVersion

from .index import LexicalIndex, SourceChunkInput

ALLOWED_SOURCE_TYPES = ("statute", "precedent", "regulation", "other")


def build_legal_index(repo, *, as_of: str, source_types=None, max_chunk_chars: int = 900):
    """Indexa as versões de fontes do locatário de ``repo``. Executa apenas SELECTs.

    O isolamento entre locatários vem do tenant_id do repositório; versões de outro
    locatário nunca entram no índice.
    """
    wanted = tuple(source_types) if source_types is not None else ALLOWED_SOURCE_TYPES
    unknown = set(wanted) - set(ALLOWED_SOURCE_TYPES)
    if unknown:
        raise ValueError(f"tipos de fonte desconhecidos: {sorted(unknown)}")

    rows = repo.session.execute(
        select(SourceVersion, LegalSource)
        .join(LegalSource, (LegalSource.tenant_id == SourceVersion.tenant_id)
              & (LegalSource.id == SourceVersion.legal_source_id))
        .where(SourceVersion.tenant_id == repo.tenant_id,
               LegalSource.tenant_id == repo.tenant_id,
               LegalSource.source_type.in_(wanted))
        .order_by(SourceVersion.id)
    ).all()

    inputs = [
        SourceChunkInput(
            source_version_id=version.id,
            legal_source_id=source.id,
            version_label=version.version_label,
            text=version.text,
            effective_from=version.effective_from or "",
            effective_to=version.effective_to or "",
        )
        for version, source in rows
    ]
    return LexicalIndex(inputs, as_of=as_of, max_chunk_chars=max_chunk_chars)
