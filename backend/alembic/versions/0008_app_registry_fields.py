"""App registry richness — environments + owner team.

Adds the data points the App Registry card surfaces (deployment environments and
the owning team) so they are real columns, not UI placeholders. LIVE PROJECTS and
OPEN QS are derived (project_apps count / proposed-fact count) — no columns needed.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-22
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE apps ADD COLUMN IF NOT EXISTS environments JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE apps ADD COLUMN IF NOT EXISTS owner_team VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS environments")
    op.execute("ALTER TABLE apps DROP COLUMN IF EXISTS owner_team")
