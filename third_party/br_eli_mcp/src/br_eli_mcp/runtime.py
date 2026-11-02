"""Runtime manifest - DISABLED in this hardened fork (see VENDOR.md).

Upstream fetched a JSON manifest from a GitHub Release on first tool call and used
it to replace the eight upstream base URLs, with no signature or hash check. That
let a release change where queries are sent without a new package version. This
fork never fetches the manifest and never reads a cached copy: every base URL is
the one fixed in the client modules, or a validated override (see server.py).
"""

from __future__ import annotations

from typing import Any


def get_runtime() -> dict[str, Any]:
    """Always empty: no network access and no cache read."""
    return {}


def base_url(key: str, default: str) -> str:
    """Kept for compatibility; always returns the default."""
    return default
