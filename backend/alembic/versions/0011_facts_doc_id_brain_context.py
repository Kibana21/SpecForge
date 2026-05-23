"""Add doc_id + source_fact_ids to app_facts; add brain_context fields to apps.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-23
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # app_facts: link facts to their source corpus document
    op.execute("""
        ALTER TABLE app_facts
        ADD COLUMN IF NOT EXISTS doc_id UUID
            REFERENCES app_corpus_docs(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_app_facts_doc_id ON app_facts (doc_id)
    """)

    # app_facts: traceability array — which per-doc facts contributed to a brain fact
    op.execute("""
        ALTER TABLE app_facts
        ADD COLUMN IF NOT EXISTS source_fact_ids JSONB NOT NULL DEFAULT '[]'
    """)

    # apps: brain context synthesis state
    op.execute("""
        ALTER TABLE apps
        ADD COLUMN IF NOT EXISTS brain_context_synthesized_at TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE apps
        ADD COLUMN IF NOT EXISTS brain_context_status VARCHAR(20) NOT NULL DEFAULT 'idle'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_app_facts_doc_id")
    op.execute("ALTER TABLE app_facts DROP COLUMN IF EXISTS doc_id")
    op.execute("ALTER TABLE app_facts DROP COLUMN IF EXISTS source_fact_ids")
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS brain_context_synthesized_at")
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS brain_context_status")
