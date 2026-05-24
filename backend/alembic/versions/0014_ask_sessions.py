"""Ask Brain chat session persistence: app_ask_sessions.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-24
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_ask_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            app_id UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            messages JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ask_sessions_app_user
        ON app_ask_sessions (app_id, user_id, updated_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ask_sessions_app_user")
    op.execute("DROP TABLE IF EXISTS app_ask_sessions")
