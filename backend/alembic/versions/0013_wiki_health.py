"""Brain Wiki health: apps.wiki_health JSONB report.

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-24
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE apps
        ADD COLUMN IF NOT EXISTS wiki_health JSONB
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS wiki_health")
