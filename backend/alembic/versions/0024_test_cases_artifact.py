"""Test Cases artifact tables: 4 enums + 3 typed tables + traceability.

Extends artifact_type with 'test_cases'. Tables:
  test_suites (one per FRS module), test_plans (one per FRS spec),
  test_cases, and test_case_traceability (NOT versioned, replace-all).

All versioned tables follow the BRD/CB/FRS row mixin pattern.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-31
"""
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend artifact_type enum to include 'test_cases' ─────────────────────
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'test_cases';
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── New enums ──────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tc_test_type AS ENUM (
                'functional','integration','e2e','negative','edge_case','responsive'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tc_priority AS ENUM ('P0','P1','P2','P3');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tc_source_kind AS ENUM (
                'acceptance_scenario','functional_requirement','business_rule',
                'independent_test','screen','manual'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tc_trace_kind AS ENUM (
                'frs_spec','frs_acceptance_scenario','frs_functional_requirement',
                'frs_business_rule','frs_screen','brd_business_requirement',
                'within_test_cases'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── 1. test_suites ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS test_suites (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id       UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key           TEXT NOT NULL,
            version           INTEGER NOT NULL CHECK (version > 0),
            is_current        BOOLEAN NOT NULL DEFAULT true,
            is_locked         BOOLEAN NOT NULL DEFAULT false,
            status            artifact_row_status NOT NULL DEFAULT 'active',
            source            artifact_row_source NOT NULL,
            created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            module_row_key    TEXT NOT NULL,
            title             TEXT NOT NULL,
            journey_overview  TEXT NOT NULL DEFAULT '',
            test_strategy     TEXT NOT NULL DEFAULT '',
            outcomes_summary  TEXT NOT NULL DEFAULT '',
            completeness      INTEGER NOT NULL DEFAULT 0,
            confidence        TEXT NOT NULL DEFAULT 'low',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_suites_current ON test_suites(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_suites_module ON test_suites(document_id, module_row_key);")

    # ── 2. test_plans ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS test_plans (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id       UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key           TEXT NOT NULL,
            version           INTEGER NOT NULL CHECK (version > 0),
            is_current        BOOLEAN NOT NULL DEFAULT true,
            is_locked         BOOLEAN NOT NULL DEFAULT false,
            status            artifact_row_status NOT NULL DEFAULT 'active',
            source            artifact_row_source NOT NULL,
            created_by        UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            suite_row_key     TEXT NOT NULL,
            spec_row_key      TEXT NOT NULL,
            module_row_key    TEXT NOT NULL,
            title             TEXT NOT NULL,
            preconditions     TEXT NOT NULL DEFAULT '',
            test_data_notes   TEXT NOT NULL DEFAULT '',
            coverage_targets  JSONB NOT NULL DEFAULT '{}'::jsonb,
            outcomes_summary  TEXT NOT NULL DEFAULT '',
            priority          tc_priority NOT NULL DEFAULT 'P1',
            summary           TEXT NOT NULL DEFAULT '',
            completeness      INTEGER NOT NULL DEFAULT 0,
            confidence        TEXT NOT NULL DEFAULT 'low',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_plans_current ON test_plans(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_plans_spec ON test_plans(document_id, spec_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_plans_suite ON test_plans(document_id, suite_row_key);")

    # ── 3. test_cases ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id             UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key                 TEXT NOT NULL,
            version                 INTEGER NOT NULL CHECK (version > 0),
            is_current              BOOLEAN NOT NULL DEFAULT true,
            is_locked               BOOLEAN NOT NULL DEFAULT false,
            status                  artifact_row_status NOT NULL DEFAULT 'active',
            source                  artifact_row_source NOT NULL,
            created_by              UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            plan_row_key            TEXT NOT NULL,
            spec_row_key            TEXT NOT NULL,
            module_row_key          TEXT NOT NULL,
            title                   TEXT NOT NULL,
            test_type               tc_test_type NOT NULL DEFAULT 'functional',
            source_kind             tc_source_kind NOT NULL DEFAULT 'acceptance_scenario',
            source_ref              TEXT,
            "given"                 TEXT NOT NULL DEFAULT '',
            "when"                  TEXT NOT NULL DEFAULT '',
            "then"                  TEXT NOT NULL DEFAULT '',
            steps                   JSONB NOT NULL DEFAULT '[]'::jsonb,
            preconditions           TEXT NOT NULL DEFAULT '',
            key_assertions          JSONB NOT NULL DEFAULT '[]'::jsonb,
            test_data               JSONB NOT NULL DEFAULT '{}'::jsonb,
            expected_result         TEXT NOT NULL DEFAULT '',
            expected_observability  JSONB NOT NULL DEFAULT '[]'::jsonb,
            viewports               JSONB NOT NULL DEFAULT '[]'::jsonb,
            auth_required           BOOLEAN NOT NULL DEFAULT false,
            auth_role               TEXT,
            priority                tc_priority NOT NULL DEFAULT 'P1',
            fr_refs                 JSONB NOT NULL DEFAULT '[]'::jsonb,
            scenario_refs           JSONB NOT NULL DEFAULT '[]'::jsonb,
            br_refs                 JSONB NOT NULL DEFAULT '[]'::jsonb,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_current ON test_cases(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_plan ON test_cases(document_id, plan_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_spec ON test_cases(document_id, spec_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_module ON test_cases(document_id, module_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_test_cases_type ON test_cases(document_id, test_type);")

    # ── 4. test_case_traceability (NOT versioned) ─────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS test_case_traceability (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            source_table    TEXT NOT NULL,
            source_row_key  TEXT NOT NULL,
            target_kind     tc_trace_kind NOT NULL,
            target_ref      TEXT NOT NULL,
            target_label    TEXT NOT NULL DEFAULT '',
            confidence      TEXT NOT NULL DEFAULT 'high',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tc_traceability_doc ON test_case_traceability(document_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tc_traceability_source ON test_case_traceability(document_id, source_table, source_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tc_traceability_target ON test_case_traceability(document_id, target_kind, target_ref);")


def downgrade() -> None:
    for tbl in [
        "test_case_traceability",
        "test_cases",
        "test_plans",
        "test_suites",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl};")
    for enum_name in ["tc_trace_kind", "tc_source_kind", "tc_priority", "tc_test_type"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
    # Note: the 'test_cases' value added to artifact_type is intentionally left in
    # place — PostgreSQL cannot easily remove an enum value, and this matches how
    # the FRS/BRD migrations handle enum extension.
