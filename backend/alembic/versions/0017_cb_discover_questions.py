"""Add cb_discover_questions and cb_discover_enhanced_briefs tables.

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-26
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend artifact_status enum with 'in_discover'
    op.execute("""
        ALTER TYPE artifact_status ADD VALUE IF NOT EXISTS 'in_discover';
    """)

    # Discovery questions table
    op.execute("""
        CREATE TABLE IF NOT EXISTS cb_discover_questions (
            id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            artifact_document_id UUID        NOT NULL
                REFERENCES artifact_documents(id) ON DELETE CASCADE,
            question_key         VARCHAR(10) NOT NULL,
            category             VARCHAR(50) NOT NULL,
            question_text        TEXT        NOT NULL,
            answer               TEXT,
            inferred_answer      TEXT,
            source               VARCHAR(30),
            context_sources      JSONB,
            seq                  INTEGER     NOT NULL,
            created_at           TIMESTAMPTZ DEFAULT now(),
            updated_at           TIMESTAMPTZ DEFAULT now(),
            UNIQUE (artifact_document_id, question_key)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_cb_discover_questions_doc
            ON cb_discover_questions(artifact_document_id);
    """)

    # Enhanced brief table
    op.execute("""
        CREATE TABLE IF NOT EXISTS cb_discover_enhanced_briefs (
            id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            artifact_document_id UUID        NOT NULL
                REFERENCES artifact_documents(id) ON DELETE CASCADE,
            original_brief       TEXT        NOT NULL,
            enhanced_brief       TEXT        NOT NULL,
            doc_sources          JSONB,
            app_sources          JSONB,
            created_at           TIMESTAMPTZ DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_cb_discover_enhanced_briefs_doc
            ON cb_discover_enhanced_briefs(artifact_document_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cb_discover_enhanced_briefs;")
    op.execute("DROP TABLE IF EXISTS cb_discover_questions;")
    # Note: Postgres does not support removing enum values; downgrade leaves in_discover in place.
