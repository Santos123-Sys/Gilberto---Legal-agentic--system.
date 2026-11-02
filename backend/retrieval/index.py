"""Índice léxico (BM25) sobre fragmentos de fontes jurídicas, filtrado pela vigência.

O que este módulo NÃO faz:
- Não prova que um dispositivo existe, está em vigor, é vinculante ou foi citado
  corretamente. Um status ``vigencia_*`` descreve apenas as datas registradas na
  versão da fonte. Não é uma verificação jurídica.
- Não chama modelo de linguagem, serviço de embeddings nem rede.
- Um resultado é evidência para leitura, nunca uma instrução. O texto da fonte é
  devolvido sem alteração e marcado com ``role = "evidencia_nao_instrucao"``.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .chunking import chunk_text
from .text import tokenize

K1 = 1.2
B = 0.75
MAX_QUERY_TOKENS = 32
MAX_TOP_K = 20
MAX_INDEX_CHUNKS = 100_000

VIGENCIA_INCLUIDA_PELAS_DATAS = "vigente_pelas_datas_registradas"
VIGENCIA_SEM_DATAS = "vigencia_nao_informada"
VIGENCIA_EXCLUIDA = {
    "ainda_nao_vigente": "a data de início é posterior à data de referência",
    "encerrada_antes_da_data": "a data de fim é anterior à data de referência",
}  # motivos de exclusão, para auditoria
EVIDENCE_ROLE = "evidencia_nao_instrucao"


class RetrievalError(ValueError):
    """Pedido inválido ou limite do índice excedido."""


@dataclass(frozen=True)
class SourceChunkInput:
    source_version_id: str
    legal_source_id: str
    version_label: str
    text: str
    effective_from: str = ""
    effective_to: str = ""


@dataclass(frozen=True)
class Hit:
    source_version_id: str
    legal_source_id: str
    version_label: str
    start_offset: int
    end_offset: int
    quoted_text: str
    score: float
    vigencia_status: str
    authority_verified: bool = False
    role: str = EVIDENCE_ROLE


@dataclass
class _Entry:
    source_version_id: str
    legal_source_id: str
    version_label: str
    start: int
    end: int
    text: str
    vigencia_status: str
    term_counts: Counter = field(default_factory=Counter)
    length: int = 0


def _parse_date(value: str, field_name: str) -> date | None:
    if value == "":
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RetrievalError(f"{field_name} deve ser AAAA-MM-DD ou vazio") from exc


def vigencia_status(as_of: date, effective_from: str, effective_to: str) -> tuple[bool, str]:
    """Retorna (incluída, status). Datas desconhecidas são incluídas, mas rotuladas; nunca tratadas como vigentes."""
    start = _parse_date(effective_from, "effective_from")
    end = _parse_date(effective_to, "effective_to")
    if start is not None and start > as_of:
        return False, "ainda_nao_vigente"
    if end is not None and end < as_of:
        return False, "encerrada_antes_da_data"
    if start is None and end is None:
        return True, VIGENCIA_SEM_DATAS
    return True, VIGENCIA_INCLUIDA_PELAS_DATAS


class LexicalIndex:
    """BM25 sobre os fragmentos vigentes em ``as_of``, segundo as datas registradas."""

    def __init__(self, sources, *, as_of: str, max_chunk_chars: int = 900,
                 max_chunks: int = MAX_INDEX_CHUNKS):
        try:
            self.as_of = date.fromisoformat(as_of)
        except (TypeError, ValueError) as exc:
            raise RetrievalError("as_of deve ser uma data AAAA-MM-DD") from exc

        self.excluded_by_date: Counter = Counter()
        self.entries: list[_Entry] = []
        for src in sources:
            included, status = vigencia_status(self.as_of, src.effective_from, src.effective_to)
            if not included:
                self.excluded_by_date[status] += 1
                continue
            for chunk in chunk_text(src.text, max_chars=max_chunk_chars):
                if len(self.entries) >= max_chunks:
                    raise RetrievalError("o índice excedeu o limite configurado de fragmentos")
                counts = Counter(tokenize(chunk.text))
                self.entries.append(_Entry(
                    source_version_id=src.source_version_id,
                    legal_source_id=src.legal_source_id,
                    version_label=src.version_label,
                    start=chunk.start, end=chunk.end, text=chunk.text,
                    vigencia_status=status, term_counts=counts,
                    length=sum(counts.values()) or 1,
                ))

        self._doc_freq: Counter = Counter()
        for entry in self.entries:
            self._doc_freq.update(entry.term_counts.keys())
        n = len(self.entries)
        self._avg_len = (sum(e.length for e in self.entries) / n) if n else 0.0
        self._n = n

    def __len__(self) -> int:
        return self._n

    def _idf(self, term: str) -> float:
        df = self._doc_freq.get(term, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        if not isinstance(query, str):
            raise RetrievalError("a consulta deve ser um texto")
        if not (1 <= top_k <= MAX_TOP_K):
            raise RetrievalError(f"top_k deve estar entre 1 e {MAX_TOP_K}")
        terms = list(dict.fromkeys(tokenize(query)))[:MAX_QUERY_TOKENS]
        if not terms or self._n == 0:
            return []

        idf = {t: self._idf(t) for t in terms if self._doc_freq.get(t, 0)}
        scored = []
        for entry in self.entries:
            score = 0.0
            for term, weight in idf.items():
                tf = entry.term_counts.get(term, 0)
                if not tf:
                    continue
                norm = tf * (K1 + 1) / (tf + K1 * (1 - B + B * entry.length / self._avg_len))
                score += weight * norm
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda pair: (-pair[0], pair[1].source_version_id, pair[1].start))
        return [
            Hit(source_version_id=e.source_version_id, legal_source_id=e.legal_source_id,
                version_label=e.version_label, start_offset=e.start, end_offset=e.end,
                quoted_text=e.text, score=round(s, 6), vigencia_status=e.vigencia_status)
            for s, e in scored[:top_k]
        ]
