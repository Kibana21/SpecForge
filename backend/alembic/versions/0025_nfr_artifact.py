"""NFR artifact tables: 3 enums + 8 versioned typed tables + traceability.

Extends artifact_type with 'nfr'. Tables:
  nfr_requirements (the 7-category core), nfr_risks, nfr_tradeoffs,
  nfr_open_questions, nfr_decisions, nfr_references, nfr_glossary,
  nfr_text_blocks, and nfr_traceability (NOT versioned, replace-all).

All versioned tables follow the BRD/CB/FRS/test-case row mixin pattern.

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-01
"""
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


# Shared versioned-row mixin DDL (same columns as cb_*/brd_*/frs_*/test_* tables).
_MIXIN = """
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
    row_key     TEXT NOT NULL,
    version     INTEGER NOT NULL CHECK (version > 0),
    is_current  BOOLEAN NOT NULL DEFAULT true,
    is_locked   BOOLEAN NOT NULL DEFAULT false,
    status      artifact_row_status NOT NULL DEFAULT 'active',
    source      artifact_row_source NOT NULL,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
"""


def upgrade() -> None:
    # ── Extend artifact_type enum to include 'nfr' ───────────────────────────────
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'nfr';
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── New enums ────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE nfr_category AS ENUM (
                'performance','security','availability','usability',
                'scalability','maintainability','portability'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE nfr_priority AS ENUM ('must','should','could','wont');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE nfr_trace_kind AS ENUM (
                'brd_objective','brd_business_requirement','brd_kpi','brd_risk',
                'brd_text_block','app_fact','doc_section','discover_qa','within_nfr'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── 1. nfr_requirements (the 7-category core) ────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_requirements (
            {_MIXIN},
            category     nfr_category NOT NULL,
            attribute    TEXT NOT NULL,
            requirement  TEXT NOT NULL,
            priority     nfr_priority NOT NULL DEFAULT 'should',
            rationale    TEXT NOT NULL DEFAULT '',
            measurement  TEXT NOT NULL DEFAULT '',
            brd_refs     JSONB NOT NULL DEFAULT '[]'::jsonb,
            completeness INTEGER NOT NULL DEFAULT 0,
            confidence   TEXT NOT NULL DEFAULT 'low',
            na           BOOLEAN NOT NULL DEFAULT false,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_requirements_current ON nfr_requirements(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_requirements_category ON nfr_requirements(document_id, category) WHERE is_current;")

    # ── 2. nfr_risks ─────────────────────────────────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_risks (
            {_MIXIN},
            risk_id            TEXT NOT NULL DEFAULT '',
            description        TEXT NOT NULL DEFAULT '',
            affected_attribute TEXT NOT NULL DEFAULT '',
            impact             TEXT NOT NULL DEFAULT '',
            likelihood         TEXT NOT NULL DEFAULT '',
            mitigation         TEXT NOT NULL DEFAULT '',
            owner              TEXT NOT NULL DEFAULT '',
            risk_status        TEXT NOT NULL DEFAULT 'open',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_risks_current ON nfr_risks(document_id) WHERE is_current;")

    # ── 3. nfr_tradeoffs ─────────────────────────────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_tradeoffs (
            {_MIXIN},
            tradeoff           TEXT NOT NULL DEFAULT '',
            options_considered JSONB NOT NULL DEFAULT '[]'::jsonb,
            decision           TEXT NOT NULL DEFAULT '',
            rationale          TEXT NOT NULL DEFAULT '',
            decided_on         TEXT NOT NULL DEFAULT '',
            decision_maker     TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_tradeoffs_current ON nfr_tradeoffs(document_id) WHERE is_current;")

    # ── 4. nfr_open_questions ────────────────────────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_open_questions (
            {_MIXIN},
            question  TEXT NOT NULL DEFAULT '',
            owner     TEXT NOT NULL DEFAULT '',
            due_date  TEXT NOT NULL DEFAULT '',
            oq_status TEXT NOT NULL DEFAULT 'open',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_open_questions_current ON nfr_open_questions(document_id) WHERE is_current;")

    # ── 5. nfr_decisions (pending decisions) ─────────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_decisions (
            {_MIXIN},
            description     TEXT NOT NULL DEFAULT '',
            owner           TEXT NOT NULL DEFAULT '',
            target_date     TEXT NOT NULL DEFAULT '',
            decision_status TEXT NOT NULL DEFAULT 'pending',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_decisions_current ON nfr_decisions(document_id) WHERE is_current;")

    # ── 6. nfr_references ────────────────────────────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_references (
            {_MIXIN},
            ref_type TEXT NOT NULL DEFAULT '',
            title    TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            notes    TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_references_current ON nfr_references(document_id) WHERE is_current;")

    # ── 7. nfr_glossary ──────────────────────────────────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_glossary (
            {_MIXIN},
            term       TEXT NOT NULL DEFAULT '',
            definition TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_glossary_current ON nfr_glossary(document_id) WHERE is_current;")

    # ── 8. nfr_text_blocks (overview / objectives) ───────────────────────────────
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS nfr_text_blocks (
            {_MIXIN},
            block_kind TEXT NOT NULL,
            content    TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_text_blocks_current ON nfr_text_blocks(document_id) WHERE is_current;")

    # ── 9. nfr_traceability (NOT versioned) ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS nfr_traceability (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            source_table    TEXT NOT NULL,
            source_row_key  TEXT NOT NULL,
            target_kind     nfr_trace_kind NOT NULL,
            target_ref      TEXT NOT NULL,
            target_label    TEXT NOT NULL DEFAULT '',
            confidence      TEXT NOT NULL DEFAULT 'high',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_traceability_doc ON nfr_traceability(document_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_traceability_source ON nfr_traceability(document_id, source_table, source_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nfr_traceability_target ON nfr_traceability(document_id, target_kind, target_ref);")


def downgrade() -> None:
    for tbl in [
        "nfr_traceability",
        "nfr_text_blocks",
        "nfr_glossary",
        "nfr_references",
        "nfr_decisions",
        "nfr_open_questions",
        "nfr_tradeoffs",
        "nfr_risks",
        "nfr_requirements",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl};")
    for enum_name in ["nfr_trace_kind", "nfr_priority", "nfr_category"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
    # Note: the 'nfr' value added to artifact_type is intentionally left in place —
    # PostgreSQL cannot easily remove an enum value, matching FRS/BRD/test-case practice.
