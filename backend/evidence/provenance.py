"""Deterministic hashing used to bind evidence to exact bytes and text."""
from __future__ import annotations

import hashlib
import json
import re

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def sha256_bytes(data: bytes) -> str:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("sha256_bytes requires bytes")
    return hashlib.sha256(bytes(data)).hexdigest()


def sha256_text(text: str) -> str:
    """Hash text exactly as stored. No normalization: changing one character
    (for example a decimal separator or a negation) changes the hash."""
    if not isinstance(text, str):
        raise TypeError("sha256_text requires str")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value) -> str:
    return sha256_text(canonical_json(value))


def is_sha256(value) -> bool:
    return isinstance(value, str) and bool(_SHA256.match(value))


def chain_hash(prev_hash: str, payload: dict) -> str:
    """Hash of an audit event linked to its predecessor."""
    return sha256_text(prev_hash + "\n" + canonical_json(payload))


GENESIS_HASH = "0" * 64
