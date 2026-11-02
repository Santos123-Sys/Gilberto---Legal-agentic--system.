"""Deterministic BR contract quotation evidence ledger.

This verifies *presence* in supplied text, not legal validity, truth,
the identity of a signatory or the accuracy of machine OCR.
"""
import hashlib
import re
import unicodedata

MAX_QUOTE_CHARS = 4000


def document_digest(text):
    if not isinstance(text, str):
        raise TypeError("Document must be text")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_for_match(text):
    """Whitespace/Unicode canonicalization only; do not remove negation,
    numbers, accents or punctuation that might change legal meaning."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def verify_contract_quote(document_text, quoted_text):
    """Return deterministic source presence metadata; never self-label legally true.

    Whitespace is normalized, but a single material character change fails.
    Exact source offsets are omitted because PDF/DOCX extraction may alter spacing.
    """
    digest = document_digest(document_text)
    if not isinstance(quoted_text, str) or not quoted_text.strip():
        return {"status": "missing_quote", "document_sha256": digest}
    if len(quoted_text) > MAX_QUOTE_CHARS:
        return {"status": "quote_too_long", "document_sha256": digest}
    needle = normalize_for_match(quoted_text)
    haystack = normalize_for_match(document_text)
    # Avoid misleading fragments from inside a larger identifier/word.
    match = re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack)
    return {
        "status": "present_in_supplied_document" if match else "not_found",
        "document_sha256": digest,
        "quote_sha256": hashlib.sha256(needle.encode("utf-8")).hexdigest(),
        "normalized_position": match.start() if match else None,
        "limitations": "Extraction/text-match only; not legal authority or OCR certification",
    }


def assess_quoted_evidence(document_text, items):
    """Only check passages explicitly flagged as CONTRACT_QUOTE, not legal citations."""
    if not isinstance(items, list):
        raise TypeError("Evidence items must be a list")
    result = []
    for item in items[:50]:
        if not isinstance(item, dict):
            result.append({"status": "invalid_evidence_item"})
            continue
        if item.get("kind") == "contract_quote":
            result.append(verify_contract_quote(document_text, item.get("quote", "")))
        else:
            result.append({"status": "not_contract_quote",
                           "kind": str(item.get("kind", "unknown"))[:40]})
    return result
