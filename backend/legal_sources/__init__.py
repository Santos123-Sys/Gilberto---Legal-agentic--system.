"""Fontes jurídicas externas acessadas somente para leitura."""

from .br_eli_client import ALLOWED_TOOLS, BrEliClient, BrEliError

__all__ = ["ALLOWED_TOOLS", "BrEliClient", "BrEliError"]
