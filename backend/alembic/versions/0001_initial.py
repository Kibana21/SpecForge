"""Initial schema — all tables and enum types

Revision ID: 0001
Revises:
Create Date: 2026-05-14

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── Enum types (idempotent — safe on re-run) ──────────────────────────────
    _enums = [
        ("parse_status", ["pending", "done", "error"]),
        ("requirement_category", ["functional", "non_functional", "constraint", "assumption", "stakeholder"]),
        ("confidence_level", ["high", "medium", "low"]),
        ("spec_type", ["functional", "technical", "user_stories", "review"]),
        ("gap_category", ["scope", "data", "security", "integration", "ux"]),
        ("gap_severity", ["blocker", "major", "minor"]),
        ("review_severity", ["critical", "warning", "suggestion"]),
        ("review_category", ["completeness", "ambiguity", "security", "data", "implementation"]),
    ]
    for name, values in _enums:
        quoted = ", ".join(f"'{v}'" for v in values)
        op.execute(
            f"DO $$ BEGIN "
            f"CREATE TYPE {name} AS ENUM ({quoted}); "
            f"EXCEPTION WHEN duplicate_object THEN NULL; "
            f"END $$"
        )

    # ── projects ──────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            name          VARCHAR(255) NOT NULL,
            description   TEXT,
            deleted_at    TIMESTAMPTZ,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_deleted_at ON projects (deleted_at)")

    # ── documents ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id     UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            filename       VARCHAR(500)  NOT NULL,
            mime_type      VARCHAR(100)  NOT NULL,
            size_bytes     BIGINT        NOT NULL,
            storage_path   TEXT          NOT NULL,
            extracted_text TEXT,
            parse_status   parse_status  NOT NULL DEFAULT 'pending',
            parse_error    TEXT,
            created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
            CONSTRAINT ck_documents_size_bytes_positive CHECK (size_bytes > 0)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents (project_id)")

    # ── extracted_requirements ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS extracted_requirements (
            id               UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id       UUID                 NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            document_id      UUID                 REFERENCES documents(id) ON DELETE SET NULL,
            category         requirement_category NOT NULL,
            ext_id           VARCHAR(50)          NOT NULL,
            text             TEXT                 NOT NULL,
            source_reference TEXT,
            confidence       confidence_level     NOT NULL,
            created_at       TIMESTAMPTZ          NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ          NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_extracted_requirements_project_id ON extracted_requirements (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_extracted_requirements_project_category ON extracted_requirements (project_id, category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_extracted_requirements_document_id ON extracted_requirements (document_id)")

    # ── spec_versions ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS spec_versions (
            id               UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id       UUID      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            spec_type        spec_type NOT NULL,
            version_number   INTEGER   NOT NULL,
            content_json     JSONB     NOT NULL,
            content_markdown TEXT,
            is_edited        BOOLEAN   NOT NULL DEFAULT false,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_spec_versions_version_positive CHECK (version_number > 0)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_spec_versions_project_id ON spec_versions (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_spec_versions_project_type_version ON spec_versions (project_id, spec_type, version_number)")

    # ── gap_questions ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS gap_questions (
            id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id      UUID         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            ext_id          VARCHAR(50)  NOT NULL,
            question        TEXT         NOT NULL,
            category        gap_category NOT NULL,
            severity        gap_severity NOT NULL,
            resolved        BOOLEAN      NOT NULL DEFAULT false,
            resolution_text TEXT,
            resolved_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_gap_questions_project_id ON gap_questions (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_gap_questions_project_resolved ON gap_questions (project_id, resolved)")

    # ── review_comments ───────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS review_comments (
            id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id      UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            spec_version_id UUID            REFERENCES spec_versions(id) ON DELETE SET NULL,
            section         TEXT            NOT NULL,
            comment         TEXT            NOT NULL,
            severity        review_severity NOT NULL,
            category        review_category NOT NULL,
            dismissed       BOOLEAN         NOT NULL DEFAULT false,
            dismissed_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_review_comments_project_id ON review_comments (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_review_comments_spec_version_id ON review_comments (spec_version_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_review_comments_project_dismissed_severity ON review_comments (project_id, dismissed, severity)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS review_comments")
    op.execute("DROP TABLE IF EXISTS gap_questions")
    op.execute("DROP TABLE IF EXISTS spec_versions")
    op.execute("DROP TABLE IF EXISTS extracted_requirements")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute("DROP TABLE IF EXISTS projects")

    for name in [
        "review_category", "review_severity", "gap_severity", "gap_category",
        "spec_type", "confidence_level", "requirement_category", "parse_status",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
