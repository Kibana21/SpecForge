"""E2 — Project Intake & Requirement Understanding

Adds portfolio/intake fields to projects, source-intake state to documents,
the PageIndex tree store (document_trees), apps-in-scope, requirement
understanding + interview, assumptions, reuse selections, project embeddings
(similarity only), and materialized triage items.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-22
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── ALTER projects — portfolio + intake fields ──────────────────────────────
    op.execute("""
        ALTER TABLE projects
            ADD COLUMN IF NOT EXISTS human_id       VARCHAR(20),
            ADD COLUMN IF NOT EXISTS business_unit  VARCHAR(255),
            ADD COLUMN IF NOT EXISTS app_scope      VARCHAR(255),
            ADD COLUMN IF NOT EXISTS status         VARCHAR(30)  NOT NULL DEFAULT 'draft',
            ADD COLUMN IF NOT EXISTS priority       VARCHAR(20)  NOT NULL DEFAULT 'medium',
            ADD COLUMN IF NOT EXISTS completion_pct INTEGER      NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS go_live_date   DATE,
            ADD COLUMN IF NOT EXISTS stage_progress JSONB        NOT NULL DEFAULT '{}'::jsonb,
            ADD COLUMN IF NOT EXISTS ru_validated   BOOLEAN      NOT NULL DEFAULT false
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_human_id ON projects (human_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_business_unit ON projects (business_unit)")

    # ── ALTER documents — source intake state ───────────────────────────────────
    op.execute("""
        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS indexing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS index_error     VARCHAR(1000),
            ADD COLUMN IF NOT EXISTS page_count      INTEGER,
            ADD COLUMN IF NOT EXISTS sha256          VARCHAR(64)
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_documents_project_sha256 ON documents (project_id, sha256)")

    # ── ALTER gap_questions — also serve workspace open questions ────────────────
    op.execute("""
        ALTER TABLE gap_questions
            ADD COLUMN IF NOT EXISTS section     VARCHAR(255),
            ADD COLUMN IF NOT EXISTS due_date    DATE,
            ADD COLUMN IF NOT EXISTS assignee_id UUID REFERENCES users(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS source      VARCHAR(20) NOT NULL DEFAULT 'gap_detector'
    """)

    # ── document_trees — PageIndex reasoning-tree store ─────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS document_trees (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            tree_json   JSONB NOT NULL,
            page_texts  JSONB NOT NULL DEFAULT '{}'::jsonb,
            node_count  INTEGER NOT NULL DEFAULT 0,
            model       VARCHAR(100),
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_document_trees_project ON document_trees (project_id)")

    # ── project_apps — apps in scope ────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_apps (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            app_id            UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            suggested         BOOLEAN NOT NULL DEFAULT false,
            included          BOOLEAN NOT NULL DEFAULT true,
            app_brain_version VARCHAR(50),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (project_id, app_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_apps_project_id ON project_apps (project_id)")

    # ── requirement_understanding ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS requirement_understanding (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id       UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
            objective        TEXT,
            content_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
            field_confidence JSONB NOT NULL DEFAULT '{}'::jsonb,
            status           VARCHAR(20) NOT NULL DEFAULT 'draft',
            version_number   INTEGER NOT NULL DEFAULT 1,
            validated_at     TIMESTAMPTZ,
            validated_by     UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # ── interview_messages ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS interview_messages (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            understanding_id UUID NOT NULL REFERENCES requirement_understanding(id) ON DELETE CASCADE,
            role             VARCHAR(20) NOT NULL,
            content          TEXT NOT NULL,
            citations        JSONB NOT NULL DEFAULT '[]'::jsonb,
            seq              INTEGER NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_interview_messages_project_seq ON interview_messages (project_id, seq)")

    # ── assumptions (reuses confidence_level enum from 0001) ────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS assumptions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            ext_id      VARCHAR(50) NOT NULL,
            text        TEXT NOT NULL,
            confidence  confidence_level NOT NULL DEFAULT 'medium',
            source_ref  TEXT,
            status      VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_assumptions_project_id ON assumptions (project_id)")

    # ── reuse_selections ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS reuse_selections (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            source_project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
            asset_category    VARCHAR(50) NOT NULL,
            asset_ref         VARCHAR(255),
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_reuse_selections_project ON reuse_selections (project_id)")

    # ── project_embeddings (pgvector — similarity only) ─────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_embeddings (
            project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
            embedding  vector(768) NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_embeddings_ivfflat
            ON project_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    # ── triage_items (materialized per-user triage) ─────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS triage_items (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            project_id  UUID REFERENCES projects(id) ON DELETE CASCADE,
            kind        VARCHAR(30) NOT NULL,
            priority    INTEGER NOT NULL,
            title       TEXT NOT NULL,
            link        VARCHAR(500) NOT NULL,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            next_at     TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_triage_items_user_priority ON triage_items (user_id, priority)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS triage_items")
    op.execute("DROP TABLE IF EXISTS project_embeddings")
    op.execute("DROP TABLE IF EXISTS reuse_selections")
    op.execute("DROP TABLE IF EXISTS assumptions")
    op.execute("DROP TABLE IF EXISTS interview_messages")
    op.execute("DROP TABLE IF EXISTS requirement_understanding")
    op.execute("DROP TABLE IF EXISTS project_apps")
    op.execute("DROP TABLE IF EXISTS document_trees")
    op.execute("""
        ALTER TABLE gap_questions
            DROP COLUMN IF EXISTS section,
            DROP COLUMN IF EXISTS due_date,
            DROP COLUMN IF EXISTS assignee_id,
            DROP COLUMN IF EXISTS source
    """)
    op.execute("DROP INDEX IF EXISTS idx_documents_project_sha256")
    op.execute("""
        ALTER TABLE documents
            DROP COLUMN IF EXISTS indexing_status,
            DROP COLUMN IF EXISTS index_error,
            DROP COLUMN IF EXISTS page_count,
            DROP COLUMN IF EXISTS sha256
    """)
    op.execute("DROP INDEX IF EXISTS idx_projects_business_unit")
    op.execute("DROP INDEX IF EXISTS idx_projects_status")
    op.execute("DROP INDEX IF EXISTS uq_projects_human_id")
    op.execute("""
        ALTER TABLE projects
            DROP COLUMN IF EXISTS human_id,
            DROP COLUMN IF EXISTS business_unit,
            DROP COLUMN IF EXISTS app_scope,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS priority,
            DROP COLUMN IF EXISTS completion_pct,
            DROP COLUMN IF EXISTS go_live_date,
            DROP COLUMN IF EXISTS stage_progress,
            DROP COLUMN IF EXISTS ru_validated
    """)
