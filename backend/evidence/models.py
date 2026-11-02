"""Versioned evidence contracts (schema version 1).

Design rules enforced at the database level, not only in Python:

* Every tenant-scoped row carries ``tenant_id`` and references its parent
  through a composite ``(tenant_id, id)`` foreign key, so a row can never be
  linked to a parent owned by another tenant.
* Evidence that verified claims may rely on is protected by
  ``ON DELETE RESTRICT``.
* An evidence span points at exactly one immutable origin: a document
  version or a legal-source version.

Immutability of versions, pages, spans, review decisions and audit events
is enforced by an ORM guard (``guard_immutable_rows``) and by the
repository, which exposes no update operation for them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKeyConstraint, Integer, MetaData, String,
    Text, UniqueConstraint, event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

SCHEMA_VERSION = 1

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


ID = String(36)
SHA = String(64)
TS = DateTime(timezone=True)


def _tenant_fk(columns, table):
    """Composite (tenant_id, <fk>) -> (<table>.tenant_id, <table>.id)."""
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{table}.tenant_id", f"{table}.id"],
        ondelete="RESTRICT",
    )


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class TenantMembership(Base):
    """Server-side mapping from an authenticated principal to its tenants.

    The tenant used for any operation is derived from this table and the
    verified (issuer, subject) pair. A client-supplied tenant id is only a
    selector among the principal's own memberships.
    """
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "issuer", "subject"),
        CheckConstraint("role IN ('member','reviewer','admin')", name="role"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ID, index=True)
    issuer: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), default="member")
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class _TenantScoped:
    """Mixin: (tenant_id, id) is unique so children can reference both."""
    id: Mapped[str] = mapped_column(ID, primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ID, index=True)
    created_at: Mapped[datetime] = mapped_column(TS, default=utcnow)


class Matter(_TenantScoped, Base):
    __tablename__ = "matters"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    title: Mapped[str] = mapped_column(String(300))


class Document(_TenantScoped, Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), _tenant_fk(["matter_id"], "matters"))
    matter_id: Mapped[str] = mapped_column(ID)
    title: Mapped[str] = mapped_column(String(300))


class DocumentVersion(_TenantScoped, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "document_id", "version_number"),
        # Idempotent ingestion: identical bytes for one document are one version.
        UniqueConstraint("tenant_id", "document_id", "content_sha256"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("byte_size >= 0", name="size_non_negative"),
        _tenant_fk(["document_id"], "documents"),
    )
    document_id: Mapped[str] = mapped_column(ID)
    version_number: Mapped[int] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(SHA)
    media_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(200))
    extraction_version: Mapped[str] = mapped_column(String(64))


class Page(_TenantScoped, Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "document_version_id", "page_number"),
        CheckConstraint("page_number >= 1", name="page_positive"),
        _tenant_fk(["document_version_id"], "document_versions"),
    )
    document_version_id: Mapped[str] = mapped_column(ID)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    text_sha256: Mapped[str] = mapped_column(SHA)


class TextBlock(_TenantScoped, Base):
    __tablename__ = "text_blocks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "page_id", "block_index"),
        CheckConstraint("start_offset >= 0 AND end_offset >= start_offset", name="offsets"),
        _tenant_fk(["page_id"], "pages"),
    )
    page_id: Mapped[str] = mapped_column(ID)
    block_index: Mapped[int] = mapped_column(Integer)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)


class Clause(_TenantScoped, Base):
    __tablename__ = "clauses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("start_page >= 1 AND end_page >= start_page", name="pages"),
        _tenant_fk(["document_version_id"], "document_versions"),
    )
    document_version_id: Mapped[str] = mapped_column(ID)
    label: Mapped[str] = mapped_column(String(100))
    heading: Mapped[str] = mapped_column(String(500), default="")
    start_page: Mapped[int] = mapped_column(Integer)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_page: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)


class DocumentTable(_TenantScoped, Base):
    __tablename__ = "document_tables"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "page_id", "table_index"),
        _tenant_fk(["page_id"], "pages"),
    )
    page_id: Mapped[str] = mapped_column(ID)
    table_index: Mapped[int] = mapped_column(Integer)
    cells_json: Mapped[str] = mapped_column(Text)


class LegalSource(_TenantScoped, Base):
    __tablename__ = "legal_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "source_type", "identifier"),
        CheckConstraint("source_type IN ('statute','precedent','regulation','other')",
                        name="source_type"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    source_type: Mapped[str] = mapped_column(String(20))
    authority: Mapped[str] = mapped_column(String(200))
    identifier: Mapped[str] = mapped_column(String(300))
    title: Mapped[str] = mapped_column(String(500), default="")
    official_url: Mapped[str] = mapped_column(String(1000), default="")


class SourceVersion(_TenantScoped, Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "legal_source_id", "content_sha256"),
        _tenant_fk(["legal_source_id"], "legal_sources"),
    )
    legal_source_id: Mapped[str] = mapped_column(ID)
    version_label: Mapped[str] = mapped_column(String(200))
    content_sha256: Mapped[str] = mapped_column(SHA)
    text: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(TS, default=utcnow)
    effective_from: Mapped[str] = mapped_column(String(10), default="")
    effective_to: Mapped[str] = mapped_column(String(10), default="")


class EvidenceSpan(_TenantScoped, Base):
    __tablename__ = "evidence_spans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "(document_version_id IS NOT NULL AND source_version_id IS NULL "
            "AND page_number IS NOT NULL) OR "
            "(document_version_id IS NULL AND source_version_id IS NOT NULL "
            "AND page_number IS NULL)", name="single_origin"),
        CheckConstraint("start_offset >= 0 AND end_offset > start_offset", name="offsets"),
        _tenant_fk(["document_version_id"], "document_versions"),
        _tenant_fk(["source_version_id"], "source_versions"),
    )
    document_version_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_version_id: Mapped[str | None] = mapped_column(ID, nullable=True)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    quoted_text: Mapped[str] = mapped_column(Text)
    quoted_sha256: Mapped[str] = mapped_column(SHA)
    origin_sha256: Mapped[str] = mapped_column(SHA)
    extraction_version: Mapped[str] = mapped_column(String(64))


CLAIM_STATUSES = ("unverified", "insufficient_evidence", "verified", "rejected")


class LegalClaim(_TenantScoped, Base):
    __tablename__ = "legal_claims"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("claim_type IN ('fact','interpretation','conclusion')",
                        name="claim_type"),
        CheckConstraint("status IN ('unverified','insufficient_evidence','verified','rejected')",
                        name="status"),
        # A claim cannot be stored as verified without the approving decision.
        # (The decision's validity is re-checked by
        # EvidenceRepository.claim_verification_is_valid; a database foreign
        # key here would be circular with review_decisions.)
        CheckConstraint("status <> 'verified' OR verified_by_decision_id IS NOT NULL",
                        name="verified_requires_decision"),
        _tenant_fk(["matter_id"], "matters"),
    )
    matter_id: Mapped[str] = mapped_column(ID)
    statement: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="unverified")
    verified_by_decision_id: Mapped[str | None] = mapped_column(ID, nullable=True)


class ClaimEvidenceLink(_TenantScoped, Base):
    __tablename__ = "claim_evidence_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "claim_id", "evidence_span_id"),
        CheckConstraint("relation IN ('supports','contradicts','context')", name="relation"),
        _tenant_fk(["claim_id"], "legal_claims"),
        _tenant_fk(["evidence_span_id"], "evidence_spans"),
    )
    claim_id: Mapped[str] = mapped_column(ID)
    evidence_span_id: Mapped[str] = mapped_column(ID)
    relation: Mapped[str] = mapped_column(String(20))


class ReviewDecision(_TenantScoped, Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("decision IN ('approve','reject','correct','reanalyze')",
                        name="decision"),
        CheckConstraint("length(rationale) > 0", name="rationale_required"),
        _tenant_fk(["claim_id"], "legal_claims"),
    )
    claim_id: Mapped[str] = mapped_column(ID)
    reviewer_issuer: Mapped[str] = mapped_column(String(500))
    reviewer_subject: Mapped[str] = mapped_column(String(500))
    decision: Mapped[str] = mapped_column(String(20))
    rationale: Mapped[str] = mapped_column(Text)
    evidence_set_sha256: Mapped[str] = mapped_column(SHA)


class AuditEvent(_TenantScoped, Base):
    """Append-only, hash-chained per tenant (prev_hash -> event_hash)."""
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "sequence"),
        ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
    )
    sequence: Mapped[int] = mapped_column(Integer)
    actor_issuer: Mapped[str] = mapped_column(String(500))
    actor_subject: Mapped[str] = mapped_column(String(500))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(ID)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    prev_hash: Mapped[str] = mapped_column(SHA)
    event_hash: Mapped[str] = mapped_column(SHA)


IMMUTABLE = (DocumentVersion, Page, TextBlock, SourceVersion, EvidenceSpan,
             ReviewDecision, AuditEvent, ClaimEvidenceLink)


class ImmutableRecordError(RuntimeError):
    pass


@event.listens_for(Session, "before_flush")
def guard_immutable_rows(session, _flush_context, _instances):
    """Refuse in-place modification or deletion of immutable evidence rows."""
    for obj in session.dirty:
        if isinstance(obj, IMMUTABLE) and session.is_modified(obj, include_collections=False):
            raise ImmutableRecordError(f"{type(obj).__name__} rows are immutable")
    for obj in session.deleted:
        if isinstance(obj, (DocumentVersion, Page, SourceVersion, EvidenceSpan,
                            ReviewDecision, AuditEvent)):
            raise ImmutableRecordError(f"{type(obj).__name__} rows cannot be deleted")
