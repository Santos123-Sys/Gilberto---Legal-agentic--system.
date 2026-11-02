"""PR-R1: recuperação léxica determinística sobre versões de fontes jurídicas.

Não está ligada ao caminho de requisições. Ver docs/legal-retrieval-design.md.
"""
from .chunking import Chunk, chunk_text
from .index import (
    EVIDENCE_ROLE, Hit, LexicalIndex, RetrievalError, SourceChunkInput, vigencia_status,
)
from .text import fold, tokenize

__all__ = [
    "Chunk", "chunk_text", "EVIDENCE_ROLE", "Hit", "LexicalIndex", "RetrievalError",
    "SourceChunkInput", "vigencia_status", "fold", "tokenize",
]
