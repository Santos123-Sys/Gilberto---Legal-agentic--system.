"""Canonical legal-evidence persistence (PR-02, ADR-001).

This package is deliberately not wired into the request path yet. ADR-001
requires a staged migration: the existing SQLite session checkpoints remain
authoritative until compatibility, backup, restore and tenant-isolation
gates pass for the evidence store.

The package lives in ``backend/evidence`` rather than ``backend/data``
because ``backend/data/`` is git-ignored and is the default runtime
location of the session checkpoint database.
"""
