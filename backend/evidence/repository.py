"""Tenant-scoped evidence repository with transactional invariants.

Invariants (spec PR-02):

1. The tenant is derived on the server from the authenticated principal's
   memberships. A requested tenant id is only a selector among them.
2. A document version is never overwritten: identical bytes are idempotent,
   different bytes become a new version number.
3. Every evidence span references an existing immutable document version or
   source version, and its quoted text is sliced by the server.
4. A claim becomes verified only through a recorded approval by a reviewer,
   against the exact current evidence set, with at least one supporting span
   whose origin still hashes correctly.
5. Evidence that a verified claim relies on cannot be deleted.
6. All operations are performed inside the caller's transaction, so any
   failure rolls the whole unit back (see ``database.transaction``).

Callers outside a tenant receive ``EvidenceNotFound`` for records that exist
in another tenant, so existence is not disclosed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .models import (
    AuditEvent, ClaimEvidenceLink, Document, DocumentVersion, EvidenceSpan,
    LegalClaim, LegalSource, Matter, Page, ReviewDecision, SourceVersion,
    Tenant, TenantMembership, TextBlock,
)
from .provenance import GENESIS_HASH, canonical_json, chain_hash, is_sha256, sha256_bytes, sha256_json, sha256_text


class EvidenceNotFound(LookupError):
    """Unknown record, or a record owned by another tenant."""


class TenantAccessDenied(EvidenceNotFound):
    pass


class EvidenceIntegrityError(ValueError):
    pass


class VersionConflict(RuntimeError):
    pass


class VerificationRefused(ValueError):
    pass


class StaleReview(VerificationRefused):
    pass


class RoleRequired(PermissionError):
    pass


class DeletionRefused(RuntimeError):
    pass


ROLE_RANK = {"member": 0, "reviewer": 1, "admin": 2}


def _principal_id(principal) -> tuple[str, str]:
    issuer = getattr(principal, "issuer", None)
    subject = getattr(principal, "subject", None)
    if not isinstance(issuer, str) or not issuer or not isinstance(subject, str) or not subject:
        raise TenantAccessDenied("authenticated principal required")
    return issuer, subject


def provision_tenant(session, principal, name: str) -> str:
    """Create a tenant whose first administrator is the given principal."""
    issuer, subject = _principal_id(principal)
    tenant = Tenant(name=name)
    session.add(tenant)
    session.flush()
    session.add(TenantMembership(tenant_id=tenant.id, issuer=issuer, subject=subject, role="admin"))
    session.flush()
    repo = EvidenceRepository(session, tenant.id, issuer, subject, "admin")
    repo._audit("tenant.provisioned", "tenant", tenant.id, {"name": name})
    return tenant.id


def open_repository(session, principal, requested_tenant_id: str | None = None,
                    object_store=None) -> "EvidenceRepository":
    issuer, subject = _principal_id(principal)
    rows = session.execute(
        select(TenantMembership.tenant_id, TenantMembership.role).where(
            TenantMembership.issuer == issuer, TenantMembership.subject == subject)
    ).all()
    memberships = {tenant_id: role for tenant_id, role in rows}
    if requested_tenant_id is not None:
        if requested_tenant_id not in memberships:
            raise TenantAccessDenied("tenant not available")
        tenant_id = requested_tenant_id
    elif len(memberships) == 1:
        tenant_id = next(iter(memberships))
    else:
        raise TenantAccessDenied("tenant selection required")
    return EvidenceRepository(session, tenant_id, issuer, subject,
                              memberships[tenant_id], object_store)


@dataclass
class EvidenceRepository:
    session: object
    tenant_id: str
    actor_issuer: str
    actor_subject: str
    role: str
    object_store: object = None

    # ── helpers ─────────────────────────────────────────────
    def _require_role(self, minimum: str) -> None:
        if ROLE_RANK.get(self.role, -1) < ROLE_RANK[minimum]:
            raise RoleRequired(f"{minimum} role required")

    def get(self, model, record_id: str):
        obj = self.session.execute(
            select(model).where(model.id == record_id, model.tenant_id == self.tenant_id)
        ).scalar_one_or_none()
        if obj is None:
            raise EvidenceNotFound(f"{model.__name__} not found")
        return obj

    def _audit(self, action: str, entity_type: str, entity_id: str, detail: dict) -> AuditEvent:
        last = self.session.execute(
            select(AuditEvent).where(AuditEvent.tenant_id == self.tenant_id)
            .order_by(AuditEvent.sequence.desc()).limit(1)
        ).scalar_one_or_none()
        sequence = 1 if last is None else last.sequence + 1
        prev = GENESIS_HASH if last is None else last.event_hash
        payload = {"sequence": sequence, "actor": [self.actor_issuer, self.actor_subject],
                   "action": action, "entity_type": entity_type, "entity_id": entity_id,
                   "detail": detail}
        event = AuditEvent(tenant_id=self.tenant_id, sequence=sequence,
                           actor_issuer=self.actor_issuer, actor_subject=self.actor_subject,
                           action=action, entity_type=entity_type, entity_id=entity_id,
                           detail_json=canonical_json(detail), prev_hash=prev,
                           event_hash=chain_hash(prev, payload))
        self.session.add(event)
        self.session.flush()
        return event

    def audit_chain_is_intact(self) -> bool:
        events = self.session.execute(
            select(AuditEvent).where(AuditEvent.tenant_id == self.tenant_id)
            .order_by(AuditEvent.sequence)).scalars().all()
        prev = GENESIS_HASH
        for expected_sequence, event in enumerate(events, start=1):
            payload = {"sequence": event.sequence,
                       "actor": [event.actor_issuer, event.actor_subject],
                       "action": event.action, "entity_type": event.entity_type,
                       "entity_id": event.entity_id, "detail": json.loads(event.detail_json)}
            if (event.sequence != expected_sequence or event.prev_hash != prev
                    or event.event_hash != chain_hash(prev, payload)):
                return False
            prev = event.event_hash
        return True

    # ── tenancy administration ──────────────────────────────
    def grant_membership(self, issuer: str, subject: str, role: str) -> TenantMembership:
        self._require_role("admin")
        if role not in ROLE_RANK:
            raise ValueError("unknown role")
        membership = TenantMembership(tenant_id=self.tenant_id, issuer=issuer,
                                      subject=subject, role=role)
        self.session.add(membership)
        self.session.flush()
        self._audit("membership.granted", "tenant_membership", membership.id,
                    {"role": role})
        return membership

    # ── matters and documents ───────────────────────────────
    def create_matter(self, title: str) -> Matter:
        matter = Matter(tenant_id=self.tenant_id, title=title)
        self.session.add(matter)
        self.session.flush()
        self._audit("matter.created", "matter", matter.id, {})
        return matter

    def create_document(self, matter_id: str, title: str) -> Document:
        self.get(Matter, matter_id)
        document = Document(tenant_id=self.tenant_id, matter_id=matter_id, title=title)
        self.session.add(document)
        self.session.flush()
        self._audit("document.created", "document", document.id, {})
        return document

    def ingest_document_version(self, document_id: str, data: bytes, *, media_type: str,
                                pages: list[str], extraction_version: str,
                                expected_sha256: str | None = None):
        """Returns (version, created). Identical bytes are idempotent."""
        self.get(Document, document_id)
        digest = sha256_bytes(data)
        if expected_sha256 is not None and expected_sha256 != digest:
            raise EvidenceIntegrityError("content hash does not match the uploaded bytes")
        if not pages or not all(isinstance(p, str) for p in pages):
            raise EvidenceIntegrityError("at least one extracted page of text is required")
        existing = self.session.execute(
            select(DocumentVersion).where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.document_id == document_id,
                DocumentVersion.content_sha256 == digest)
        ).scalar_one_or_none()
        if existing is not None:
            self._audit("document_version.duplicate_ingestion", "document_version",
                        existing.id, {"content_sha256": digest})
            return existing, False
        key = (self.object_store.put(self.tenant_id, data) if self.object_store is not None
               else f"{self.tenant_id}/{digest}")
        next_number = (self.session.execute(
            select(func.max(DocumentVersion.version_number)).where(
                DocumentVersion.tenant_id == self.tenant_id,
                DocumentVersion.document_id == document_id)
        ).scalar() or 0) + 1
        version = DocumentVersion(tenant_id=self.tenant_id, document_id=document_id,
                                  version_number=next_number, content_sha256=digest,
                                  media_type=media_type, byte_size=len(data),
                                  object_key=key, extraction_version=extraction_version)
        try:
            with self.session.begin_nested():
                self.session.add(version)
                self.session.flush()
                for number, text in enumerate(pages, start=1):
                    self.session.add(Page(tenant_id=self.tenant_id,
                                          document_version_id=version.id,
                                          page_number=number, text=text,
                                          text_sha256=sha256_text(text)))
                self.session.flush()
        except IntegrityError as exc:
            raise VersionConflict("a concurrent ingestion created this version first") from exc
        self._audit("document_version.ingested", "document_version", version.id,
                    {"content_sha256": digest, "version_number": next_number,
                     "pages": len(pages)})
        return version, True

    def page(self, document_version_id: str, page_number: int) -> Page:
        self.get(DocumentVersion, document_version_id)
        page = self.session.execute(
            select(Page).where(Page.tenant_id == self.tenant_id,
                               Page.document_version_id == document_version_id,
                               Page.page_number == page_number)
        ).scalar_one_or_none()
        if page is None:
            raise EvidenceNotFound("page not found")
        return page

    def add_text_block(self, page_id: str, block_index: int, start: int, end: int) -> TextBlock:
        page = self.get(Page, page_id)
        if not 0 <= start <= end <= len(page.text):
            raise EvidenceIntegrityError("text block offsets fall outside the page")
        block = TextBlock(tenant_id=self.tenant_id, page_id=page_id, block_index=block_index,
                          start_offset=start, end_offset=end)
        self.session.add(block)
        self.session.flush()
        return block

    # ── legal sources ───────────────────────────────────────
    def register_legal_source(self, *, source_type: str, authority: str, identifier: str,
                              title: str = "", official_url: str = "") -> LegalSource:
        existing = self.session.execute(
            select(LegalSource).where(LegalSource.tenant_id == self.tenant_id,
                                      LegalSource.source_type == source_type,
                                      LegalSource.identifier == identifier)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        source = LegalSource(tenant_id=self.tenant_id, source_type=source_type,
                             authority=authority, identifier=identifier, title=title,
                             official_url=official_url)
        self.session.add(source)
        self.session.flush()
        self._audit("legal_source.registered", "legal_source", source.id,
                    {"source_type": source_type, "identifier": identifier})
        return source

    def add_source_version(self, legal_source_id: str, text: str, *, version_label: str,
                           effective_from: str = "", effective_to: str = "",
                           expected_sha256: str | None = None) -> SourceVersion:
        self.get(LegalSource, legal_source_id)
        digest = sha256_text(text)
        if expected_sha256 is not None and expected_sha256 != digest:
            raise EvidenceIntegrityError("source text does not match its declared hash")
        existing = self.session.execute(
            select(SourceVersion).where(SourceVersion.tenant_id == self.tenant_id,
                                        SourceVersion.legal_source_id == legal_source_id,
                                        SourceVersion.content_sha256 == digest)
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        version = SourceVersion(tenant_id=self.tenant_id, legal_source_id=legal_source_id,
                                version_label=version_label, content_sha256=digest, text=text,
                                effective_from=effective_from, effective_to=effective_to)
        self.session.add(version)
        self.session.flush()
        self._audit("source_version.added", "source_version", version.id,
                    {"content_sha256": digest})
        return version

    def delete_legal_source(self, legal_source_id: str) -> None:
        source = self.get(LegalSource, legal_source_id)
        has_versions = self.session.execute(
            select(func.count()).select_from(SourceVersion).where(
                SourceVersion.tenant_id == self.tenant_id,
                SourceVersion.legal_source_id == legal_source_id)
        ).scalar()
        if has_versions:
            raise DeletionRefused("source versions are immutable evidence and cannot be deleted")
        self.session.delete(source)
        self.session.flush()
        self._audit("legal_source.deleted", "legal_source", legal_source_id, {})

    # ── evidence spans ──────────────────────────────────────
    @staticmethod
    def _slice(text: str, start: int, end: int, expected_quote: str | None) -> str:
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text)):
            raise EvidenceIntegrityError("span offsets fall outside the origin text")
        quoted = text[start:end]
        if expected_quote is not None and expected_quote != quoted:
            raise EvidenceIntegrityError("quoted text does not appear at the stated offsets")
        return quoted

    def add_document_span(self, document_version_id: str, page_number: int, start: int, end: int,
                          *, expected_quote: str | None = None) -> EvidenceSpan:
        version = self.get(DocumentVersion, document_version_id)
        page = self.page(document_version_id, page_number)
        quoted = self._slice(page.text, start, end, expected_quote)
        span = EvidenceSpan(tenant_id=self.tenant_id, document_version_id=version.id,
                            page_number=page_number, start_offset=start, end_offset=end,
                            quoted_text=quoted, quoted_sha256=sha256_text(quoted),
                            origin_sha256=page.text_sha256,
                            extraction_version=version.extraction_version)
        self.session.add(span)
        self.session.flush()
        self._audit("evidence_span.added", "evidence_span", span.id,
                    {"origin": "document", "quoted_sha256": span.quoted_sha256})
        return span

    def add_source_span(self, source_version_id: str, start: int, end: int,
                        *, expected_quote: str | None = None) -> EvidenceSpan:
        version = self.get(SourceVersion, source_version_id)
        quoted = self._slice(version.text, start, end, expected_quote)
        span = EvidenceSpan(tenant_id=self.tenant_id, source_version_id=version.id,
                            start_offset=start, end_offset=end, quoted_text=quoted,
                            quoted_sha256=sha256_text(quoted),
                            origin_sha256=version.content_sha256,
                            extraction_version="source-text-v1")
        self.session.add(span)
        self.session.flush()
        self._audit("evidence_span.added", "evidence_span", span.id,
                    {"origin": "source", "quoted_sha256": span.quoted_sha256})
        return span

    def span_is_intact(self, span: EvidenceSpan) -> bool:
        if span.document_version_id is not None:
            origin = self.page(span.document_version_id, span.page_number)
            text, digest = origin.text, origin.text_sha256
        else:
            origin = self.get(SourceVersion, span.source_version_id)
            text, digest = origin.text, origin.content_sha256
        return (is_sha256(digest) and sha256_text(text) == digest == span.origin_sha256
                and text[span.start_offset:span.end_offset] == span.quoted_text
                and sha256_text(span.quoted_text) == span.quoted_sha256)

    # ── claims and verification ─────────────────────────────
    def create_claim(self, matter_id: str, statement: str, claim_type: str) -> LegalClaim:
        self.get(Matter, matter_id)
        claim = LegalClaim(tenant_id=self.tenant_id, matter_id=matter_id,
                           statement=statement, claim_type=claim_type)
        self.session.add(claim)
        self.session.flush()
        self._audit("claim.created", "legal_claim", claim.id, {"claim_type": claim_type})
        return claim

    def link_evidence(self, claim_id: str, span_id: str, relation: str) -> ClaimEvidenceLink:
        claim = self.get(LegalClaim, claim_id)
        self.get(EvidenceSpan, span_id)
        if claim.status == "verified":
            raise VerificationRefused("evidence of a verified claim cannot change; "
                                      "record a new review instead")
        link = ClaimEvidenceLink(tenant_id=self.tenant_id, claim_id=claim_id,
                                 evidence_span_id=span_id, relation=relation)
        self.session.add(link)
        self.session.flush()
        self._audit("claim.evidence_linked", "legal_claim", claim_id,
                    {"span": span_id, "relation": relation})
        return link

    def _links(self, claim_id: str):
        return self.session.execute(
            select(ClaimEvidenceLink, EvidenceSpan)
            .join(EvidenceSpan, (EvidenceSpan.id == ClaimEvidenceLink.evidence_span_id)
                  & (EvidenceSpan.tenant_id == ClaimEvidenceLink.tenant_id))
            .where(ClaimEvidenceLink.tenant_id == self.tenant_id,
                   ClaimEvidenceLink.claim_id == claim_id)
        ).all()

    def evidence_set_sha256(self, claim_id: str) -> str:
        self.get(LegalClaim, claim_id)
        entries = sorted(
            [link.evidence_span_id, link.relation, span.quoted_sha256, span.origin_sha256]
            for link, span in self._links(claim_id))
        return sha256_json(entries)

    def record_review(self, claim_id: str, *, decision: str, rationale: str,
                      evidence_set_sha256: str) -> ReviewDecision:
        """The only way a claim's status changes after creation."""
        self._require_role("reviewer")
        claim = self.get(LegalClaim, claim_id)
        if not isinstance(rationale, str) or not rationale.strip():
            raise VerificationRefused("a review rationale is required")
        if evidence_set_sha256 != self.evidence_set_sha256(claim_id):
            raise StaleReview("the evidence changed after it was reviewed")
        if decision == "approve":
            supporting = [span for link, span in self._links(claim_id)
                          if link.relation == "supports"]
            if not supporting:
                raise VerificationRefused("no supporting evidence is linked")
            if not all(self.span_is_intact(span) for span in supporting):
                raise VerificationRefused("supporting evidence no longer matches its origin")
        review = ReviewDecision(tenant_id=self.tenant_id, claim_id=claim_id,
                                reviewer_issuer=self.actor_issuer,
                                reviewer_subject=self.actor_subject, decision=decision,
                                rationale=rationale, evidence_set_sha256=evidence_set_sha256)
        self.session.add(review)
        self.session.flush()
        claim.status = {"approve": "verified", "reject": "rejected"}.get(decision, "unverified")
        claim.verified_by_decision_id = review.id if decision == "approve" else None
        self.session.flush()
        self._audit("claim.reviewed", "legal_claim", claim_id,
                    {"decision": decision, "review": review.id})
        return review

    def mark_insufficient_evidence(self, claim_id: str) -> LegalClaim:
        claim = self.get(LegalClaim, claim_id)
        if claim.status == "verified":
            raise VerificationRefused("a verified claim changes only through a new review")
        claim.status = "insufficient_evidence"
        self.session.flush()
        self._audit("claim.insufficient_evidence", "legal_claim", claim_id, {})
        return claim

    def claim_verification_is_valid(self, claim_id: str) -> bool:
        """Re-checks a verified claim against its approving review and evidence."""
        claim = self.get(LegalClaim, claim_id)
        if claim.status != "verified" or not claim.verified_by_decision_id:
            return False
        review = self.get(ReviewDecision, claim.verified_by_decision_id)
        return (review.claim_id == claim_id and review.decision == "approve"
                and review.evidence_set_sha256 == self.evidence_set_sha256(claim_id)
                and all(self.span_is_intact(span) for link, span in self._links(claim_id)
                        if link.relation == "supports"))
