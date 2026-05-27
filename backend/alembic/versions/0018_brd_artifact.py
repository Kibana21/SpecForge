"""BRD artifact tables: enums, 21 typed tables, traceability.

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-27
"""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New enums ──────────────────────────────────────────────────────────────

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_priority AS ENUM ('must','should','could','wont');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_category AS ENUM (
                'functional','non_functional','data','integration',
                'reporting','compliance','operational'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_trace_kind AS ENUM (
                'cb_text_block','cb_outcome','cb_metric','cb_capability',
                'cb_scope_item','cb_milestone','app_fact','doc_section',
                'discover_qa','within_brd'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_risk_severity AS ENUM ('critical','high','medium','low');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_risk_likelihood AS ENUM ('high','medium','low');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_stakeholder_type AS ENUM (
                'sponsor','owner','user','operations','compliance','technical','external'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE brd_process_step_type AS ENUM ('asis','tobe');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── §1–2: Prose text blocks ────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_text_blocks (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key     TEXT NOT NULL,
            version     INTEGER NOT NULL CHECK (version > 0),
            is_current  BOOLEAN NOT NULL DEFAULT true,
            is_locked   BOOLEAN NOT NULL DEFAULT false,
            status      artifact_row_status NOT NULL DEFAULT 'active',
            source      artifact_row_source NOT NULL,
            created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            field_key   TEXT NOT NULL,
            text        TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_text_blocks_current ON brd_text_blocks(document_id) WHERE is_current;")

    # ── §3: Objectives ─────────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_objectives (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key         TEXT NOT NULL,
            version         INTEGER NOT NULL CHECK (version > 0),
            is_current      BOOLEAN NOT NULL DEFAULT true,
            is_locked       BOOLEAN NOT NULL DEFAULT false,
            status          artifact_row_status NOT NULL DEFAULT 'active',
            source          artifact_row_source NOT NULL,
            created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            statement       TEXT NOT NULL,
            category        TEXT NOT NULL DEFAULT 'strategic',
            priority        brd_priority NOT NULL DEFAULT 'must',
            owner           TEXT NOT NULL DEFAULT '',
            cb_outcome_ref  TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_objectives_current ON brd_objectives(document_id) WHERE is_current;")

    # ── §4: Stakeholders & Actors ──────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_stakeholders (
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
            name              TEXT NOT NULL,
            stakeholder_type  brd_stakeholder_type NOT NULL DEFAULT 'user',
            role              TEXT NOT NULL DEFAULT '',
            interest          TEXT NOT NULL DEFAULT '',
            influence         TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_stakeholders_current ON brd_stakeholders(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_actors (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key      TEXT NOT NULL,
            version      INTEGER NOT NULL CHECK (version > 0),
            is_current   BOOLEAN NOT NULL DEFAULT true,
            is_locked    BOOLEAN NOT NULL DEFAULT false,
            status       artifact_row_status NOT NULL DEFAULT 'active',
            source       artifact_row_source NOT NULL,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            name         TEXT NOT NULL,
            actor_type   TEXT NOT NULL DEFAULT 'human',
            description  TEXT NOT NULL DEFAULT '',
            interactions TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_actors_current ON brd_actors(document_id) WHERE is_current;")

    # ── §5: Scope ──────────────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_scope_items (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id   UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key       TEXT NOT NULL,
            version       INTEGER NOT NULL CHECK (version > 0),
            is_current    BOOLEAN NOT NULL DEFAULT true,
            is_locked     BOOLEAN NOT NULL DEFAULT false,
            status        artifact_row_status NOT NULL DEFAULT 'active',
            source        artifact_row_source NOT NULL,
            created_by    UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            kind          TEXT NOT NULL,
            text          TEXT NOT NULL,
            rationale     TEXT NOT NULL DEFAULT '',
            cb_scope_ref  TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_scope_items_current ON brd_scope_items(document_id) WHERE is_current;")

    # ── §6: Process Steps ─────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_process_steps (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key      TEXT NOT NULL,
            version      INTEGER NOT NULL CHECK (version > 0),
            is_current   BOOLEAN NOT NULL DEFAULT true,
            is_locked    BOOLEAN NOT NULL DEFAULT false,
            status       artifact_row_status NOT NULL DEFAULT 'active',
            source       artifact_row_source NOT NULL,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            step_type    brd_process_step_type NOT NULL,
            step_number  INTEGER NOT NULL DEFAULT 1,
            actor        TEXT NOT NULL DEFAULT '',
            action       TEXT NOT NULL,
            pain_point   TEXT,
            improvement  TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_process_steps_current ON brd_process_steps(document_id) WHERE is_current;")

    # ── §7: Business Requirements (keystone) ──────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_business_requirements (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id          UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key              TEXT NOT NULL,
            version              INTEGER NOT NULL CHECK (version > 0),
            is_current           BOOLEAN NOT NULL DEFAULT true,
            is_locked            BOOLEAN NOT NULL DEFAULT false,
            status               artifact_row_status NOT NULL DEFAULT 'active',
            source               artifact_row_source NOT NULL,
            created_by           UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            title                TEXT NOT NULL,
            description          TEXT NOT NULL DEFAULT '',
            priority             brd_priority NOT NULL DEFAULT 'must',
            category             brd_category NOT NULL DEFAULT 'functional',
            acceptance_criteria  JSONB NOT NULL DEFAULT '[]',
            objective_refs       JSONB NOT NULL DEFAULT '[]',
            stakeholder_refs     JSONB NOT NULL DEFAULT '[]',
            rationale            TEXT NOT NULL DEFAULT '',
            completeness         INTEGER NOT NULL DEFAULT 0,
            confidence           TEXT NOT NULL DEFAULT 'low',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_br_current ON brd_business_requirements(document_id) WHERE is_current;")

    # ── §8: Data & Reporting ──────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_data_entities (
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
            entity_name       TEXT NOT NULL,
            description       TEXT NOT NULL DEFAULT '',
            owner_system      TEXT NOT NULL DEFAULT '',
            data_sensitivity  TEXT NOT NULL DEFAULT 'standard',
            key_attributes    JSONB NOT NULL DEFAULT '[]',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_data_entities_current ON brd_data_entities(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_report_requirements (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key      TEXT NOT NULL,
            version      INTEGER NOT NULL CHECK (version > 0),
            is_current   BOOLEAN NOT NULL DEFAULT true,
            is_locked    BOOLEAN NOT NULL DEFAULT false,
            status       artifact_row_status NOT NULL DEFAULT 'active',
            source       artifact_row_source NOT NULL,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            report_name  TEXT NOT NULL,
            description  TEXT NOT NULL DEFAULT '',
            audience     TEXT NOT NULL DEFAULT '',
            frequency    TEXT NOT NULL DEFAULT '',
            key_metrics  JSONB NOT NULL DEFAULT '[]',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_report_req_current ON brd_report_requirements(document_id) WHERE is_current;")

    # ── §9: Assumptions, Constraints, Dependencies ────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_assumptions (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id      UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key          TEXT NOT NULL,
            version          INTEGER NOT NULL CHECK (version > 0),
            is_current       BOOLEAN NOT NULL DEFAULT true,
            is_locked        BOOLEAN NOT NULL DEFAULT false,
            status           artifact_row_status NOT NULL DEFAULT 'active',
            source           artifact_row_source NOT NULL,
            created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            assumption       TEXT NOT NULL,
            impact_if_wrong  TEXT NOT NULL DEFAULT '',
            owner            TEXT NOT NULL DEFAULT '',
            cb_scope_ref     TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_assumptions_current ON brd_assumptions(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_constraints (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id      UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key          TEXT NOT NULL,
            version          INTEGER NOT NULL CHECK (version > 0),
            is_current       BOOLEAN NOT NULL DEFAULT true,
            is_locked        BOOLEAN NOT NULL DEFAULT false,
            status           artifact_row_status NOT NULL DEFAULT 'active',
            source           artifact_row_source NOT NULL,
            created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            constraint_text  TEXT NOT NULL,
            constraint_type  TEXT NOT NULL DEFAULT 'business',
            source_ref       TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_constraints_current ON brd_constraints(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_dependencies (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id      UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key          TEXT NOT NULL,
            version          INTEGER NOT NULL CHECK (version > 0),
            is_current       BOOLEAN NOT NULL DEFAULT true,
            is_locked        BOOLEAN NOT NULL DEFAULT false,
            status           artifact_row_status NOT NULL DEFAULT 'active',
            source           artifact_row_source NOT NULL,
            created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            dependency       TEXT NOT NULL,
            dependency_type  TEXT NOT NULL DEFAULT 'external',
            owner            TEXT NOT NULL DEFAULT '',
            due_date         TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_dependencies_current ON brd_dependencies(document_id) WHERE is_current;")

    # ── §10: Risks ────────────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_risks (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key      TEXT NOT NULL,
            version      INTEGER NOT NULL CHECK (version > 0),
            is_current   BOOLEAN NOT NULL DEFAULT true,
            is_locked    BOOLEAN NOT NULL DEFAULT false,
            status       artifact_row_status NOT NULL DEFAULT 'active',
            source       artifact_row_source NOT NULL,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            risk         TEXT NOT NULL,
            description  TEXT NOT NULL DEFAULT '',
            severity     brd_risk_severity NOT NULL DEFAULT 'medium',
            likelihood   brd_risk_likelihood NOT NULL DEFAULT 'medium',
            mitigation   TEXT NOT NULL DEFAULT '',
            owner        TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_risks_current ON brd_risks(document_id) WHERE is_current;")

    # ── §11: Implementation & Phasing ─────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_phases (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id      UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key          TEXT NOT NULL,
            version          INTEGER NOT NULL CHECK (version > 0),
            is_current       BOOLEAN NOT NULL DEFAULT true,
            is_locked        BOOLEAN NOT NULL DEFAULT false,
            status           artifact_row_status NOT NULL DEFAULT 'active',
            source           artifact_row_source NOT NULL,
            created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            phase_name       TEXT NOT NULL,
            description      TEXT NOT NULL DEFAULT '',
            target_date      TEXT NOT NULL DEFAULT '',
            included_br_refs JSONB NOT NULL DEFAULT '[]',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_phases_current ON brd_phases(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_milestones (
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
            milestone         TEXT NOT NULL,
            target            TEXT NOT NULL DEFAULT '',
            description       TEXT NOT NULL DEFAULT '',
            phase_ref         TEXT,
            cb_milestone_ref  TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_milestones_current ON brd_milestones(document_id) WHERE is_current;")

    # ── §12: KPIs ─────────────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_kpis (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key         TEXT NOT NULL,
            version         INTEGER NOT NULL CHECK (version > 0),
            is_current      BOOLEAN NOT NULL DEFAULT true,
            is_locked       BOOLEAN NOT NULL DEFAULT false,
            status          artifact_row_status NOT NULL DEFAULT 'active',
            source          artifact_row_source NOT NULL,
            created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            kpi_name        TEXT NOT NULL,
            description     TEXT NOT NULL DEFAULT '',
            baseline        TEXT NOT NULL DEFAULT '',
            target          TEXT NOT NULL DEFAULT '',
            timeframe       TEXT NOT NULL DEFAULT '',
            data_source     TEXT NOT NULL DEFAULT '',
            objective_ref   TEXT,
            cb_metric_ref   TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_kpis_current ON brd_kpis(document_id) WHERE is_current;")

    # ── §13: Open Questions & Decisions ───────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_open_questions (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key      TEXT NOT NULL,
            version      INTEGER NOT NULL CHECK (version > 0),
            is_current   BOOLEAN NOT NULL DEFAULT true,
            is_locked    BOOLEAN NOT NULL DEFAULT false,
            status       artifact_row_status NOT NULL DEFAULT 'active',
            source       artifact_row_source NOT NULL,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            question     TEXT NOT NULL,
            context      TEXT NOT NULL DEFAULT '',
            owner        TEXT NOT NULL DEFAULT '',
            due_date     TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_open_q_current ON brd_open_questions(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_decisions (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id              UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key                  TEXT NOT NULL,
            version                  INTEGER NOT NULL CHECK (version > 0),
            is_current               BOOLEAN NOT NULL DEFAULT true,
            is_locked                BOOLEAN NOT NULL DEFAULT false,
            status                   artifact_row_status NOT NULL DEFAULT 'active',
            source                   artifact_row_source NOT NULL,
            created_by               UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
            decision                 TEXT NOT NULL,
            rationale                TEXT NOT NULL DEFAULT '',
            owner                    TEXT NOT NULL DEFAULT '',
            decision_date            TEXT NOT NULL DEFAULT '',
            alternatives_considered  TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_decisions_current ON brd_decisions(document_id) WHERE is_current;")

    # ── §14: References & Glossary ────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_references (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key         TEXT NOT NULL,
            version         INTEGER NOT NULL CHECK (version > 0),
            is_current      BOOLEAN NOT NULL DEFAULT true,
            is_locked       BOOLEAN NOT NULL DEFAULT false,
            status          artifact_row_status NOT NULL DEFAULT 'active',
            source          artifact_row_source NOT NULL,
            created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            title           TEXT NOT NULL,
            reference_type  TEXT NOT NULL DEFAULT 'document',
            location        TEXT NOT NULL DEFAULT '',
            description     TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_references_current ON brd_references(document_id) WHERE is_current;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_glossary_entries (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id  UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key      TEXT NOT NULL,
            version      INTEGER NOT NULL CHECK (version > 0),
            is_current   BOOLEAN NOT NULL DEFAULT true,
            is_locked    BOOLEAN NOT NULL DEFAULT false,
            status       artifact_row_status NOT NULL DEFAULT 'active',
            source       artifact_row_source NOT NULL,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            term         TEXT NOT NULL,
            definition   TEXT NOT NULL,
            source_ref   TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_glossary_current ON brd_glossary_entries(document_id) WHERE is_current;")

    # ── Traceability ──────────────────────────────────────────────────────────

    op.execute("""
        CREATE TABLE IF NOT EXISTS brd_traceability (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            source_table    TEXT NOT NULL,
            source_row_key  TEXT NOT NULL,
            target_kind     brd_trace_kind NOT NULL,
            target_ref      TEXT NOT NULL,
            target_label    TEXT NOT NULL DEFAULT '',
            confidence      TEXT NOT NULL DEFAULT 'high',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_traceability_doc ON brd_traceability(document_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_brd_traceability_source_row ON brd_traceability(document_id, source_row_key);")


def downgrade() -> None:
    for tbl in [
        "brd_traceability", "brd_glossary_entries", "brd_references",
        "brd_decisions", "brd_open_questions", "brd_kpis", "brd_milestones",
        "brd_phases", "brd_risks", "brd_dependencies", "brd_constraints",
        "brd_assumptions", "brd_report_requirements", "brd_data_entities",
        "brd_business_requirements", "brd_process_steps", "brd_scope_items",
        "brd_actors", "brd_stakeholders", "brd_objectives", "brd_text_blocks",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl};")
    for enum in [
        "brd_process_step_type", "brd_stakeholder_type", "brd_risk_likelihood",
        "brd_risk_severity", "brd_trace_kind", "brd_category", "brd_priority",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum};")
