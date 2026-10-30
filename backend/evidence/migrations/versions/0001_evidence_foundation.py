"""Evidence foundation schema v1 (expand only).

Additive: creates new tables only; touches no existing table or the SQLite
session-checkpoint store. Generated with Alembic autogenerate against
PostgreSQL 16 and reviewed by hand (FK order, constraint names, RESTRICT
semantics, reverse-order downgrade).

Revision ID: 0001_evidence_foundation
Revises: 
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa


revision = '0001_evidence_foundation'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('tenants',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tenants'))
    )
    op.create_table('audit_events',
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('actor_issuer', sa.String(length=500), nullable=False),
    sa.Column('actor_subject', sa.String(length=500), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('entity_type', sa.String(length=100), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('detail_json', sa.Text(), nullable=False),
    sa.Column('prev_hash', sa.String(length=64), nullable=False),
    sa.Column('event_hash', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_audit_events_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_audit_events_tenant_id_id')),
    sa.UniqueConstraint('tenant_id', 'sequence', name=op.f('uq_audit_events_tenant_id_sequence'))
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('legal_sources',
    sa.Column('source_type', sa.String(length=20), nullable=False),
    sa.Column('authority', sa.String(length=200), nullable=False),
    sa.Column('identifier', sa.String(length=300), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('official_url', sa.String(length=1000), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("source_type IN ('statute','precedent','regulation','other')", name=op.f('ck_legal_sources_source_type')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_legal_sources_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_legal_sources')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_legal_sources_tenant_id_id')),
    sa.UniqueConstraint('tenant_id', 'source_type', 'identifier', name=op.f('uq_legal_sources_tenant_id_source_type_identifier'))
    )
    with op.batch_alter_table('legal_sources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_legal_sources_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('matters',
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_matters_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_matters')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_matters_tenant_id_id'))
    )
    with op.batch_alter_table('matters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_matters_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('tenant_memberships',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('issuer', sa.String(length=500), nullable=False),
    sa.Column('subject', sa.String(length=500), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("role IN ('member','reviewer','admin')", name=op.f('ck_tenant_memberships_role')),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name=op.f('fk_tenant_memberships_tenant_id_tenants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tenant_memberships')),
    sa.UniqueConstraint('tenant_id', 'issuer', 'subject', name=op.f('uq_tenant_memberships_tenant_id_issuer_subject'))
    )
    with op.batch_alter_table('tenant_memberships', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tenant_memberships_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('documents',
    sa.Column('matter_id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id', 'matter_id'], ['matters.tenant_id', 'matters.id'], name=op.f('fk_documents_tenant_id_matter_id_matters'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_documents')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_documents_tenant_id_id'))
    )
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documents_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('legal_claims',
    sa.Column('matter_id', sa.String(length=36), nullable=False),
    sa.Column('statement', sa.Text(), nullable=False),
    sa.Column('claim_type', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('verified_by_decision_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("claim_type IN ('fact','interpretation','conclusion')", name=op.f('ck_legal_claims_claim_type')),
    sa.CheckConstraint("status <> 'verified' OR verified_by_decision_id IS NOT NULL", name=op.f('ck_legal_claims_verified_requires_decision')),
    sa.CheckConstraint("status IN ('unverified','insufficient_evidence','verified','rejected')", name=op.f('ck_legal_claims_status')),
    sa.ForeignKeyConstraint(['tenant_id', 'matter_id'], ['matters.tenant_id', 'matters.id'], name=op.f('fk_legal_claims_tenant_id_matter_id_matters'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_legal_claims')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_legal_claims_tenant_id_id'))
    )
    with op.batch_alter_table('legal_claims', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_legal_claims_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('source_versions',
    sa.Column('legal_source_id', sa.String(length=36), nullable=False),
    sa.Column('version_label', sa.String(length=200), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('effective_from', sa.String(length=10), nullable=False),
    sa.Column('effective_to', sa.String(length=10), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id', 'legal_source_id'], ['legal_sources.tenant_id', 'legal_sources.id'], name=op.f('fk_source_versions_tenant_id_legal_source_id_legal_sources'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_source_versions')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_source_versions_tenant_id_id')),
    sa.UniqueConstraint('tenant_id', 'legal_source_id', 'content_sha256', name=op.f('uq_source_versions_tenant_id_legal_source_id_content_sha256'))
    )
    with op.batch_alter_table('source_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_source_versions_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('document_versions',
    sa.Column('document_id', sa.String(length=36), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('media_type', sa.String(length=120), nullable=False),
    sa.Column('byte_size', sa.Integer(), nullable=False),
    sa.Column('object_key', sa.String(length=200), nullable=False),
    sa.Column('extraction_version', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('byte_size >= 0', name=op.f('ck_document_versions_size_non_negative')),
    sa.CheckConstraint('version_number >= 1', name=op.f('ck_document_versions_version_positive')),
    sa.ForeignKeyConstraint(['tenant_id', 'document_id'], ['documents.tenant_id', 'documents.id'], name=op.f('fk_document_versions_tenant_id_document_id_documents'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_versions')),
    sa.UniqueConstraint('tenant_id', 'document_id', 'content_sha256', name=op.f('uq_document_versions_tenant_id_document_id_content_sha256')),
    sa.UniqueConstraint('tenant_id', 'document_id', 'version_number', name=op.f('uq_document_versions_tenant_id_document_id_version_number')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_document_versions_tenant_id_id'))
    )
    with op.batch_alter_table('document_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_versions_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('review_decisions',
    sa.Column('claim_id', sa.String(length=36), nullable=False),
    sa.Column('reviewer_issuer', sa.String(length=500), nullable=False),
    sa.Column('reviewer_subject', sa.String(length=500), nullable=False),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('evidence_set_sha256', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("decision IN ('approve','reject','correct','reanalyze')", name=op.f('ck_review_decisions_decision')),
    sa.CheckConstraint('length(rationale) > 0', name=op.f('ck_review_decisions_rationale_required')),
    sa.ForeignKeyConstraint(['tenant_id', 'claim_id'], ['legal_claims.tenant_id', 'legal_claims.id'], name=op.f('fk_review_decisions_tenant_id_claim_id_legal_claims'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_review_decisions')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_review_decisions_tenant_id_id'))
    )
    with op.batch_alter_table('review_decisions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_review_decisions_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('clauses',
    sa.Column('document_version_id', sa.String(length=36), nullable=False),
    sa.Column('label', sa.String(length=100), nullable=False),
    sa.Column('heading', sa.String(length=500), nullable=False),
    sa.Column('start_page', sa.Integer(), nullable=False),
    sa.Column('start_offset', sa.Integer(), nullable=False),
    sa.Column('end_page', sa.Integer(), nullable=False),
    sa.Column('end_offset', sa.Integer(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('start_page >= 1 AND end_page >= start_page', name=op.f('ck_clauses_pages')),
    sa.ForeignKeyConstraint(['tenant_id', 'document_version_id'], ['document_versions.tenant_id', 'document_versions.id'], name=op.f('fk_clauses_tenant_id_document_version_id_document_versions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_clauses')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_clauses_tenant_id_id'))
    )
    with op.batch_alter_table('clauses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_clauses_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('evidence_spans',
    sa.Column('document_version_id', sa.String(length=36), nullable=True),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('source_version_id', sa.String(length=36), nullable=True),
    sa.Column('start_offset', sa.Integer(), nullable=False),
    sa.Column('end_offset', sa.Integer(), nullable=False),
    sa.Column('quoted_text', sa.Text(), nullable=False),
    sa.Column('quoted_sha256', sa.String(length=64), nullable=False),
    sa.Column('origin_sha256', sa.String(length=64), nullable=False),
    sa.Column('extraction_version', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('(document_version_id IS NOT NULL AND source_version_id IS NULL AND page_number IS NOT NULL) OR (document_version_id IS NULL AND source_version_id IS NOT NULL AND page_number IS NULL)', name=op.f('ck_evidence_spans_single_origin')),
    sa.CheckConstraint('start_offset >= 0 AND end_offset > start_offset', name=op.f('ck_evidence_spans_offsets')),
    sa.ForeignKeyConstraint(['tenant_id', 'document_version_id'], ['document_versions.tenant_id', 'document_versions.id'], name=op.f('fk_evidence_spans_tenant_id_document_version_id_document_versions'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tenant_id', 'source_version_id'], ['source_versions.tenant_id', 'source_versions.id'], name=op.f('fk_evidence_spans_tenant_id_source_version_id_source_versions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_evidence_spans')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_evidence_spans_tenant_id_id'))
    )
    with op.batch_alter_table('evidence_spans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evidence_spans_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('pages',
    sa.Column('document_version_id', sa.String(length=36), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('text_sha256', sa.String(length=64), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('page_number >= 1', name=op.f('ck_pages_page_positive')),
    sa.ForeignKeyConstraint(['tenant_id', 'document_version_id'], ['document_versions.tenant_id', 'document_versions.id'], name=op.f('fk_pages_tenant_id_document_version_id_document_versions'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pages')),
    sa.UniqueConstraint('tenant_id', 'document_version_id', 'page_number', name=op.f('uq_pages_tenant_id_document_version_id_page_number')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_pages_tenant_id_id'))
    )
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pages_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('claim_evidence_links',
    sa.Column('claim_id', sa.String(length=36), nullable=False),
    sa.Column('evidence_span_id', sa.String(length=36), nullable=False),
    sa.Column('relation', sa.String(length=20), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("relation IN ('supports','contradicts','context')", name=op.f('ck_claim_evidence_links_relation')),
    sa.ForeignKeyConstraint(['tenant_id', 'claim_id'], ['legal_claims.tenant_id', 'legal_claims.id'], name=op.f('fk_claim_evidence_links_tenant_id_claim_id_legal_claims'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tenant_id', 'evidence_span_id'], ['evidence_spans.tenant_id', 'evidence_spans.id'], name=op.f('fk_claim_evidence_links_tenant_id_evidence_span_id_evidence_spans'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_claim_evidence_links')),
    sa.UniqueConstraint('tenant_id', 'claim_id', 'evidence_span_id', name=op.f('uq_claim_evidence_links_tenant_id_claim_id_evidence_span_id')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_claim_evidence_links_tenant_id_id'))
    )
    with op.batch_alter_table('claim_evidence_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_claim_evidence_links_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('document_tables',
    sa.Column('page_id', sa.String(length=36), nullable=False),
    sa.Column('table_index', sa.Integer(), nullable=False),
    sa.Column('cells_json', sa.Text(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id', 'page_id'], ['pages.tenant_id', 'pages.id'], name=op.f('fk_document_tables_tenant_id_page_id_pages'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_tables')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_document_tables_tenant_id_id')),
    sa.UniqueConstraint('tenant_id', 'page_id', 'table_index', name=op.f('uq_document_tables_tenant_id_page_id_table_index'))
    )
    with op.batch_alter_table('document_tables', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_document_tables_tenant_id'), ['tenant_id'], unique=False)

    op.create_table('text_blocks',
    sa.Column('page_id', sa.String(length=36), nullable=False),
    sa.Column('block_index', sa.Integer(), nullable=False),
    sa.Column('start_offset', sa.Integer(), nullable=False),
    sa.Column('end_offset', sa.Integer(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('start_offset >= 0 AND end_offset >= start_offset', name=op.f('ck_text_blocks_offsets')),
    sa.ForeignKeyConstraint(['tenant_id', 'page_id'], ['pages.tenant_id', 'pages.id'], name=op.f('fk_text_blocks_tenant_id_page_id_pages'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_text_blocks')),
    sa.UniqueConstraint('tenant_id', 'id', name=op.f('uq_text_blocks_tenant_id_id')),
    sa.UniqueConstraint('tenant_id', 'page_id', 'block_index', name=op.f('uq_text_blocks_tenant_id_page_id_block_index'))
    )
    with op.batch_alter_table('text_blocks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_text_blocks_tenant_id'), ['tenant_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('text_blocks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_text_blocks_tenant_id'))

    op.drop_table('text_blocks')
    with op.batch_alter_table('document_tables', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_tables_tenant_id'))

    op.drop_table('document_tables')
    with op.batch_alter_table('claim_evidence_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_claim_evidence_links_tenant_id'))

    op.drop_table('claim_evidence_links')
    with op.batch_alter_table('pages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pages_tenant_id'))

    op.drop_table('pages')
    with op.batch_alter_table('evidence_spans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evidence_spans_tenant_id'))

    op.drop_table('evidence_spans')
    with op.batch_alter_table('clauses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_clauses_tenant_id'))

    op.drop_table('clauses')
    with op.batch_alter_table('review_decisions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_review_decisions_tenant_id'))

    op.drop_table('review_decisions')
    with op.batch_alter_table('document_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_document_versions_tenant_id'))

    op.drop_table('document_versions')
    with op.batch_alter_table('source_versions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_source_versions_tenant_id'))

    op.drop_table('source_versions')
    with op.batch_alter_table('legal_claims', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_legal_claims_tenant_id'))

    op.drop_table('legal_claims')
    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documents_tenant_id'))

    op.drop_table('documents')
    with op.batch_alter_table('tenant_memberships', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tenant_memberships_tenant_id'))

    op.drop_table('tenant_memberships')
    with op.batch_alter_table('matters', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_matters_tenant_id'))

    op.drop_table('matters')
    with op.batch_alter_table('legal_sources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_legal_sources_tenant_id'))

    op.drop_table('legal_sources')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_tenant_id'))

    op.drop_table('audit_events')
    op.drop_table('tenants')
