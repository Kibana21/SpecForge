"""Brain Wiki: app_wiki_summaries + app_wiki_concepts tables; apps wiki state.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-24
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Per-document wiki summary (1 per corpus doc)
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_wiki_summaries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            app_id UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            doc_id UUID NOT NULL REFERENCES app_corpus_docs(id) ON DELETE CASCADE,
            brief TEXT NOT NULL,
            content_md TEXT NOT NULL,
            related_slugs JSONB NOT NULL DEFAULT '[]',
            doc_type VARCHAR(20) NOT NULL DEFAULT 'short',
            compiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_wiki_summaries_app_doc UNIQUE (app_id, doc_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_wiki_summaries_app ON app_wiki_summaries (app_id)
    """)

    # Emergent cross-document concept pages
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_wiki_concepts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            app_id UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            slug VARCHAR(120) NOT NULL,
            title TEXT NOT NULL,
            brief TEXT NOT NULL,
            content_md TEXT NOT NULL,
            source_doc_ids JSONB NOT NULL DEFAULT '[]',
            related_slugs JSONB NOT NULL DEFAULT '[]',
            tree_node_refs JSONB NOT NULL DEFAULT '[]',
            compiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_wiki_concepts_app_slug UNIQUE (app_id, slug)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_wiki_concepts_app ON app_wiki_concepts (app_id)
    """)

    # apps: wiki compilation state
    op.execute("""
        ALTER TABLE apps
        ADD COLUMN IF NOT EXISTS wiki_status VARCHAR(20) NOT NULL DEFAULT 'idle'
    """)
    op.execute("""
        ALTER TABLE apps
        ADD COLUMN IF NOT EXISTS wiki_compiled_at TIMESTAMPTZ
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS wiki_compiled_at")
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS wiki_status")
    op.execute("DROP INDEX IF EXISTS ix_wiki_concepts_app")
    op.execute("DROP TABLE IF EXISTS app_wiki_concepts")
    op.execute("DROP INDEX IF EXISTS ix_wiki_summaries_app")
    op.execute("DROP TABLE IF EXISTS app_wiki_summaries")
