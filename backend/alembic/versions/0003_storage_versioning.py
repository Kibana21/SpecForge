"""Add files, file_blobs, and version_snapshots tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-21
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            name           VARCHAR(500) NOT NULL,
            content_type   VARCHAR(100) NOT NULL,
            size           BIGINT       NOT NULL,
            sha256         VARCHAR(64)  NOT NULL,
            classification VARCHAR(50)  NOT NULL DEFAULT 'internal',
            created_by     UUID,
            created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_files_sha256 ON files (sha256)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_files_created_by ON files (created_by)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS file_blobs (
            file_id  UUID    NOT NULL REFERENCES files(id) ON DELETE CASCADE,
            chunk_no INTEGER NOT NULL DEFAULT 0,
            data     BYTEA   NOT NULL,
            PRIMARY KEY (file_id, chunk_no)
        )
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE generation_type AS ENUM (
                'ai', 'human', 'regeneration', 'restore', 'import'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS version_snapshots (
            id               UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
            document_key     VARCHAR(255)    NOT NULL,
            version_no       INTEGER         NOT NULL,
            actor_id         UUID,
            created_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
            change_note      TEXT,
            changed_sections JSONB,
            change_count     INTEGER         NOT NULL DEFAULT 0,
            generation_type  generation_type NOT NULL DEFAULT 'human',
            is_immutable     BOOLEAN         NOT NULL DEFAULT false,
            content_ref      TEXT,
            CONSTRAINT uq_version_snapshots_key_ver UNIQUE (document_key, version_no)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_version_snapshots_document_key ON version_snapshots (document_key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_version_snapshots_actor_id ON version_snapshots (actor_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS version_snapshots")
    op.execute("DROP TYPE IF EXISTS generation_type")
    op.execute("DROP TABLE IF EXISTS file_blobs")
    op.execute("DROP TABLE IF EXISTS files")
