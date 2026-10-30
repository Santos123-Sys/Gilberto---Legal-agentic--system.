"""PR-02 evidence-store tests. Synthetic data only; no client documents.

Every test runs the real Alembic migration (not metadata.create_all), on
SQLite always and on PostgreSQL when EVIDENCE_TEST_DATABASE_URL is set.
CI sets EVIDENCE_REQUIRE_POSTGRES_TESTS so the PostgreSQL run cannot be
skipped silently.
"""
import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from evidence import database
from evidence.database import (
    SchemaVersionMismatch, make_engine, make_session_factory, require_current_schema,
    transaction,
)
from evidence.models import (
    AuditEvent, Base, ClaimEvidenceLink, DocumentVersion, EvidenceSpan, ImmutableRecordError,
    Matter, Page,
)
from evidence.object_store import (
    LocalPrivateObjectStore, ObjectAccessDenied, ObjectIntegrityError, ObjectKeyError,
    object_key,
)
from evidence.provenance import sha256_bytes
from evidence.repository import (
    DeletionRefused, EvidenceIntegrityError, EvidenceNotFound, RoleRequired, StaleReview,
    TenantAccessDenied, VerificationRefused, open_repository, provision_tenant,
)
from security.oidc import Principal

IDP = "https://idp.example.test"
LAWYER_A = Principal(IDP, "lawyer-a")
LAWYER_B = Principal(IDP, "lawyer-b")
REVIEWER_A = Principal(IDP, "reviewer-a")

PAGE_1 = ("CLÁUSULA 5 - MULTA. Em caso de atraso, a multa será de 2% (dois por cento) "
          "ao mês, não cumulativa com juros.")
PAGE_2 = "CLÁUSULA 9 - FORO. Fica eleito o foro da Comarca do Rio de Janeiro."
STATUTE = ("Art. 412. O valor da cominação imposta na cláusula penal não pode exceder "
           "o da obrigação principal.")
QUOTE = "a multa será de 2% (dois por cento)"


class EvidenceStoreContract:
    """Shared tests; subclasses supply a database URL."""

    def database_url(self):  # pragma: no cover - overridden
        raise NotImplementedError

    def setUp(self):
        self.url = self.database_url()
        database.downgrade(self.url, "base")
        database.upgrade(self.url)
        self.engine = make_engine(self.url)
        self.addCleanup(self.engine.dispose)
        self.factory = make_session_factory(self.engine)
        with transaction(self.factory) as s:
            self.tenant_a = provision_tenant(s, LAWYER_A, "Synthetic firm A")
            self.tenant_b = provision_tenant(s, LAWYER_B, "Synthetic firm B")
            open_repository(s, LAWYER_A).grant_membership(IDP, "reviewer-a", "reviewer")

    # ── fixtures ───────────────────────────────────────────
    def scenario(self, principal=LAWYER_A):
        """A matter, a two-page document version, a statute version and spans."""
        with transaction(self.factory) as s:
            repo = open_repository(s, principal)
            matter = repo.create_matter("Synthetic supply contract")
            document = repo.create_document(matter.id, "Contrato sintético")
            version, created = repo.ingest_document_version(
                document.id, b"%PDF synthetic bytes v1", media_type="application/pdf",
                pages=[PAGE_1, PAGE_2], extraction_version="native-text-v1")
            source = repo.register_legal_source(source_type="statute", authority="Planalto",
                                                identifier="Lei 10.406/2002 art. 412")
            source_version = repo.add_source_version(source.id, STATUTE,
                                                     version_label="texto compilado")
            start = PAGE_1.index(QUOTE)
            doc_span = repo.add_document_span(version.id, 1, start, start + len(QUOTE),
                                              expected_quote=QUOTE)
            src_span = repo.add_source_span(source_version.id, 0, len(STATUTE))
            claim = repo.create_claim(matter.id, "A multa moratória é de 2% ao mês.", "fact")
            repo.link_evidence(claim.id, doc_span.id, "supports")
            return dict(matter=matter.id, document=document.id, version=version.id,
                        created=created, source=source.id, source_version=source_version.id,
                        doc_span=doc_span.id, src_span=src_span.id, claim=claim.id)

    def approve(self, claim_id, principal=REVIEWER_A, rationale="Checked clause 5 on page 1"):
        with transaction(self.factory) as s:
            repo = open_repository(s, principal, self.tenant_a)
            return repo.record_review(claim_id, decision="approve", rationale=rationale,
                                      evidence_set_sha256=repo.evidence_set_sha256(claim_id))

    # ── tenant isolation ───────────────────────────────────
    def test_cross_tenant_reads_are_indistinguishable_from_missing(self):
        ids = self.scenario()
        with transaction(self.factory) as s:
            repo_b = open_repository(s, LAWYER_B)
            for model, key in ((Matter, "matter"), (DocumentVersion, "version")):
                with self.subTest(model=model.__name__):
                    with self.assertRaises(EvidenceNotFound):
                        repo_b.get(model, ids[key])
            with self.assertRaises(EvidenceNotFound):
                repo_b.page(ids["version"], 1)
            with self.assertRaises(EvidenceNotFound):
                repo_b.evidence_set_sha256(ids["claim"])

    def test_client_tenant_selector_cannot_grant_access(self):
        with transaction(self.factory) as s:
            with self.assertRaises(TenantAccessDenied):
                open_repository(s, LAWYER_B, requested_tenant_id=self.tenant_a)
            with self.assertRaises(TenantAccessDenied):
                open_repository(s, Principal(IDP, "stranger"))
            with self.assertRaises(TenantAccessDenied):
                open_repository(s, Principal("", ""))
            repo = open_repository(s, LAWYER_A, requested_tenant_id=self.tenant_a)
            self.assertEqual(repo.tenant_id, self.tenant_a)

    def test_principal_with_several_tenants_must_select_one_of_its_own(self):
        with transaction(self.factory) as s:
            open_repository(s, LAWYER_B).grant_membership(IDP, "lawyer-a", "member")
        with transaction(self.factory) as s:
            with self.assertRaises(TenantAccessDenied):
                open_repository(s, LAWYER_A)
            self.assertEqual(open_repository(s, LAWYER_A, self.tenant_b).role, "member")

    def test_cross_tenant_link_is_rejected_by_the_repository_and_the_database(self):
        ids_a = self.scenario(LAWYER_A)
        ids_b = self.scenario(LAWYER_B)
        with transaction(self.factory) as s:
            with self.assertRaises(EvidenceNotFound):
                open_repository(s, LAWYER_B).link_evidence(ids_b["claim"], ids_a["doc_span"],
                                                           "supports")
        # Bypassing the repository: the composite (tenant_id, id) foreign key
        # still refuses a tenant-B link to a tenant-A span.
        with self.assertRaises(IntegrityError):
            with transaction(self.factory) as s:
                s.add(ClaimEvidenceLink(tenant_id=self.tenant_b, claim_id=ids_b["claim"],
                                        evidence_span_id=ids_a["doc_span"],
                                        relation="supports"))

    # ── document versions ──────────────────────────────────
    def test_duplicate_ingestion_is_idempotent_and_versions_never_overwrite(self):
        ids = self.scenario()
        self.assertTrue(ids["created"])
        with transaction(self.factory) as s:
            repo = open_repository(s, LAWYER_A)
            again, created = repo.ingest_document_version(
                ids["document"], b"%PDF synthetic bytes v1", media_type="application/pdf",
                pages=[PAGE_1, PAGE_2], extraction_version="native-text-v1")
            self.assertFalse(created)
            self.assertEqual(again.id, ids["version"])
            second, created = repo.ingest_document_version(
                ids["document"], b"%PDF synthetic bytes v2", media_type="application/pdf",
                pages=[PAGE_1.replace("2%", "3%")], extraction_version="native-text-v1")
            self.assertTrue(created)
            self.assertEqual(second.version_number, 2)
        with transaction(self.factory) as s:
            count = s.execute(select(func.count()).select_from(DocumentVersion)).scalar()
            self.assertEqual(count, 2)
            original = s.get(DocumentVersion, ids["version"])
            self.assertEqual(original.content_sha256, sha256_bytes(b"%PDF synthetic bytes v1"))

    def test_same_bytes_in_another_tenant_are_a_separate_version(self):
        ids_a = self.scenario(LAWYER_A)
        ids_b = self.scenario(LAWYER_B)
        self.assertNotEqual(ids_a["version"], ids_b["version"])
        self.assertTrue(ids_b["created"])

    def test_versions_and_pages_are_immutable(self):
        ids = self.scenario()
        for mutate in (lambda s: setattr(s.get(DocumentVersion, ids["version"]),
                                         "content_sha256", "0" * 64),
                       lambda s: setattr(s.execute(select(Page)).scalars().first(),
                                         "text", "altered"),
                       lambda s: s.delete(s.get(DocumentVersion, ids["version"]))):
            with self.assertRaises(ImmutableRecordError):
                with transaction(self.factory) as s:
                    mutate(s)

    def test_duplicate_version_number_is_rejected_by_the_database(self):
        ids = self.scenario()
        with self.assertRaises(IntegrityError):
            with transaction(self.factory) as s:
                s.add(DocumentVersion(tenant_id=self.tenant_a, document_id=ids["document"],
                                      version_number=1, content_sha256="f" * 64,
                                      media_type="application/pdf", byte_size=1,
                                      object_key="k", extraction_version="x"))

    # ── provenance and integrity ───────────────────────────
    def test_content_hash_mismatch_and_misquoted_evidence_are_rejected(self):
        ids = self.scenario()
        with transaction(self.factory) as s:
            repo = open_repository(s, LAWYER_A)
            with self.assertRaises(EvidenceIntegrityError):
                repo.ingest_document_version(ids["document"], b"other bytes",
                                             media_type="application/pdf", pages=[PAGE_1],
                                             extraction_version="x",
                                             expected_sha256=sha256_bytes(b"declared bytes"))
            start = PAGE_1.index(QUOTE)
            # The agent "quotes" 20% where the document says 2%.
            with self.assertRaises(EvidenceIntegrityError):
                repo.add_document_span(ids["version"], 1, start, start + len(QUOTE),
                                       expected_quote=QUOTE.replace("2%", "20%"))
            with self.assertRaises(EvidenceIntegrityError):
                repo.add_document_span(ids["version"], 1, 0, len(PAGE_1) + 5)
            with self.assertRaises(EvidenceNotFound):
                repo.add_document_span(ids["version"], 7, 0, 3)
            with self.assertRaises(EvidenceIntegrityError):
                repo.add_source_version(ids["source"], STATUTE + " ",
                                        version_label="x",
                                        expected_sha256=sha256_bytes(STATUTE.encode()))

    def test_tampered_origin_text_invalidates_evidence_and_blocks_verification(self):
        ids = self.scenario()
        with self.engine.begin() as conn:  # out-of-band tampering, bypassing the ORM
            conn.execute(text("UPDATE pages SET text = :t WHERE document_version_id = :v "
                              "AND page_number = 1"),
                         {"t": PAGE_1.replace("2%", "20%"), "v": ids["version"]})
        with transaction(self.factory) as s:
            repo = open_repository(s, REVIEWER_A, self.tenant_a)
            self.assertFalse(repo.span_is_intact(repo.get(EvidenceSpan, ids["doc_span"])))
            with self.assertRaises(VerificationRefused):
                repo.record_review(ids["claim"], decision="approve", rationale="Looks right",
                                   evidence_set_sha256=repo.evidence_set_sha256(ids["claim"]))

    def test_broken_foreign_keys_are_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction(self.factory) as s:
                s.add(EvidenceSpan(tenant_id=self.tenant_a,
                                   document_version_id="00000000-0000-4000-8000-000000000000",
                                   page_number=1, start_offset=0, end_offset=1, quoted_text="x",
                                   quoted_sha256="a" * 64, origin_sha256="a" * 64,
                                   extraction_version="x"))

    def test_span_must_have_exactly_one_origin(self):
        ids = self.scenario()
        with self.assertRaises(IntegrityError):
            with transaction(self.factory) as s:
                s.add(EvidenceSpan(tenant_id=self.tenant_a, document_version_id=ids["version"],
                                   page_number=1, source_version_id=ids["source_version"],
                                   start_offset=0, end_offset=1, quoted_text="C",
                                   quoted_sha256="a" * 64, origin_sha256="a" * 64,
                                   extraction_version="x"))

    # ── verification invariants ────────────────────────────
    def test_claim_is_verified_only_by_a_reviewer_against_current_evidence(self):
        ids = self.scenario()
        with transaction(self.factory) as s:
            open_repository(s, LAWYER_A).grant_membership(IDP, "paralegal-a", "member")
        with transaction(self.factory) as s:
            paralegal = open_repository(s, Principal(IDP, "paralegal-a"))
            with self.assertRaises(RoleRequired):
                paralegal.record_review(ids["claim"], decision="approve", rationale="ok",
                                        evidence_set_sha256=paralegal.evidence_set_sha256(
                                            ids["claim"]))
        with transaction(self.factory) as s:
            reviewer = open_repository(s, REVIEWER_A, self.tenant_a)
            with self.assertRaises(VerificationRefused):
                reviewer.record_review(ids["claim"], decision="approve", rationale="   ",
                                       evidence_set_sha256=reviewer.evidence_set_sha256(
                                           ids["claim"]))
            with self.assertRaises(StaleReview):
                reviewer.record_review(ids["claim"], decision="approve", rationale="ok",
                                       evidence_set_sha256="0" * 64)
        review = self.approve(ids["claim"])
        with transaction(self.factory) as s:
            repo = open_repository(s, LAWYER_A)
            self.assertTrue(repo.claim_verification_is_valid(ids["claim"]))
            with self.assertRaises(VerificationRefused):
                repo.link_evidence(ids["claim"], ids["src_span"], "contradicts")
            with self.assertRaises(VerificationRefused):
                repo.mark_insufficient_evidence(ids["claim"])
        self.assertEqual(review.reviewer_subject, "reviewer-a")

    def test_claim_without_supporting_evidence_cannot_be_verified(self):
        ids = self.scenario()
        with transaction(self.factory) as s:
            repo = open_repository(s, LAWYER_A)
            bare = repo.create_claim(ids["matter"], "Unsupported proposition", "conclusion")
            repo.link_evidence(bare.id, ids["src_span"], "context")
            bare_id = bare.id
        with self.assertRaises(VerificationRefused):
            self.approve(bare_id)

    def test_database_refuses_verified_status_without_a_decision(self):
        ids = self.scenario()
        with self.assertRaises(IntegrityError):
            with self.engine.begin() as conn:
                conn.execute(text("UPDATE legal_claims SET status = 'verified' WHERE id = :c"),
                             {"c": ids["claim"]})

    # ── deletion ───────────────────────────────────────────
    def test_evidence_behind_a_verified_claim_cannot_be_deleted(self):
        ids = self.scenario()
        with transaction(self.factory) as s:
            repo = open_repository(s, LAWYER_A)
            linked = repo.create_claim(ids["matter"], "Cláusula penal limitada", "interpretation")
            repo.link_evidence(linked.id, ids["src_span"], "supports")
            linked_id = linked.id
        self.approve(linked_id)
        with transaction(self.factory) as s:
            with self.assertRaises(DeletionRefused):
                open_repository(s, LAWYER_A).delete_legal_source(ids["source"])
        for statement in ("DELETE FROM source_versions WHERE id = :i",
                          "DELETE FROM legal_sources WHERE id = :s"):
            with self.subTest(statement=statement):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as conn:
                        conn.execute(text(statement), {"i": ids["source_version"],
                                                       "s": ids["source"]})
        with transaction(self.factory) as s:
            self.assertTrue(open_repository(s, LAWYER_A).claim_verification_is_valid(linked_id))

    def test_unused_source_without_versions_can_be_deleted(self):
        with transaction(self.factory) as s:
            repo = open_repository(s, LAWYER_A)
            source = repo.register_legal_source(source_type="precedent", authority="STJ",
                                                identifier="synthetic-unused")
            repo.delete_legal_source(source.id)

    # ── transactions and audit ─────────────────────────────
    def test_failed_transaction_leaves_no_partial_state(self):
        with self.assertRaises(RuntimeError):
            with transaction(self.factory) as s:
                open_repository(s, LAWYER_A).create_matter("Will be rolled back")
                raise RuntimeError("simulated failure mid-transaction")
        with transaction(self.factory) as s:
            self.assertEqual(s.execute(select(func.count()).select_from(Matter)).scalar(), 0)
            actions = s.execute(select(AuditEvent.action)).scalars().all()
            self.assertNotIn("matter.created", actions)

    def test_audit_chain_detects_tampering(self):
        self.scenario()
        with transaction(self.factory) as s:
            self.assertTrue(open_repository(s, LAWYER_A).audit_chain_is_intact())
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE audit_events SET action = 'claim.deleted' "
                              "WHERE tenant_id = :t AND sequence = 3"), {"t": self.tenant_a})
        with transaction(self.factory) as s:
            self.assertFalse(open_repository(s, LAWYER_A).audit_chain_is_intact())
            self.assertTrue(open_repository(s, LAWYER_B).audit_chain_is_intact())

    # ── schema and migrations ──────────────────────────────
    def test_schema_version_mismatch_fails_closed(self):
        require_current_schema(self.engine)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num = '9999_future'"))
        with self.assertRaises(SchemaVersionMismatch):
            require_current_schema(self.engine)
        self.engine.dispose()
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE alembic_version SET version_num = :v"),
                         {"v": database.head_revision(self.url)})
        database.downgrade(self.url, "base")
        with self.assertRaises(SchemaVersionMismatch):
            require_current_schema(self.engine)

    def test_models_match_the_migration(self):
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext
        with self.engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        self.assertEqual(diff, [])

    def test_downgrade_and_reupgrade_round_trip(self):
        self.scenario()
        database.downgrade(self.url, "base")
        self.assertIsNone(database.current_revision(self.engine))
        database.upgrade(self.url)
        require_current_schema(self.engine)


class SQLiteEvidenceStoreTests(EvidenceStoreContract, unittest.TestCase):
    def database_url(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return f"sqlite:///{folder.name}/evidence.db"

    def test_evidence_migration_leaves_session_checkpoints_readable(self):
        # Even if EVIDENCE_DATABASE_URL were mistakenly pointed at the session
        # checkpoint file, the additive migration must not disturb checkpoints.
        import session_store
        from engines.debate_engine_v3 import DebateEngineV3
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = folder.name + "/sessions.db"
        with patch.dict(os.environ, SESSION_DB_PATH=path):
            engine = DebateEngineV3("compat", 20, 1, "general")
            session = dict(id="compat", engine=engine, task=None,
                           config=dict(num_agents=20, num_rounds=1, workflow_type="general"),
                           status="awaiting_feedback", events=[], error=None)
            session_store.save(session)
            database.upgrade(f"sqlite:///{path}")
            restored = session_store.load("compat", DebateEngineV3)
            self.assertEqual(restored["status"], "awaiting_feedback")
            database.downgrade(f"sqlite:///{path}", "base")
            self.assertEqual(session_store.load("compat", DebateEngineV3)["status"],
                             "awaiting_feedback")


POSTGRES_URL = os.environ.get("EVIDENCE_TEST_DATABASE_URL", "")
REQUIRE_POSTGRES = os.environ.get("EVIDENCE_REQUIRE_POSTGRES_TESTS") == "true"


@unittest.skipUnless(POSTGRES_URL or REQUIRE_POSTGRES,
                     "EVIDENCE_TEST_DATABASE_URL not set (CI requires it)")
class PostgresEvidenceStoreTests(EvidenceStoreContract, unittest.TestCase):
    def database_url(self):
        if not POSTGRES_URL:
            self.fail("EVIDENCE_REQUIRE_POSTGRES_TESTS is set but no database URL is")
        return POSTGRES_URL

    def test_failed_migration_leaves_no_partial_schema(self):
        database.downgrade(self.url, "base")
        from alembic import op
        real_create_table = op.create_table
        calls = {"n": 0}

        def failing_create_table(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 6:
                raise RuntimeError("simulated failure during migration")
            return real_create_table(*args, **kwargs)

        with patch.object(op, "create_table", side_effect=failing_create_table):
            with self.assertRaises(RuntimeError):
                database.upgrade(self.url)
        self.assertGreaterEqual(calls["n"], 6)
        from sqlalchemy import inspect
        self.engine.dispose()
        # Only alembic's empty bookkeeping table (left by the downgrade above)
        # may exist: no evidence table and no recorded revision.
        self.assertEqual(set(inspect(self.engine).get_table_names()) - {"alembic_version"}, set())
        self.assertIsNone(database.current_revision(self.engine))
        database.upgrade(self.url)  # restoration: a clean retry succeeds
        require_current_schema(self.engine)


class ObjectStoreTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = folder.name + "/objects"
        self.store = LocalPrivateObjectStore(self.root)
        self.tenant_a = "aaaaaaaa-1111-4111-8111-11111111abcd"
        self.tenant_b = "bbbbbbbb-2222-4222-8222-22222222cdef"

    def test_round_trip_is_private_idempotent_and_hash_verified(self):
        key = self.store.put(self.tenant_a, b"synthetic contract bytes")
        self.assertEqual(key, self.store.put(self.tenant_a, b"synthetic contract bytes"))
        self.assertEqual(self.store.get(self.tenant_a, key), b"synthetic contract bytes")
        path = os.path.join(self.root, *key.split("/"))
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.root).st_mode), 0o700)

    def test_malicious_keys_are_rejected(self):
        digest = "a" * 64
        for key in ("../" + digest, "/etc/passwd", f"{self.tenant_a}/../{digest}",
                    f"{self.tenant_a}/{digest}/x", f"{self.tenant_a.upper()}/{digest}",
                    f"{self.tenant_a}/{'A' * 64}", f"{self.tenant_a}/{digest[:-1]}",
                    "", f"{self.tenant_a}\\{digest}"):
            with self.subTest(key=key):
                with self.assertRaises(ObjectKeyError):
                    self.store.get(self.tenant_a, key)
        with self.assertRaises(ObjectKeyError):
            object_key("../escape", digest)

    def test_other_tenant_cannot_read_an_object(self):
        key = self.store.put(self.tenant_a, b"tenant A confidential")
        with self.assertRaises(ObjectAccessDenied):
            self.store.get(self.tenant_b, key)

    def test_tampered_object_fails_integrity_check(self):
        key = self.store.put(self.tenant_a, b"original")
        with open(os.path.join(self.root, *key.split("/")), "wb") as handle:
            handle.write(b"altered")
        with self.assertRaises(ObjectIntegrityError):
            self.store.get(self.tenant_a, key)


if __name__ == "__main__":
    unittest.main()
