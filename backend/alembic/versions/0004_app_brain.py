"""Add app brain tables (apps, app_members, app_corpus_docs, app_chunks, app_facts)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-21
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── apps ─────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS apps (
            id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            name           VARCHAR(255) NOT NULL,
            short_name     VARCHAR(50)  NOT NULL,
            description    TEXT,
            tier           INTEGER      NOT NULL CHECK (tier BETWEEN 1 AND 3),
            owner_id       UUID         REFERENCES users(id) ON DELETE SET NULL,
            is_onboarded   BOOLEAN      NOT NULL DEFAULT false,
            version        VARCHAR(50),
            domain_area    VARCHAR(100),
            rebuild_status VARCHAR(20),
            created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_apps_short_name ON apps (lower(short_name))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_apps_owner_id ON apps (owner_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_apps_tier ON apps (tier)")

    # ── app_members ───────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_members (
            app_id   UUID        NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            user_id  UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind     VARCHAR(20) NOT NULL DEFAULT 'delegate'
                         CHECK (kind IN ('owner', 'delegate')),
            added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (app_id, user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_members_user_id ON app_members (user_id)")

    # ── app_corpus_docs ───────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE index_status_enum AS ENUM ('pending', 'running', 'done', 'error');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app_corpus_docs (
            id             UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
            app_id         UUID               NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            file_id        UUID               NOT NULL REFERENCES files(id) ON DELETE RESTRICT,
            name           VARCHAR(500)       NOT NULL,
            page_count     INTEGER,
            is_primary     BOOLEAN            NOT NULL DEFAULT false,
            pii_detected   BOOLEAN            NOT NULL DEFAULT false,
            classification VARCHAR(50)        NOT NULL DEFAULT 'internal',
            indexed_at     TIMESTAMPTZ,
            index_status   index_status_enum  NOT NULL DEFAULT 'pending',
            index_error    VARCHAR(1000),
            created_at     TIMESTAMPTZ        NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_corpus_docs_app_id ON app_corpus_docs (app_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_corpus_docs_file_id ON app_corpus_docs (file_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_corpus_docs_index_status ON app_corpus_docs (index_status)")

    # ── app_chunks ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_chunks (
            id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
            doc_id     UUID    NOT NULL REFERENCES app_corpus_docs(id) ON DELETE CASCADE,
            chunk_no   INTEGER NOT NULL,
            text       TEXT    NOT NULL,
            embedding  vector(768),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (doc_id, chunk_no)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_chunks_doc_id ON app_chunks (doc_id)")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_app_chunks_embedding_ivfflat
            ON app_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
    """)

    # ── app_facts ─────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fact_kind_enum AS ENUM (
                'capability', 'constraint', 'limitation', 'integration', 'gotcha'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fact_confidence_enum AS ENUM ('high', 'medium', 'low');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fact_status_enum AS ENUM ('active', 'proposed', 'dismissed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS app_facts (
            id          UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
            app_id      UUID                NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
            kind        fact_kind_enum      NOT NULL,
            text        TEXT                NOT NULL,
            source_ref  VARCHAR(255),
            confidence  fact_confidence_enum NOT NULL DEFAULT 'medium',
            status      fact_status_enum    NOT NULL DEFAULT 'active',
            chunk_ids   JSONB               NOT NULL DEFAULT '[]',
            created_at  TIMESTAMPTZ         NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ         NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_facts_app_id ON app_facts (app_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_facts_kind ON app_facts (kind)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_facts_status ON app_facts (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_app_facts_chunk_ids_gin ON app_facts USING gin (chunk_ids)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_facts")
    op.execute("DROP TYPE IF EXISTS fact_status_enum")
    op.execute("DROP TYPE IF EXISTS fact_confidence_enum")
    op.execute("DROP TYPE IF EXISTS fact_kind_enum")
    op.execute("DROP TABLE IF EXISTS app_chunks")
    op.execute("DROP TABLE IF EXISTS app_corpus_docs")
    op.execute("DROP TYPE IF EXISTS index_status_enum")
    op.execute("DROP TABLE IF EXISTS app_members")
    op.execute("DROP TABLE IF EXISTS apps")
