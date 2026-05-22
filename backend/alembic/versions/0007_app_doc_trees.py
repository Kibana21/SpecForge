"""Hybrid App Brain — PageIndex reasoning tree per app corpus doc.

Adds app_doc_trees so the App Registry / App Brain can retrieve via PageIndex
(reasoning tree) in addition to the existing pgvector app_chunks.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-22
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_doc_trees (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            corpus_doc_id UUID NOT NULL UNIQUE REFERENCES app_corpus_docs(id) ON DELETE CASCADE,
            app_id        UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            tree_json     JSONB NOT NULL,
            page_texts    JSONB NOT NULL DEFAULT '{}'::jsonb,
            node_count    INTEGER NOT NULL DEFAULT 0,
            model         VARCHAR(100),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_doc_trees_app ON app_doc_trees (app_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_doc_trees")
