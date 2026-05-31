"""Project Copilot chat sessions table.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-31
"""
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS project_ask_sessions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
            title       TEXT NOT NULL,
            messages    JSONB NOT NULL DEFAULT '[]',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_project_ask_sessions_project_user
            ON project_ask_sessions (project_id, user_id, updated_at DESC)
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_project_ask_sessions_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END;
        $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER trg_project_ask_sessions_updated_at
                BEFORE UPDATE ON project_ask_sessions
                FOR EACH ROW EXECUTE FUNCTION update_project_ask_sessions_updated_at();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_ask_sessions CASCADE")
    op.execute("DROP FUNCTION IF EXISTS update_project_ask_sessions_updated_at CASCADE")
