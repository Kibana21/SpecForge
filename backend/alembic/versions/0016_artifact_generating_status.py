"""Add generating status to artifact_status enum.

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-25
"""
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE artifact_status ADD VALUE IF NOT EXISTS 'generating'")


def downgrade():
    pass
