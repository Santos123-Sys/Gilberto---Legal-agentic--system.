"""Normalização e tokenização de texto para a recuperação jurídica em português do Brasil.

A normalização remove acentos e diferenças de caixa, de modo que "cláusula penal",
"Clausula Penal" e "CLÁUSULA PENAL" produzam os mesmos termos. É apenas um recurso
de correspondência: nunca altera o texto armazenado, citado ou comparado por hash.
"""
from __future__ import annotations

import re
import unicodedata

# Lista propositalmente curta. Remover stopwords em excesso eliminaria termos como
# "não" (negação), que mudam o sentido jurídico; por isso as negações são mantidas.
STOPWORDS = frozenset({
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na", "no",
    "nas", "nos", "um", "uma", "uns", "umas", "que", "para", "por", "com", "ou",
    "se", "ao", "aos", "ser", "sao", "pelo", "pela",
})
# Observação: as stopwords são comparadas após a normalização, por isso formas
# acentuadas não precisam de entradas próprias.

_TOKEN = re.compile(r"[0-9a-z]+")


def fold(text: str) -> str:
    """Converte em minúsculas e remove marcas de combinação (NFKD).

    O comprimento pode mudar; use apenas para correspondência.
    """
    if not isinstance(text, str):
        raise TypeError("fold exige str")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


def tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN.findall(fold(text)) if tok not in STOPWORDS]
