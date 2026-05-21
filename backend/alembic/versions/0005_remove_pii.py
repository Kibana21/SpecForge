"""Remove PII detection / data-classification columns (out of scope for SpecForge)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-21
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE app_corpus_docs DROP COLUMN IF EXISTS pii_detected")
    op.execute("ALTER TABLE app_corpus_docs DROP COLUMN IF EXISTS classification")
    op.execute("ALTER TABLE files DROP COLUMN IF EXISTS classification")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE files ADD COLUMN IF NOT EXISTS classification VARCHAR(50) NOT NULL DEFAULT 'internal'"
    )
    op.execute(
        "ALTER TABLE app_corpus_docs ADD COLUMN IF NOT EXISTS classification VARCHAR(50) NOT NULL DEFAULT 'internal'"
    )
    op.execute(
        "ALTER TABLE app_corpus_docs ADD COLUMN IF NOT EXISTS pii_detected BOOLEAN NOT NULL DEFAULT false"
    )
