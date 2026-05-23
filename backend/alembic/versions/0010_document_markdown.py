"""Add document_markdown table for cached markdown conversions.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-23
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS document_markdown (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            correlation_id VARCHAR(36),
            source_hash VARCHAR(64) NOT NULL,
            filename    VARCHAR(500) NOT NULL,
            mime_type   VARCHAR(100) NOT NULL,
            markdown_text TEXT NOT NULL,
            provider    VARCHAR(50) NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_docmd_source_hash    ON document_markdown (source_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_docmd_correlation_id ON document_markdown (correlation_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS document_markdown")
