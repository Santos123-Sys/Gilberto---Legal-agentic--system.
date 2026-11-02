"""Fail-closed resource owner policy, independent of untrusted request fields.

This policy is intentionally not wired to routes until backend and frontend
can validate an OIDC principal end-to-end. Legacy unowned checkpoints are
quarantined, not silently assigned to the first user to present their UUID.
"""
from collections.abc import Mapping
from security.oidc import Principal


class AccessDenied(Exception):
    """Do not disclose which principal owns a confidential resource."""


def require_session_owner(principal: Principal, session: Mapping) -> None:
    if not isinstance(principal, Principal) or not isinstance(session, Mapping):
        raise AccessDenied("Resource unavailable")
    owner_issuer = session.get("owner_issuer")
    owner_subject = session.get("owner_subject")
    if (not isinstance(owner_issuer, str) or not owner_issuer or
            not isinstance(owner_subject, str) or not owner_subject):
        # Pre-authentication legacy sessions are NOT claimable by UUID.
        raise AccessDenied("Resource unavailable")
    if (owner_issuer, owner_subject) != principal.stable_id:
        raise AccessDenied("Resource unavailable")
