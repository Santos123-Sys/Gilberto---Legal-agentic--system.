"""Fragmentação determinística com deslocamentos exatos de caracteres.

Todo fragmento satisfaz ``text[start:end] == chunk.text``. Assim, um fragmento pode
virar um EvidenceSpan com ``add_source_span(..., expected_quote=...)`` e ser
rechecado depois com ``span_is_intact``. Nenhum fragmento é reescrito, normalizado
ou concatenado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_CHARS = 900
MIN_MAX_CHARS = 120

_PARAGRAPH = re.compile(r"[^\n]+(?:\n(?![ \t]*\n)[^\n]+)*")
_SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")


@dataclass(frozen=True)
class Chunk:
    start: int
    end: int
    text: str


def _paragraph_spans(text: str):
    """Sequências máximas de linhas não vazias, como deslocamentos (início, fim)."""
    return [(m.start(), m.end()) for m in _PARAGRAPH.finditer(text) if m.group().strip()]


def _split_long(text: str, start: int, end: int, max_chars: int):
    """Divide um trecho grande nas frases; uma frase grande demais é dividida em espaços, nunca no meio de uma palavra."""
    pieces = []
    for m in _SENTENCE.finditer(text, start, end):
        if m.group().strip():
            pieces.append((m.start(), m.end()))
    if not pieces:
        pieces = [(start, end)]
    out = []
    for p_start, p_end in pieces:
        while p_end - p_start > max_chars:
            cut = text.rfind(" ", p_start, p_start + max_chars)
            if cut <= p_start:
                cut = p_start + max_chars
            out.append((p_start, cut))
            p_start = cut
            while p_start < p_end and text[p_start].isspace():
                p_start += 1
        if p_end > p_start:
            out.append((p_start, p_end))
    return out


def _strip_span(text: str, start: int, end: int):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Agrupa parágrafos em fragmentos de no máximo ``max_chars`` caracteres.

    Dá-se preferência às quebras de parágrafo. Um parágrafo maior que o limite é
    dividido nas frases e, se uma frase ainda for maior, nos espaços.
    """
    if not isinstance(text, str):
        raise TypeError("chunk_text exige str")
    if max_chars < MIN_MAX_CHARS:
        raise ValueError(f"max_chars deve ser de pelo menos {MIN_MAX_CHARS}")

    units = []
    for p_start, p_end in _paragraph_spans(text):
        if p_end - p_start <= max_chars:
            units.append((p_start, p_end))
        else:
            units.extend(_split_long(text, p_start, p_end, max_chars))

    chunks: list[Chunk] = []
    cur_start = cur_end = None
    for u_start, u_end in units:
        if cur_start is None:
            cur_start, cur_end = u_start, u_end
        elif u_end - cur_start <= max_chars:
            cur_end = u_end
        else:
            chunks.append(_make(text, cur_start, cur_end))
            cur_start, cur_end = u_start, u_end
    if cur_start is not None:
        chunks.append(_make(text, cur_start, cur_end))
    return [c for c in chunks if c is not None]


def _make(text: str, start: int, end: int):
    start, end = _strip_span(text, start, end)
    if end <= start:
        return None
    return Chunk(start=start, end=end, text=text[start:end])
