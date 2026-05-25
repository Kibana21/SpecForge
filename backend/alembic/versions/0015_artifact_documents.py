"""SDLC Artifacts: shared tables, Concept Brief typed tables, impact_note on project_apps.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-25
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mixin columns appended to every cb_* table (keeps DDL DRY)
_MIXIN = """
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
    row_key TEXT NOT NULL,
    version INT NOT NULL,
    is_current BOOL NOT NULL DEFAULT true,
    is_locked BOOL NOT NULL DEFAULT false,
    status artifact_row_status NOT NULL DEFAULT 'active',
    source artifact_row_source NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
"""

_CB_TABLES = [
    ("cb_text_blocks",    "field_key TEXT NOT NULL, text TEXT NOT NULL DEFAULT ''"),
    ("cb_context_map",    "dimension TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''"),
    ("cb_outcomes",       "outcome TEXT NOT NULL, description TEXT NOT NULL DEFAULT ''"),
    ("cb_metrics",        "metric TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', quantifiable BOOL NOT NULL DEFAULT false"),
    ("cb_capabilities",   "capability TEXT NOT NULL, description TEXT NOT NULL DEFAULT ''"),
    ("cb_scope_items",    "kind TEXT NOT NULL, text TEXT NOT NULL"),
    ("cb_milestones",     "milestone TEXT NOT NULL, target TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT ''"),
    ("cb_gate_criteria",  "criterion TEXT NOT NULL, gate_status TEXT NOT NULL DEFAULT 'Pending', notes TEXT NOT NULL DEFAULT ''"),
]


def upgrade() -> None:
    # ── Enums ─────────────────────────────────────────────────────────────────
    for enum_name, values in [
        ("artifact_type",         "'concept_brief','brd'"),
        ("artifact_status",       "'in_interview','validated'"),
        ("artifact_row_status",   "'active','removed'"),
        ("artifact_row_source",   "'ai','human','regeneration'"),
        ("artifact_message_role", "'ai','user','question','synthesis'"),
    ]:
        op.execute(f"""
            DO $$ BEGIN
                CREATE TYPE {enum_name} AS ENUM ({values});
            EXCEPTION WHEN duplicate_object THEN NULL;
            END $$;
        """)

    # ── Shared tables ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS artifact_documents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            artifact_type artifact_type NOT NULL,
            status artifact_status NOT NULL DEFAULT 'in_interview',
            unit_status JSONB NOT NULL DEFAULT '{}',
            validated_at TIMESTAMPTZ,
            validated_by UUID REFERENCES users(id) ON DELETE SET NULL,
            validated_snapshot_key TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_artifact_documents_project_type UNIQUE (project_id, artifact_type)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_artifact_documents_project_id ON artifact_documents (project_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS artifact_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            role artifact_message_role NOT NULL,
            content TEXT NOT NULL,
            citations JSONB NOT NULL DEFAULT '[]',
            meta JSONB NOT NULL DEFAULT '{}',
            seq INT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_artifact_messages_document_seq ON artifact_messages (document_id, seq)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS artifact_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            artifact_document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            source_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            included BOOL NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_artifact_sources UNIQUE (artifact_document_id, source_document_id)
        )
    """)

    # ── Concept Brief typed tables ────────────────────────────────────────────
    for table_name, typed_cols in _CB_TABLES:
        short = table_name.replace("cb_", "")
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {_MIXIN},
                {typed_cols},
                CONSTRAINT uq_{table_name}_doc_key_ver UNIQUE (document_id, row_key, version),
                CONSTRAINT ck_{table_name}_version CHECK (version > 0)
            )
        """)
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_current
            ON {table_name} (document_id) WHERE is_current
        """)

    # ── impact_note on project_apps ───────────────────────────────────────────
    op.execute("""
        ALTER TABLE project_apps ADD COLUMN IF NOT EXISTS impact_note TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE project_apps DROP COLUMN IF EXISTS impact_note")

    for table_name, _ in reversed(_CB_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table_name}")

    op.execute("DROP TABLE IF EXISTS artifact_sources")
    op.execute("DROP TABLE IF EXISTS artifact_messages")
    op.execute("DROP TABLE IF EXISTS artifact_documents")

    for enum_name in reversed([
        "artifact_message_role", "artifact_row_source", "artifact_row_status",
        "artifact_status", "artifact_type",
    ]):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
