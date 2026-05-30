"""Project Wiki (E2): project_wiki_summaries + project_wiki_concepts tables;
projects wiki compilation state (wiki_status, wiki_compiled_at, wiki_health).

Mirrors the App Brain wiki (0012/0013) scoped to a project. Idempotent guards
so re-runs are safe.

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-30
"""
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Per-document project wiki summary (1 per project document)
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_wiki_summaries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            brief TEXT NOT NULL,
            content_md TEXT NOT NULL,
            related_slugs JSONB NOT NULL DEFAULT '[]',
            doc_type VARCHAR(20) NOT NULL DEFAULT 'short',
            compiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_pwiki_summaries_proj_doc UNIQUE (project_id, document_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_pwiki_summaries_project
        ON project_wiki_summaries (project_id)
    """)

    # Emergent cross-document project concept pages
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_wiki_concepts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            slug VARCHAR(120) NOT NULL,
            title TEXT NOT NULL,
            brief TEXT NOT NULL,
            content_md TEXT NOT NULL,
            source_doc_ids JSONB NOT NULL DEFAULT '[]',
            related_slugs JSONB NOT NULL DEFAULT '[]',
            tree_node_refs JSONB NOT NULL DEFAULT '[]',
            compiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_pwiki_concepts_proj_slug UNIQUE (project_id, slug)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_pwiki_concepts_project
        ON project_wiki_concepts (project_id)
    """)

    # projects: wiki compilation state
    op.execute("""
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS wiki_status VARCHAR(20) NOT NULL DEFAULT 'idle'
    """)
    op.execute("""
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS wiki_compiled_at TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS wiki_health JSONB
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS wiki_health")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS wiki_compiled_at")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS wiki_status")
    op.execute("DROP INDEX IF EXISTS ix_pwiki_concepts_project")
    op.execute("DROP TABLE IF EXISTS project_wiki_concepts")
    op.execute("DROP INDEX IF EXISTS ix_pwiki_summaries_project")
    op.execute("DROP TABLE IF EXISTS project_wiki_summaries")
