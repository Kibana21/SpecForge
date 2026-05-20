"""Add auth tables: users, refresh_tokens, password_reset_tokens, audit_events, project_members

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-21

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM (
                'business_analyst', 'product_owner', 'solution_architect',
                'app_owner', 'qa_lead', 'compliance_reviewer', 'platform_admin'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_status AS ENUM ('active', 'locked', 'disabled');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            email               VARCHAR(255) NOT NULL,
            display_name        VARCHAR(80)  NOT NULL,
            password_hash       VARCHAR(255) NOT NULL,
            role                user_role    NOT NULL,
            status              user_status  NOT NULL DEFAULT 'active',
            is_test             BOOLEAN      NOT NULL DEFAULT false,
            failed_login_count  INTEGER      NOT NULL DEFAULT 0,
            locked_until        TIMESTAMPTZ,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_users_email UNIQUE (email)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users (status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash  VARCHAR(64) NOT NULL,
            family_id   VARCHAR(36) NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked     BOOLEAN     NOT NULL DEFAULT false,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_refresh_tokens_hash UNIQUE (token_hash)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens (token_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family_id ON refresh_tokens (family_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash  VARCHAR(64) NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            used        BOOLEAN     NOT NULL DEFAULT false,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_password_reset_tokens_hash UNIQUE (token_hash)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash ON password_reset_tokens (token_hash)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id                BIGSERIAL    PRIMARY KEY,
            event             VARCHAR(100) NOT NULL,
            actor_id          UUID,
            email_hash        VARCHAR(64),
            project_id        UUID,
            document_key      VARCHAR(255),
            app_key           VARCHAR(255),
            action            VARCHAR(100),
            source_version    VARCHAR(50),
            target_version    VARCHAR(50),
            affected_sections JSONB,
            ai_meta           JSONB,
            ip                VARCHAR(45),
            user_agent        VARCHAR(255),
            correlation_id    VARCHAR(36),
            ts                TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_actor_id ON audit_events (actor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_event ON audit_events (event)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_ts ON audit_events (ts)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_project_id ON audit_events (project_id)")

    # Add owner_id to existing projects table
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id) ON DELETE SET NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects (owner_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS project_members (
            project_id UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            user_id    UUID        NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
            role       VARCHAR(50) NOT NULL DEFAULT 'member',
            added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (project_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_project_members_user_id ON project_members (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS project_members")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS owner_id")
    op.execute("DROP TABLE IF EXISTS audit_events")
    op.execute("DROP TABLE IF EXISTS password_reset_tokens")
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")
