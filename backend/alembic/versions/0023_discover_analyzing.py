"""Add discover_analyzing flag to artifact_documents.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-31
"""
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE artifact_documents
            ADD COLUMN IF NOT EXISTS discover_analyzing BOOLEAN NOT NULL DEFAULT FALSE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE artifact_documents DROP COLUMN IF EXISTS discover_analyzing")
