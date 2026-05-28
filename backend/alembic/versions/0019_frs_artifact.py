"""FRS artifact tables: 8 enums + 15 typed tables (Stage A + Stage B).

Stage A tables (7): frs_modules, frs_module_actors, frs_module_responsibilities,
  frs_module_interfaces, frs_module_data_entities, frs_specs (stubs),
  frs_spec_decisions.

Stage B tables (8): frs_screens, frs_ui_components, frs_endpoints, frs_data_entities,
  frs_business_rules, frs_acceptance_scenarios, frs_functional_requirements,
  frs_traceability (NOT versioned).

All versioned tables follow the BRD/CB row mixin pattern. frs_traceability is
replace-all per regen.

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-28
"""
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend artifact_type enum to include 'frs' ────────────────────────────
    # ALTER TYPE ADD VALUE is the simplest path; cannot run inside a transaction
    # by default but Alembic per-op autocommit handles it.
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'frs';
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── New enums ──────────────────────────────────────────────────────────────

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_module_layer AS ENUM ('foundation','vertical','cross_cutting');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_actor_relationship AS ENUM (
                'primary_user','dependency','external_system','downstream_consumer'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_interface_kind AS ENUM ('ui_surface','api','event');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_interface_direction AS ENUM ('inbound','outbound');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_priority AS ENUM ('P0','P1','P2','P3');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_decision_status AS ENUM (
                'open','accepted_ai','overridden','dismissed'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_http_method AS ENUM ('GET','POST','PUT','PATCH','DELETE');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE frs_trace_kind AS ENUM (
                'brd_business_requirement','brd_objective','brd_kpi','brd_risk',
                'brd_text_block','nfr_driver','app_fact','doc_section',
                'discover_qa','within_frs'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ═════════════════════════════════════════════════════════════════════════
    # STAGE A — Module-level tables (5) + spec stub + module decisions
    # ═════════════════════════════════════════════════════════════════════════

    # ── 1. frs_modules ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_modules (
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
            name            TEXT NOT NULL,
            slug            TEXT NOT NULL,
            layer           frs_module_layer NOT NULL DEFAULT 'vertical',
            scope_in        TEXT NOT NULL DEFAULT '',
            scope_out       TEXT NOT NULL DEFAULT '',
            summary         TEXT NOT NULL DEFAULT '',
            figma_root_link TEXT,
            completeness    INTEGER NOT NULL DEFAULT 0,
            confidence      TEXT NOT NULL DEFAULT 'low',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_modules_current ON frs_modules(document_id) WHERE is_current;")

    # ── 2. frs_module_actors ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_module_actors (
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
            module_row_key  TEXT NOT NULL,
            actor_name      TEXT NOT NULL,
            relationship    frs_actor_relationship NOT NULL DEFAULT 'primary_user',
            notes           TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_actors_current ON frs_module_actors(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_actors_module ON frs_module_actors(document_id, module_row_key);")

    # ── 3. frs_module_responsibilities ────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_module_responsibilities (
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
            module_row_key  TEXT NOT NULL,
            responsibility  TEXT NOT NULL,
            frs_refs        JSONB NOT NULL DEFAULT '[]'::jsonb,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_resp_current ON frs_module_responsibilities(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_resp_module ON frs_module_responsibilities(document_id, module_row_key);")

    # ── 4. frs_module_interfaces ──────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_module_interfaces (
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
            module_row_key  TEXT NOT NULL,
            interface_kind  frs_interface_kind NOT NULL,
            direction       frs_interface_direction,
            transport       TEXT,
            name            TEXT NOT NULL,
            counterpart     TEXT,
            user_role       TEXT,
            purpose         TEXT NOT NULL DEFAULT '',
            frs_ref         TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_if_current ON frs_module_interfaces(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_if_module ON frs_module_interfaces(document_id, module_row_key);")

    # ── 5. frs_module_data_entities ───────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_module_data_entities (
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
            entity_name       TEXT NOT NULL,
            business_purpose  TEXT NOT NULL DEFAULT '',
            source_of_truth   TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_de_current ON frs_module_data_entities(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_mod_de_module ON frs_module_data_entities(document_id, module_row_key);")

    # ── 6. frs_specs (stub form in Stage A; full form in Stage B) ─────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_specs (
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
            module_row_key           TEXT NOT NULL,
            title                    TEXT NOT NULL,
            priority                 frs_priority NOT NULL DEFAULT 'P1',
            layer                    frs_module_layer NOT NULL DEFAULT 'vertical',
            br_refs                  JSONB NOT NULL DEFAULT '[]'::jsonb,
            nfr_refs                 JSONB NOT NULL DEFAULT '[]'::jsonb,
            depends_on               JSONB NOT NULL DEFAULT '[]'::jsonb,
            narrative                TEXT NOT NULL DEFAULT '',
            independent_test         TEXT NOT NULL DEFAULT '',
            data_and_validation      TEXT NOT NULL DEFAULT '',
            errors_and_edge_cases    TEXT NOT NULL DEFAULT '',
            observability            TEXT NOT NULL DEFAULT '',
            implementation_tasks     JSONB NOT NULL DEFAULT '[]'::jsonb,
            completeness             INTEGER NOT NULL DEFAULT 0,
            confidence               TEXT NOT NULL DEFAULT 'low',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_specs_current ON frs_specs(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_specs_module ON frs_specs(document_id, module_row_key);")

    # ── 7. frs_spec_decisions ─────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_spec_decisions (
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
            spec_row_key            TEXT,
            module_row_key          TEXT,
            question                TEXT NOT NULL,
            options                 JSONB NOT NULL DEFAULT '[]'::jsonb,
            recommended_index       INTEGER NOT NULL DEFAULT 0,
            recommended_rationale   TEXT NOT NULL DEFAULT '',
            user_chosen_index       INTEGER,
            resolution_status       frs_decision_status NOT NULL DEFAULT 'open',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_dec_current ON frs_spec_decisions(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_dec_status ON frs_spec_decisions(document_id, resolution_status);")

    # ═════════════════════════════════════════════════════════════════════════
    # STAGE B — Spec sub-row tables (7) + traceability
    # ═════════════════════════════════════════════════════════════════════════

    # ── 8. frs_screens ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_screens (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id            UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key                TEXT NOT NULL,
            version                INTEGER NOT NULL CHECK (version > 0),
            is_current             BOOLEAN NOT NULL DEFAULT true,
            is_locked              BOOLEAN NOT NULL DEFAULT false,
            status                 artifact_row_status NOT NULL DEFAULT 'active',
            source                 artifact_row_source NOT NULL,
            created_by             UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            spec_row_key           TEXT NOT NULL,
            screen_name            TEXT NOT NULL,
            figma_link             TEXT,
            purpose                TEXT NOT NULL DEFAULT '',
            user_roles             JSONB NOT NULL DEFAULT '[]'::jsonb,
            layout                 TEXT NOT NULL DEFAULT '',
            navigation             TEXT NOT NULL DEFAULT '',
            interactive_behavior   TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_screens_current ON frs_screens(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_screens_spec ON frs_screens(document_id, spec_row_key);")

    # ── 9. frs_ui_components ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_ui_components (
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
            spec_row_key    TEXT NOT NULL,
            screen_row_key  TEXT NOT NULL,
            component_name  TEXT NOT NULL,
            component_type  TEXT NOT NULL DEFAULT 'input',
            definition      JSONB NOT NULL DEFAULT '{}'::jsonb,
            behavior        JSONB NOT NULL DEFAULT '{}'::jsonb,
            validation      JSONB NOT NULL DEFAULT '{}'::jsonb,
            actions         JSONB NOT NULL DEFAULT '[]'::jsonb,
            data_mapping    JSONB NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_ui_comp_current ON frs_ui_components(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_ui_comp_spec ON frs_ui_components(document_id, spec_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_ui_comp_screen ON frs_ui_components(document_id, screen_row_key);")

    # ── 10. frs_endpoints ─────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_endpoints (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id         UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key             TEXT NOT NULL,
            version             INTEGER NOT NULL CHECK (version > 0),
            is_current          BOOLEAN NOT NULL DEFAULT true,
            is_locked           BOOLEAN NOT NULL DEFAULT false,
            status              artifact_row_status NOT NULL DEFAULT 'active',
            source              artifact_row_source NOT NULL,
            created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            spec_row_key        TEXT NOT NULL,
            service_name        TEXT NOT NULL DEFAULT '',
            endpoint_name       TEXT NOT NULL,
            url                 TEXT NOT NULL DEFAULT '',
            protocol            TEXT NOT NULL DEFAULT 'HTTPS',
            method              frs_http_method NOT NULL DEFAULT 'POST',
            sync_async          TEXT NOT NULL DEFAULT 'sync',
            idempotent          BOOLEAN NOT NULL DEFAULT false,
            request_spec        JSONB NOT NULL DEFAULT '{}'::jsonb,
            response_spec       JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_handling      JSONB NOT NULL DEFAULT '{}'::jsonb,
            security            JSONB NOT NULL DEFAULT '{}'::jsonb,
            operational         JSONB NOT NULL DEFAULT '{}'::jsonb,
            integration_target  TEXT,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_endpoints_current ON frs_endpoints(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_endpoints_spec ON frs_endpoints(document_id, spec_row_key);")

    # ── 11. frs_data_entities ─────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_data_entities (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id        UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            row_key            TEXT NOT NULL,
            version            INTEGER NOT NULL CHECK (version > 0),
            is_current         BOOLEAN NOT NULL DEFAULT true,
            is_locked          BOOLEAN NOT NULL DEFAULT false,
            status             artifact_row_status NOT NULL DEFAULT 'active',
            source             artifact_row_source NOT NULL,
            created_by         UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            spec_row_key       TEXT NOT NULL,
            entity_name        TEXT NOT NULL,
            data_store_type    TEXT NOT NULL DEFAULT 'RDBMS',
            description        TEXT NOT NULL DEFAULT '',
            expected_volume    TEXT NOT NULL DEFAULT '',
            columns            JSONB NOT NULL DEFAULT '[]'::jsonb,
            keys_constraints   JSONB NOT NULL DEFAULT '{}'::jsonb,
            indexes            JSONB NOT NULL DEFAULT '[]'::jsonb,
            relationships      JSONB NOT NULL DEFAULT '[]'::jsonb,
            access_logic       TEXT NOT NULL DEFAULT '',
            cache_spec         JSONB,
            retention_policy   TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_data_ent_current ON frs_data_entities(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_data_ent_spec ON frs_data_entities(document_id, spec_row_key);")

    # ── 12. frs_business_rules ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_business_rules (
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
            spec_row_key    TEXT NOT NULL,
            rule_id         TEXT NOT NULL,
            description     TEXT NOT NULL,
            applies_to      TEXT NOT NULL DEFAULT '',
            logic_decision  TEXT NOT NULL DEFAULT '',
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_br_current ON frs_business_rules(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_br_spec ON frs_business_rules(document_id, spec_row_key);")

    # ── 13. frs_acceptance_scenarios ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_acceptance_scenarios (
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
            spec_row_key     TEXT NOT NULL,
            scenario_index   INTEGER NOT NULL DEFAULT 1,
            "given"          TEXT NOT NULL,
            "when"           TEXT NOT NULL,
            "then"           TEXT NOT NULL,
            is_negative      BOOLEAN NOT NULL DEFAULT false,
            fr_refs          JSONB NOT NULL DEFAULT '[]'::jsonb,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_as_current ON frs_acceptance_scenarios(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_as_spec ON frs_acceptance_scenarios(document_id, spec_row_key);")

    # ── 14. frs_functional_requirements ───────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_functional_requirements (
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
            spec_row_key      TEXT NOT NULL,
            fr_id             TEXT NOT NULL,
            requirement_text  TEXT NOT NULL,
            scenario_refs     JSONB NOT NULL DEFAULT '[]'::jsonb,
            UNIQUE (document_id, row_key, version)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_fr_current ON frs_functional_requirements(document_id) WHERE is_current;")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_fr_spec ON frs_functional_requirements(document_id, spec_row_key);")

    # ── 15. frs_traceability (NOT versioned) ──────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS frs_traceability (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id     UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
            source_table    TEXT NOT NULL,
            source_row_key  TEXT NOT NULL,
            target_kind     frs_trace_kind NOT NULL,
            target_ref      TEXT NOT NULL,
            target_label    TEXT NOT NULL DEFAULT '',
            confidence      TEXT NOT NULL DEFAULT 'high',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_traceability_doc ON frs_traceability(document_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_traceability_source ON frs_traceability(document_id, source_table, source_row_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_frs_traceability_target ON frs_traceability(document_id, target_kind, target_ref);")


def downgrade() -> None:
    # Drop tables in reverse dependency order (none have FKs between them within FRS,
    # but listed in reverse-create order for symmetry)
    for tbl in [
        "frs_traceability",
        "frs_functional_requirements",
        "frs_acceptance_scenarios",
        "frs_business_rules",
        "frs_data_entities",
        "frs_endpoints",
        "frs_ui_components",
        "frs_screens",
        "frs_spec_decisions",
        "frs_specs",
        "frs_module_data_entities",
        "frs_module_interfaces",
        "frs_module_responsibilities",
        "frs_module_actors",
        "frs_modules",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {tbl};")
    for enum_name in [
        "frs_trace_kind", "frs_http_method", "frs_decision_status",
        "frs_priority", "frs_interface_direction", "frs_interface_kind",
        "frs_actor_relationship", "frs_module_layer",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
