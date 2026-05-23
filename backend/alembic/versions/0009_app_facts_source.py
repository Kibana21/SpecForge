"""Add source column to app_facts to distinguish AI-extracted vs human-authored facts.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-23
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app_facts
        ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'ai'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE app_facts DROP COLUMN IF EXISTS source")
