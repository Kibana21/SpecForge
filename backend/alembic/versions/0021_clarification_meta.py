"""Clarification Engine metadata on gap_questions: kind, citations, rationale.

Additive + nullable — existing rows (RU's source='interview', gap_detector) keep
working with defaults. See .claude/plans/E2-intelligent-intake.md.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-30
"""
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS kind VARCHAR(20)")
    op.execute("ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS citations JSONB NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS rationale TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE gap_questions DROP COLUMN IF EXISTS rationale")
    op.execute("ALTER TABLE gap_questions DROP COLUMN IF EXISTS citations")
    op.execute("ALTER TABLE gap_questions DROP COLUMN IF EXISTS kind")
