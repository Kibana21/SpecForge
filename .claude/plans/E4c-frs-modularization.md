# E4c · Part 1 — FRS Modularization · Implementation Plan

> **Companion to** `.claude/prd/prd-e4c-frs-modularization.md` (the product spec). That doc
> describes WHAT to build; this doc describes HOW — file by file, schema by schema, with
> the visual design language and the rugged-backend invariants spelled out.
>
> **Stage A** of the FRS Builder pipeline: decompose the validated BRD into 5–12
> business-capability modules using DDD bounded contexts. Each module owns scope, actors,
> responsibilities, interfaces (UI/APIs/events), data ownership, and an FRS backlog. Stage B
> (per-module FRS authoring) consumes the output of this stage and is planned separately in
> `E4c-frs-functional-design.md`.
>
> **Two product principles drive every decision below**:
>   - **Rugged backend**: idempotent generation, atomic JSONB merges, transactional row
>     upserts, row-level locking, soft-delete by status, mock-first DSPy, dispose-per-task
>     connection pool, optimistic concurrency on edits, no N+1 queries.
>   - **Brilliant UI**: provenance everywhere (chips, popovers), progressive disclosure,
>     visual hierarchy by Layer, "construction site" generation theater, inline editing with
>     optimistic updates, calm density, purposeful motion that respects `useReducedMotion()`.

---

## 1. Context & overview

### 1.1 Where this fits

```
RU ──validated──▶ Concept Brief (E4a) ──validated──▶ BRD (E4b) ──validated──▶ FRS (E4c)
                                                                                   │
                                                                                   ├──▶ Stage A: Modularization  ← THIS PLAN
                                                                                   └──▶ Stage B: Functional Design (E4c-2)
```

The "claims chatbot" project already has a validated BRD with 14 BRs, 6 objectives, 5 risks,
4 KPIs across 22 typed tables. This plan turns that into a structured set of modules ready
for per-module FRS design.

### 1.2 The "two skills, one pipeline" mental model

The FRS-Builder skill at `reference_mds/skills/frs-builder/SKILL.md` defines two sub-skills:

```
┌─ STAGE A (this plan) ────────────────┐    ┌─ STAGE B (E4c-2 plan) ─────────────┐
│ modularize.md                         │    │ functional-design.md + frs-template │
│                                       │    │                                     │
│ INPUT:  validated BRD + apps + docs + │    │ INPUT:  module + corpus + figma     │
│         CB + 7 discover Qs            │ ─▶ │         link + resolved decisions   │
│                                       │    │                                     │
│ OUTPUT: 5–12 modules with             │    │ OUTPUT: full FRS spec per stub:     │
│         - scope/actors/responsib.     │    │         - narrative, UI, backend,   │
│         - interfaces (UI/APIs/evts)   │    │           data, business rules,     │
│         - data ownership              │    │           ≥6 scenarios, FRs, traces │
│         - FRS backlog stubs           │    │                                     │
│                                       │    │                                     │
│ TIME:   single DSPy call (~30–60s)    │    │ TIME:   N parallel DSPy calls       │
└──────────────────────────────────────┘    └────────────────────────────────────┘
```

This plan covers ONLY Stage A. Stage B's plan lives in `E4c-frs-functional-design.md`.

### 1.3 Reuses (and what's new)

| Concept | Source | Reuse approach |
|---------|--------|----------------|
| `ArtifactDocument` shell | E4a/E4b | New row with `artifact_type='frs'` |
| `ArtifactMessage` Q&A thread | E4a/E4b | Used for question/user/synthesis/figma_link_required/spec_decision_open |
| `VersionedRowMixin` | E4a/E4b | Inherited by all 6 Stage-A row tables |
| Atomic JSONB `unit_status` merge | E4b | Same `||` pattern; `_current_unit` for theater |
| Mock-first DSPy + fixture loader | E4a/E4b | New fixture `brd_modularize.json`; `_load_fixture("frs_modularize")` |
| `EditableRows` component | E4b | Inline edit/lock/version semantics for module sub-rows |
| `DiscoverPhase` component | E5 | New catalog routing; same UI shell |
| `FindingsDrawer` shape | E4b | New `FrsModularizeFindings` with Stage-A-only groups |
| `BrdConfettiBurst` | E4b | Reused on "Continue to Stage 2" success |
| `SourceStrip` component | E4b | **Extended** with a 4th BRD layer |
| Two-step validate pattern | E4b | "Check & Validate" (GET) → drawer → "Continue to Stage 2" (POST commits Stage-A transition) |
| Per-task Celery session disposal | E1 inf | `_run_async()` wrapper — no shared sessions |

**Genuinely new** (no analog in existing code):
1. `BrdLayer` in the context bundle (parallel to `CbLayer`)
2. Hierarchical FRS data model (modules → backlog stubs vs BRD's flat 21 tables)
3. Module-rail navigation primitive (vs BRD's section rail)
4. Module Identity Card with Layer indicator
5. Construction-site generation theater (sequential narrative vs BRD's DAG visualisation)
6. Cross-module contract mini-graph viz
7. Layer-0 hoisting logic (auto-creating MOD-000 Cross-cutting Standards)

---

## 2. Architecture & key design decisions

### 2.1 Layered data model

```
ArtifactDocument (artifact_type='frs', status='generating'|'in_interview'|'validated')
  │
  ├── ArtifactMessage[]   (the Q&A thread — shared with Stage B)
  ├── ArtifactSource[]    (which project docs are in scope)
  │
  ├── FrsModule[]                  ──► one per business capability (MOD-000 to MOD-014)
  │     ├── FrsModuleActor[]       ──► capability/role actors + external systems
  │     ├── FrsModuleResponsibility[]
  │     ├── FrsModuleInterface[]   ──► UI surfaces + APIs (inbound/outbound) + events
  │     └── FrsModuleDataEntity[]  ──► owned data (conceptual; schema in Stage B)
  │
  ├── FrsSpec[]                    ──► one per backlog stub (M001-FRS001, …)
  │                                    Stage A creates STUBS only (completeness=0,
  │                                    empty narrative; Stage B fills out)
  │
  └── FrsSpecDecision[]            ──► module-scoped [SPEC-DECISION] MCQs
                                       (spec-scoped come in Stage B)
```

### 2.2 The 5 design decisions baked into Stage A

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Auto-cascade Stage A → Stage B** by default | Matches BRD's seamless experience; explicit "Continue to Stage 2" remains as a confirm gate when user wants to review modules first |
| 2 | **[SPEC-DECISION] non-blocking** | AI picks `recommended_index` and proceeds; user confirms/overrides later. Open decisions become warnings, not majors |
| 3 | **Cross-cutting Standards module: AI-decided** | When the LLM detects ≥2 modules sharing rules, it hoists into MOD-000. User can override via "Edit module" or "Delete module" |
| 4 | **BR coverage: Must-priority required** | Validator coverage check enforces only `priority='must'` BRs; Should/Could/Wont surface as warnings |
| 5 | **NFR + Architecture: project docs only** | PageIndex-indexed `nfr*`, `architecture*`, `technical-design*` filenames; no formal NFR artifact yet |

### 2.3 Rugged backend invariants (non-negotiable)

These invariants are inherited from BRD's proven patterns. Every implementation step in §3
must satisfy them:

1. **Atomicity per row table**: `upsert_frs_rows()` uses `db.begin_nested()` savepoint per
   module-row group so a single bad row doesn't poison the whole module persistence.
2. **JSONB `unit_status` merge is atomic**: every progress update uses
   `SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb)` so
   concurrent unit writes never clobber each other.
3. **Idempotency**: re-running modularize with no input changes must produce zero new versions.
   This requires deterministic row_key generation and stable Pydantic field ordering.
4. **Lock semantics**: rows with `is_locked=True` are preserved verbatim through all
   regenerations (the DSPy Signature receives them as `locked_modules` JSON; the orchestrator
   reapplies them post-LLM if the AI ignores the instruction).
5. **Soft delete only**: never `DELETE FROM frs_modules` in code paths; use
   `status='removed'`. Hard delete restricted to platform_admin via separate endpoint
   `POST /frs/{table}/{row_id}/destroy` (out of scope for v1).
6. **Per-Celery-task session**: every Celery task uses `_run_async()` which `engine.dispose()`s
   after — prevents "Future attached to different loop" errors.
7. **Mock-first**: every DSPy call has a `_is_mock()` short-circuit that returns a fixture.
   Tests run with `LLM_PROVIDER=mock`; zero Vertex calls.
8. **Optimistic concurrency on edits**: `edit_frs_row` accepts an optional `expected_version`
   and rejects with 409 if the current version is higher (prevents lost-update on concurrent
   edits in different browser tabs).
9. **Migration safety**: `IF NOT EXISTS` on every CREATE; `DO $$ ... EXCEPTION WHEN
   duplicate_object` on every enum; reversible downgrade.
10. **Audit-light**: every AI generation logs `brd.generate.{unit_key}` audit event with row
    counts; every human edit logs `frs.row.edit` with diff; validation logs `frs.validate.run`
    with finding counts.

### 2.4 Brilliant UI principles (the UX north stars)

1. **Provenance is the product**: every module shows its BR sources as colored chips; every
   backlog stub shows its trace chips; every interface shows its target/source module.
2. **Hierarchy via Layer is obvious**: Layer 0 (foundation) gets a distinct visual treatment
   (parchment border, foundation icon), Layer 1 (vertical) gets the accent green, Layer 2
   (cross-cutting) gets sky blue.
3. **State is felt**: the construction-site theater shows 5 sequential sub-steps the LLM is
   internally doing (identifying contexts → validating boundaries → mapping contracts →
   generating backlog → hoisting cross-cutting).
4. **Editing is frictionless**: every row uses inline edit with optimistic update + version
   bump + "Saved ✓" toast. No "Save" buttons except in modals.
5. **Locks are reassuring**: locked rows show 🔒 + accent ring on hover; tooltip "Locked —
   will be preserved on regenerate. Click to unlock."
6. **Findings are actionable**: each finding has a one-click "Accept fix" (where mechanical),
   "Jump to row" (smooth-scroll + 600ms red pulse), or "Edit manually" (opens row editor).
7. **Density is calm**: module rail collapses by default; module panel sections collapsed
   except scope; backlog stub bodies collapsed except priority+BR chips.
8. **Motion is purposeful**:
   - 280ms ease-out for state transitions (dot fills, chip appears)
   - 600ms ease-in-out for smooth-scroll anchoring + section title pulse
   - 180ms ease-out for hover popovers (Radix default)
   - All gated by `useReducedMotion()`

---

## 3. Backend — rugged orchestration (detailed file plan)

### 3.1 Data model + Alembic migration

**File**: `backend/app/models/frs.py` (NEW)

```python
"""FRS artifact models — modules + backlog stubs (Stage A) + spec sub-rows (Stage B).

All tables use VersionedRowMixin for row-level versioning + locking + soft-delete.
FrsTraceability is NOT versioned (replace-all semantics).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column, ForeignKey, Integer, String, Text, Boolean,
    JSON, DateTime, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.artifact import VersionedRowMixin


# ── Enums (created in migration; re-used here as SQLAlchemy column types) ──────

FrsModuleLayer = ENUM(
    "foundation", "vertical", "cross_cutting",
    name="frs_module_layer", create_type=False,
)
FrsActorRelationship = ENUM(
    "primary_user", "dependency", "external_system", "downstream_consumer",
    name="frs_actor_relationship", create_type=False,
)
FrsInterfaceKind = ENUM(
    "ui_surface", "api", "event",
    name="frs_interface_kind", create_type=False,
)
FrsInterfaceDirection = ENUM(
    "inbound", "outbound",
    name="frs_interface_direction", create_type=False,
)
FrsPriority = ENUM(
    "P0", "P1", "P2", "P3",
    name="frs_priority", create_type=False,
)
FrsDecisionStatus = ENUM(
    "open", "accepted_ai", "overridden", "dismissed",
    name="frs_decision_status", create_type=False,
)
FrsHttpMethod = ENUM(
    "GET", "POST", "PUT", "PATCH", "DELETE",
    name="frs_http_method", create_type=False,
)
FrsTraceKind = ENUM(
    "brd_business_requirement", "brd_objective", "brd_kpi", "brd_risk",
    "brd_text_block", "nfr_driver", "app_fact", "doc_section",
    "discover_qa", "within_frs",
    name="frs_trace_kind", create_type=False,
)


# ── 1. frs_modules ─────────────────────────────────────────────────────────────

class FrsModule(Base, VersionedRowMixin):
    __tablename__ = "frs_modules"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str] = mapped_column(FrsModuleLayer, nullable=False)
    scope_in: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scope_out: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    figma_root_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[str] = mapped_column(String(8), default="low", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_modules_doc_key_ver"),
        Index("ix_frs_modules_doc_current", "document_id", "is_current"),
        Index("ix_frs_modules_doc_status", "document_id", "status"),
    )


# ── 2. frs_module_actors ───────────────────────────────────────────────────────

class FrsModuleActor(Base, VersionedRowMixin):
    __tablename__ = "frs_module_actors"

    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    actor_name: Mapped[str] = mapped_column(Text, nullable=False)
    relationship: Mapped[str] = mapped_column(FrsActorRelationship, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_actors_doc_key_ver"),
        Index("ix_frs_mod_actors_doc_module", "document_id", "module_row_key"),
    )


# ── 3. frs_module_responsibilities ─────────────────────────────────────────────

class FrsModuleResponsibility(Base, VersionedRowMixin):
    __tablename__ = "frs_module_responsibilities"

    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    responsibility: Mapped[str] = mapped_column(Text, nullable=False)
    frs_refs: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_resp_doc_key_ver"),
        Index("ix_frs_mod_resp_doc_module", "document_id", "module_row_key"),
    )


# ── 4. frs_module_interfaces ───────────────────────────────────────────────────

class FrsModuleInterface(Base, VersionedRowMixin):
    __tablename__ = "frs_module_interfaces"

    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    interface_kind: Mapped[str] = mapped_column(FrsInterfaceKind, nullable=False)
    direction: Mapped[str | None] = mapped_column(FrsInterfaceDirection, nullable=True)
    transport: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    counterpart: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    frs_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_if_doc_key_ver"),
        Index("ix_frs_mod_if_doc_module", "document_id", "module_row_key"),
    )


# ── 5. frs_module_data_entities ────────────────────────────────────────────────

class FrsModuleDataEntity(Base, VersionedRowMixin):
    __tablename__ = "frs_module_data_entities"

    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    business_purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_of_truth: Mapped[str] = mapped_column(Text, default="", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_de_doc_key_ver"),
        Index("ix_frs_mod_de_doc_module", "document_id", "module_row_key"),
    )


# ── 6. frs_specs (stub form in Stage A; full form in Stage B) ──────────────────

class FrsSpec(Base, VersionedRowMixin):
    __tablename__ = "frs_specs"

    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(FrsPriority, nullable=False)
    layer: Mapped[str] = mapped_column(FrsModuleLayer, nullable=False)
    br_refs: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    nfr_refs: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, default="", nullable=False)
    independent_test: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_and_validation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    errors_and_edge_cases: Mapped[str] = mapped_column(Text, default="", nullable=False)
    observability: Mapped[str] = mapped_column(Text, default="", nullable=False)
    implementation_tasks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    completeness: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[str] = mapped_column(String(8), default="low", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_specs_doc_key_ver"),
        Index("ix_frs_specs_doc_current", "document_id", "is_current"),
        Index("ix_frs_specs_doc_module", "document_id", "module_row_key"),
    )


# ── 7. frs_spec_decisions ──────────────────────────────────────────────────────

class FrsSpecDecision(Base, VersionedRowMixin):
    __tablename__ = "frs_spec_decisions"

    spec_row_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    module_row_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    recommended_index: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_chosen_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_status: Mapped[str] = mapped_column(FrsDecisionStatus, default="open", nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_dec_doc_key_ver"),
        Index("ix_frs_dec_doc_status", "document_id", "resolution_status"),
    )


# Stage B's 8 sub-row tables (frs_screens, frs_ui_components, frs_endpoints,
# frs_data_entities, frs_business_rules, frs_acceptance_scenarios,
# frs_functional_requirements, frs_traceability) are defined in the same migration
# but only their model classes — Stage A doesn't write to them. See E4c-frs-functional-design.md.
```

**File**: `backend/app/alembic/versions/0019_frs_artifact.py` (NEW)

The migration creates **all 14 tables** + 8 enums in one atomic operation, even though Stage A
uses only 7. This avoids a follow-up migration when Stage B ships.

```python
"""FRS artifact: 14 tables + 8 enums for both Stage A (modularize) and Stage B (design).

Revision: 0019
Revises: 0018 (BRD)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0019"
down_revision = "0018"


def upgrade() -> None:
    # ── 1. Create enums (with duplicate-safety) ─────────────────────────────────
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_module_layer AS ENUM ('foundation', 'vertical', 'cross_cutting');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_actor_relationship AS ENUM
            ('primary_user', 'dependency', 'external_system', 'downstream_consumer');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_interface_kind AS ENUM ('ui_surface', 'api', 'event');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_interface_direction AS ENUM ('inbound', 'outbound');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_priority AS ENUM ('P0', 'P1', 'P2', 'P3');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_decision_status AS ENUM
            ('open', 'accepted_ai', 'overridden', 'dismissed');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_http_method AS ENUM ('GET', 'POST', 'PUT', 'PATCH', 'DELETE');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE frs_trace_kind AS ENUM
            ('brd_business_requirement', 'brd_objective', 'brd_kpi', 'brd_risk',
             'brd_text_block', 'nfr_driver', 'app_fact', 'doc_section',
             'discover_qa', 'within_frs');
    EXCEPTION WHEN duplicate_object THEN null; END $$;
    """)

    # ── 2. Stage A tables (5 module-level + frs_specs stub + frs_spec_decisions) ─

    _versioning_cols = lambda: [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True),
                  sa.ForeignKey("artifact_documents.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("row_key", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_locked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column("source", sa.Text, nullable=False, server_default="ai"),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    ]

    op.create_table("frs_modules",
        *_versioning_cols(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("layer", sa.dialects.postgresql.ENUM(
            "foundation", "vertical", "cross_cutting",
            name="frs_module_layer", create_type=False), nullable=False),
        sa.Column("scope_in", sa.Text, nullable=False, server_default=""),
        sa.Column("scope_out", sa.Text, nullable=False, server_default=""),
        sa.Column("summary", sa.Text, nullable=False, server_default=""),
        sa.Column("figma_root_link", sa.Text, nullable=True),
        sa.Column("completeness", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence", sa.String(8), nullable=False, server_default="low"),
        sa.UniqueConstraint("document_id", "row_key", "version",
                            name="uq_frs_modules_doc_key_ver"),
    )
    op.create_index("ix_frs_modules_doc_current", "frs_modules",
                    ["document_id", "is_current"])

    # … (same shape for frs_module_actors, frs_module_responsibilities,
    #    frs_module_interfaces, frs_module_data_entities,
    #    frs_specs, frs_spec_decisions)

    # ── 3. Stage B tables (8) ──────────────────────────────────────────────────
    # frs_screens, frs_ui_components, frs_endpoints, frs_data_entities,
    # frs_business_rules, frs_acceptance_scenarios, frs_functional_requirements,
    # frs_traceability — all created here so Stage B ships without another migration.
    # (Definitions in E4c-frs-functional-design.md §5.)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("frs_traceability")
    op.drop_table("frs_functional_requirements")
    op.drop_table("frs_acceptance_scenarios")
    op.drop_table("frs_business_rules")
    op.drop_table("frs_data_entities")
    op.drop_table("frs_endpoints")
    op.drop_table("frs_ui_components")
    op.drop_table("frs_screens")
    op.drop_table("frs_spec_decisions")
    op.drop_table("frs_specs")
    op.drop_table("frs_module_data_entities")
    op.drop_table("frs_module_interfaces")
    op.drop_table("frs_module_responsibilities")
    op.drop_table("frs_module_actors")
    op.drop_table("frs_modules")

    # Drop enums
    for enum_name in ("frs_trace_kind", "frs_http_method", "frs_decision_status",
                      "frs_priority", "frs_interface_direction", "frs_interface_kind",
                      "frs_actor_relationship", "frs_module_layer"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
```

**Register every model** in `backend/app/models/__init__.py`:

```python
from app.models.frs import (
    FrsModule, FrsModuleActor, FrsModuleResponsibility,
    FrsModuleInterface, FrsModuleDataEntity,
    FrsSpec, FrsSpecDecision,
    # Stage B models also exported here:
    FrsScreen, FrsUiComponent, FrsEndpoint, FrsDataEntity,
    FrsBusinessRule, FrsAcceptanceScenario, FrsFunctionalRequirement,
    FrsTraceability,
)
```

### 3.2 BrdLayer for context bundle

**File**: `backend/app/services/context/brd_layer.py` (NEW)

```python
"""BRD layer: all validated BRD rows + discover Q&A, formatted for FRS prompt injection."""
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import BrdLayer


async def build_brd_layer(project_id: uuid.UUID, db: AsyncSession) -> BrdLayer:
    """Load the full validated BRD corpus for FRS grounding.

    Returns an empty BrdLayer (with brd_status=None) if no BRD exists for the project.
    The readiness check in `_compute_readiness` enforces that brd_status == 'validated'
    before FRS generation can proceed.
    """
    from app.models.artifact import ArtifactDocument
    from app.models.brd import (
        BrdTextBlock, BrdObjective, BrdStakeholder, BrdActor,
        BrdScopeItem, BrdProcessStep, BrdBusinessRequirement,
        BrdDataEntity, BrdReportRequirement,
        BrdAssumption, BrdConstraint, BrdDependency,
        BrdRisk, BrdPhase, BrdMilestone, BrdKpi,
        BrdOpenQuestion, BrdDecision, BrdReference, BrdGlossaryEntry,
        BrdTraceability,
    )

    doc = (await db.execute(
        select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == "brd",
        )
    )).scalar_one_or_none()

    if doc is None:
        return BrdLayer(
            brd_document_id=None, brd_status=None, brd_validated_at=None, brd_snapshot_key=None,
            text_blocks=[], objectives=[], stakeholders=[], actors=[],
            scope_items=[], process_steps=[], business_requirements=[],
            data_entities=[], report_requirements=[],
            assumptions=[], constraints=[], dependencies=[],
            risks=[], phases=[], milestones=[], kpis=[],
            open_questions=[], decisions=[], references=[], glossary_entries=[],
            traceability=[], formatted_context="(no BRD found)",
        )

    async def _load(model, cols: list[str]) -> list[dict]:
        rows = (await db.execute(
            select(model).where(
                model.document_id == doc.id,
                model.is_current.is_(True),
                model.status == "active",
            )
        )).scalars().all()
        return [{"row_key": r.row_key, **{c: getattr(r, c) for c in cols}} for r in rows]

    text_blocks = await _load(BrdTextBlock, ["field_key", "text"])
    objectives = await _load(BrdObjective, ["statement", "category", "priority", "owner", "cb_outcome_ref"])
    stakeholders = await _load(BrdStakeholder, ["name", "stakeholder_type", "role", "interest", "influence"])
    actors = await _load(BrdActor, ["name", "actor_type", "description", "interactions"])
    scope_items = await _load(BrdScopeItem, ["kind", "text", "rationale", "cb_scope_ref"])
    process_steps = await _load(BrdProcessStep, ["step_type", "step_number", "actor", "action", "pain_point", "improvement"])
    brs = await _load(BrdBusinessRequirement, [
        "title", "description", "priority", "category",
        "acceptance_criteria", "objective_refs", "stakeholder_refs",
        "rationale", "completeness", "confidence",
    ])
    data_entities = await _load(BrdDataEntity, ["entity_name", "description", "owner_system", "data_sensitivity", "key_attributes"])
    report_reqs = await _load(BrdReportRequirement, ["report_name", "description", "audience", "frequency", "key_metrics"])
    assumptions = await _load(BrdAssumption, ["assumption", "impact_if_wrong", "owner", "cb_scope_ref"])
    constraints = await _load(BrdConstraint, ["constraint_text", "constraint_type", "source_ref"])
    dependencies = await _load(BrdDependency, ["dependency", "dependency_type", "owner", "due_date"])
    risks = await _load(BrdRisk, ["risk", "description", "severity", "likelihood", "mitigation", "owner"])
    phases = await _load(BrdPhase, ["phase_name", "description", "target_date", "included_br_refs"])
    milestones = await _load(BrdMilestone, ["milestone", "target", "description", "phase_ref", "cb_milestone_ref"])
    kpis = await _load(BrdKpi, ["kpi_name", "description", "baseline", "target", "timeframe", "data_source", "objective_ref", "cb_metric_ref"])
    open_qs = await _load(BrdOpenQuestion, ["question", "context", "owner", "due_date"])
    decisions = await _load(BrdDecision, ["decision", "rationale", "owner", "decision_date", "alternatives_considered"])
    refs = await _load(BrdReference, ["title", "reference_type", "location", "description"])
    glossary = await _load(BrdGlossaryEntry, ["term", "definition", "source_ref"])

    traceability = (await db.execute(
        select(BrdTraceability).where(BrdTraceability.document_id == doc.id)
    )).scalars().all()
    trace_dicts = [{
        "source_table": t.source_table, "source_row_key": t.source_row_key,
        "target_kind": t.target_kind, "target_ref": t.target_ref,
        "target_label": t.target_label, "confidence": t.confidence,
    } for t in traceability]

    formatted = _format_brd_context(
        text_blocks, objectives, stakeholders, actors, scope_items,
        process_steps, brs, data_entities, report_reqs,
        assumptions, constraints, dependencies, risks,
        phases, milestones, kpis, open_qs, decisions,
    )

    return BrdLayer(
        brd_document_id=str(doc.id),
        brd_status=doc.status,
        brd_validated_at=doc.validated_at.isoformat() if doc.validated_at else None,
        brd_snapshot_key=doc.validated_snapshot_key,
        text_blocks=text_blocks, objectives=objectives, stakeholders=stakeholders,
        actors=actors, scope_items=scope_items, process_steps=process_steps,
        business_requirements=brs, data_entities=data_entities,
        report_requirements=report_reqs, assumptions=assumptions,
        constraints=constraints, dependencies=dependencies, risks=risks,
        phases=phases, milestones=milestones, kpis=kpis,
        open_questions=open_qs, decisions=decisions,
        references=refs, glossary_entries=glossary,
        traceability=trace_dicts, formatted_context=formatted,
    )


def _format_brd_context(text_blocks, objectives, stakeholders, actors, scope_items,
                        process_steps, brs, data_entities, report_reqs,
                        assumptions, constraints, dependencies, risks,
                        phases, milestones, kpis, open_qs, decisions) -> str:
    """Render BRD as a compact prompt-ready string.

    Format:
      === Validated BRD ===
      **Business Context:** ...
      **Problem Statement:** ...

      **Objectives:**
        - [OBJ-001] (must) Reduce reconciliation time by 70% — owner: Ops Lead

      **Business Requirements (KEYSTONE):**
        - [BR-001] (must, functional) Reconcile premium collections within 7 days …
          AC: 1. Given premium received When 7 days passed Then …
          Trace: → OBJ-001 → CB capability:reconciliation
      …
    """
    lines: list[str] = ["=== Validated BRD ===\n"]

    tb_by_key = {r["field_key"]: r["text"] for r in text_blocks}
    for fk in ["business_context", "problem_statement", "root_causes"]:
        if text := tb_by_key.get(fk):
            label = fk.replace("_", " ").title()
            lines.append(f"**{label}:**\n{text}\n")

    if objectives:
        lines.append("\n**Strategic Objectives:**")
        for o in objectives:
            lines.append(f"  - [{o['row_key']}] ({o['priority']}) {o['statement']} — owner: {o['owner']}")

    if stakeholders:
        lines.append("\n**Stakeholders:**")
        for s in stakeholders:
            lines.append(f"  - [{s['row_key']}] {s['name']} ({s['stakeholder_type']}) — {s['role']}; interest: {s['interest']}; influence: {s['influence']}")

    if scope_items:
        by_kind: dict[str, list] = {}
        for s in scope_items:
            by_kind.setdefault(s["kind"], []).append(s)
        for kind_key, label in [("in_scope", "In Scope"), ("out_of_scope", "Out of Scope"), ("assumption", "Assumptions")]:
            if rows := by_kind.get(kind_key):
                lines.append(f"\n**Scope · {label}:**")
                for r in rows:
                    lines.append(f"  - [{r['row_key']}] {r['text']}")

    if brs:
        lines.append("\n**Business Requirements (KEYSTONE):**")
        for br in brs:
            ac_summary = ""
            if br.get("acceptance_criteria"):
                ac_count = len(br["acceptance_criteria"])
                ac_summary = f" · {ac_count} AC"
            lines.append(
                f"  - [{br['row_key']}] ({br['priority']}, {br['category']}) {br['title']}{ac_summary}\n"
                f"    {br['description'][:200]}{'…' if len(br['description']) > 200 else ''}\n"
                f"    Trace: → {', '.join(br.get('objective_refs', []))} / Stakeholders: {', '.join(br.get('stakeholder_refs', []))}"
            )

    if kpis:
        lines.append("\n**KPIs:**")
        for k in kpis:
            lines.append(f"  - [{k['row_key']}] {k['kpi_name']}: baseline {k['baseline']} → target {k['target']} ({k['timeframe']})")

    if risks:
        lines.append("\n**Risks:**")
        for r in risks:
            lines.append(f"  - [{r['row_key']}] ({r['severity']}/{r['likelihood']}) {r['risk']} — mitigation: {r['mitigation']}")

    if assumptions:
        lines.append("\n**Assumptions:**")
        for a in assumptions:
            lines.append(f"  - [{a['row_key']}] {a['assumption']}")

    if constraints:
        lines.append("\n**Constraints:**")
        for c in constraints:
            lines.append(f"  - [{c['row_key']}] ({c['constraint_type']}) {c['constraint_text']}")

    if dependencies:
        lines.append("\n**Dependencies:**")
        for d in dependencies:
            lines.append(f"  - [{d['row_key']}] ({d['dependency_type']}) {d['dependency']}")

    if phases:
        lines.append("\n**Implementation Phases:**")
        for p in phases:
            br_refs = ", ".join(p.get("included_br_refs", []))
            lines.append(f"  - [{p['row_key']}] {p['phase_name']} (target: {p['target_date']}) — covers BRs: {br_refs}")

    if data_entities:
        lines.append("\n**Data Entities (BRD level):**")
        for e in data_entities:
            lines.append(f"  - [{e['row_key']}] {e['entity_name']} ({e['data_sensitivity']}) — owner: {e['owner_system']}")

    return "\n".join(lines)
```

**File**: `backend/app/services/context/project_context.py` (EXTEND)

Add the new `BrdLayer` dataclass and update `gather_project_context`:

```python
# Add to existing file:

@dataclass
class BrdLayer:
    brd_document_id: str | None
    brd_status: str | None
    brd_validated_at: str | None
    brd_snapshot_key: str | None

    text_blocks: list[dict]
    objectives: list[dict]
    stakeholders: list[dict]
    actors: list[dict]
    scope_items: list[dict]
    process_steps: list[dict]
    business_requirements: list[dict]
    data_entities: list[dict]
    report_requirements: list[dict]
    assumptions: list[dict]
    constraints: list[dict]
    dependencies: list[dict]
    risks: list[dict]
    phases: list[dict]
    milestones: list[dict]
    kpis: list[dict]
    open_questions: list[dict]
    decisions: list[dict]
    references: list[dict]
    glossary_entries: list[dict]
    traceability: list[dict]

    formatted_context: str


@dataclass
class ProjectContextBundle:
    project_id: str
    project_name: str
    business_unit: str
    apps: AppLayer
    docs: DocsLayer
    cb: CbLayer
    brd: BrdLayer | None              # NEW; populated when artifact_type='frs'
    readiness: BundleReadiness
    snapshot_timestamp: str


# Update gather_project_context:

async def gather_project_context(
    project_id: uuid.UUID,
    db: AsyncSession,
    *,
    artifact_document_id: uuid.UUID | None = None,
    artifact_type: str = "brd",       # NEW param: 'brd' | 'frs'
) -> ProjectContextBundle:
    from app.services.context.app_layer import build_app_layer
    from app.services.context.docs_layer import build_docs_layer
    from app.services.context.cb_layer import build_cb_layer
    from app.services.context.brd_layer import build_brd_layer

    layers = await asyncio.gather(
        build_app_layer(project_id, db),
        build_docs_layer(project_id, db, artifact_document_id=artifact_document_id),
        build_cb_layer(project_id, db),
        build_brd_layer(project_id, db) if artifact_type == "frs" else _empty_brd(),
    )
    apps, docs, cb, brd = layers

    readiness = _compute_readiness(apps, docs, cb, brd, artifact_type=artifact_type)
    project_meta = await _load_project(project_id, db)

    return ProjectContextBundle(
        project_id=str(project_id),
        project_name=project_meta.name,
        business_unit=project_meta.business_unit or "—",
        apps=apps, docs=docs, cb=cb, brd=brd,
        readiness=readiness,
        snapshot_timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _compute_readiness(apps, docs, cb, brd, *, artifact_type: str = "brd") -> BundleReadiness:
    docs_all_ready = docs.pending_count == 0 and docs.failed_count == 0
    cb_ready = cb.cb_status == "validated"
    brd_ready = (artifact_type != "frs") or (brd is not None and brd.brd_status == "validated")

    blocking = None
    if docs.pending_count > 0:
        blocking = f"{docs.pending_count} document(s) still indexing"
    elif docs.failed_count > 0:
        blocking = f"{docs.failed_count} document(s) failed indexing"
    elif not cb_ready:
        blocking = f"Concept Brief not yet validated (status: {cb.cb_status or 'not started'})"
    elif not brd_ready:
        brd_status = brd.brd_status if brd else "not started"
        blocking = f"BRD not yet validated (status: {brd_status})"

    return BundleReadiness(
        apps_ready=True,
        docs_all_ready=docs_all_ready,
        docs_ready_count=docs.ready_count,
        docs_total_count=docs.total_count,
        docs_pending_names=[e.filename for e in docs.inventory if e.indexing_status in ("pending", "running")],
        docs_failed_names=[e.filename for e in docs.inventory if e.indexing_status == "error"],
        cb_ready=cb_ready, cb_status=cb.cb_status,
        brd_ready=brd_ready, brd_status=brd.brd_status if brd else None,
        can_generate=(docs_all_ready and cb_ready and brd_ready),
        blocking_reason=blocking,
    )
```

### 3.3 Projection (per-unit context narrowing)

**File**: `backend/app/services/context/projection.py` (EXTEND)

Add FRS routing to `project_for_unit`:

```python
@dataclass
class UnitContext:
    app_brain: str
    doc_sections: str
    cb_context: str
    brd_context: str           # NEW
    discover_qa: str
    combined: str


def project_for_unit(
    bundle: ProjectContextBundle,
    artifact_type: str,
    unit_key: str,
    *,
    doc_sections: str = "",
) -> UnitContext:
    if artifact_type == "brd":
        # existing BRD projection
        elements = _UNIT_CB_ELEMENTS.get(unit_key, ["text_blocks", "discover_qa"])
        cb_context = _project_cb(bundle.cb, elements)
        brd_context = ""
    elif artifact_type == "frs":
        # For FRS modularize, we want the FULL CB context (every element) since
        # modularization grounds on the entire CB
        cb_context = bundle.cb.formatted_context
        brd_context = bundle.brd.formatted_context if bundle.brd else "(no BRD)"
    else:
        cb_context = bundle.cb.formatted_context
        brd_context = ""

    combined_parts = [
        "=== App Brain ===\n" + bundle.apps.formatted_context,
        "=== Project Documents ===\n" + (doc_sections or bundle.docs.outline_text),
        cb_context,
    ]
    if brd_context:
        combined_parts.append(brd_context)
    combined = "\n\n".join(p for p in combined_parts if p.strip())

    return UnitContext(
        app_brain=bundle.apps.formatted_context,
        doc_sections=doc_sections or bundle.docs.outline_text,
        cb_context=cb_context,
        brd_context=brd_context,
        discover_qa=bundle.cb.discover_qa,
        combined=combined,
    )
```

### 3.4 Discover catalog additions

**File**: `backend/app/services/artifacts/discover_catalog.py` (EXTEND)

```python
# Add to existing file:

FRS_DISCOVER_CATEGORIES = [
    {"key": "scope",        "emoji": "🎯", "label": "Scope",        "color": "emerald"},
    {"key": "personas",     "emoji": "👥", "label": "Personas",     "color": "sky"},
    {"key": "integrations", "emoji": "🔄", "label": "Integrations", "color": "violet"},
    {"key": "data",         "emoji": "📊", "label": "Data",         "color": "amber"},
    {"key": "nfrs",         "emoji": "⚡", "label": "NFRs",         "color": "yellow"},
    {"key": "security",     "emoji": "🛡", "label": "Security",     "color": "rose"},
    {"key": "errors",       "emoji": "⚠", "label": "Errors",       "color": "orange"},
    {"key": "ui",           "emoji": "🎨", "label": "UI",           "color": "pink"},
    {"key": "delivery",     "emoji": "🚀", "label": "Delivery",     "color": "blue"},
]

FRS_DISCOVER_QUESTIONS = [
    # 🎯 Scope (2)
    {
        "key": "frs_1a", "category": "scope",
        "question": "What user workflows are P0 in this FRS bundle?",
        "why": "Drives module scope_in and backlog stub priorities (P0 vs P1+).",
        "example": "Customer registration, claim submission, status check",
    },
    {
        "key": "frs_1b", "category": "scope",
        "question": "Any modules you'd like to be pre-defined?",
        "why": "Locks high-confidence boundaries the AI shouldn't override.",
        "example": "Notifications should be its own module; do not merge with Auth",
    },
    # 👥 Personas (1)
    {
        "key": "frs_2a", "category": "personas",
        "question": "Who are the primary roles?",
        "why": "Drives the FrsModuleActor rows per module.",
        "example": "Customer, Claims Operator, Auditor, System (chatbot)",
    },
    # 🔄 Integrations (2)
    {
        "key": "frs_3a", "category": "integrations",
        "question": "Which external systems will the modules call?",
        "why": "Drives outbound API interfaces in feature modules.",
        "example": "Email service, CRM, payment gateway, KYC provider",
    },
    {
        "key": "frs_3b", "category": "integrations",
        "question": "Sync API or async events for cross-module communication?",
        "why": "Drives interface transport choice (rest vs event_bus).",
        "example": "Async events for notifications; sync REST elsewhere",
    },
    # 📊 Data (1)
    {
        "key": "frs_4a", "category": "data",
        "question": "Source of truth for the main entities?",
        "why": "Drives data ownership in modules; prevents shared-database integration.",
        "example": "customer_profile owned by Customer module; read by all",
    },
    # ⚡ NFRs (1)
    {
        "key": "frs_5a", "category": "nfrs",
        "question": "Latency / availability / scalability targets?",
        "why": "Captured as system-view constraints inside each module.",
        "example": "P99 < 500ms; 99.9% uptime",
    },
    # 🛡 Security (2)
    {
        "key": "frs_6a", "category": "security",
        "question": "Auth/RBAC model? Data sensitivity per entity?",
        "why": "Used in Stage B; hoists into Cross-cutting Standards module.",
        "example": "OAuth2; customer PII redacted in logs",
    },
    {
        "key": "frs_6b", "category": "security",
        "question": "Audit / compliance requirements?",
        "why": "Drives audit-trail responsibilities in feature modules.",
        "example": "All claim mutations logged for 7 years (SOX)",
    },
    # ⚠ Errors (1)
    {
        "key": "frs_7a", "category": "errors",
        "question": "Failure-handling strategy?",
        "why": "Used in Stage B; influences Cross-cutting Standards error envelope.",
        "example": "Idempotent retry with backoff for transient; fail-fast for validation",
    },
    # 🎨 UI (1)
    {
        "key": "frs_8a", "category": "ui",
        "question": "Will Figma designs be provided? Where?",
        "why": "Sets expectations for Stage B Figma gate.",
        "example": "Yes, links shared per screen during Stage B",
    },
    # 🚀 Delivery (1)
    {
        "key": "frs_9a", "category": "delivery",
        "question": "Phasing — which modules must ship first?",
        "why": "Influences module ordering and Layer 1 vs Layer 2 classification.",
        "example": "Phase 1: registration + intake; Phase 2: triage; Phase 3: analytics",
    },
]

# Map each unit to its subset of questions
FRS_UNIT_DISCOVER_MAP = {
    "modularize": [
        "frs_1a", "frs_1b", "frs_2a", "frs_3a", "frs_3b", "frs_4a", "frs_9a",
    ],
    "design_module": [
        "frs_4a", "frs_5a", "frs_6a", "frs_6b", "frs_7a", "frs_8a",
    ],
}


def get_catalog_for_artifact(artifact_type: str) -> dict:
    if artifact_type == "concept_brief":
        return {"categories": CB_CATEGORIES, "questions": CB_QUESTIONS}
    elif artifact_type == "brd":
        return {"categories": BRD_CATEGORIES, "questions": BRD_QUESTIONS}
    elif artifact_type == "frs":
        return {"categories": FRS_DISCOVER_CATEGORIES, "questions": FRS_DISCOVER_QUESTIONS}
    raise ValueError(f"Unknown artifact_type: {artifact_type}")
```

### 3.5 Manifest

**File**: `backend/app/services/artifacts/manifest/frs.py` (NEW)

```python
"""FRS manifest — declarative definition of the 2 generation phases."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class FrsUnitSpec:
    unit_key: str
    phase: Literal["A", "B"]
    label: str
    writes: list[str]
    depends_on: list[str]
    discover_question_keys: list[str]
    timeout_seconds: int = 90


FRS_STAGE_A_UNIT = FrsUnitSpec(
    unit_key="modularize",
    phase="A",
    label="Decompose BRD into modules",
    writes=[
        "frs_modules",
        "frs_module_actors",
        "frs_module_responsibilities",
        "frs_module_interfaces",
        "frs_module_data_entities",
        "frs_specs",            # backlog stubs only
        "frs_spec_decisions",   # module-scoped only
    ],
    depends_on=[],
    discover_question_keys=["frs_1a", "frs_1b", "frs_2a", "frs_3a", "frs_3b", "frs_4a", "frs_9a"],
    timeout_seconds=90,
)


# Stage B is defined in `E4c-frs-functional-design.md` plan and added to this manifest later.

FRS_MANIFEST: list[FrsUnitSpec] = [FRS_STAGE_A_UNIT]
FRS_MANIFEST_BY_KEY = {u.unit_key: u for u in FRS_MANIFEST}


# Table registry — used by orchestrator for routing and by validator for queries
from app.models.frs import (
    FrsModule, FrsModuleActor, FrsModuleResponsibility,
    FrsModuleInterface, FrsModuleDataEntity,
    FrsSpec, FrsSpecDecision,
    # Stage B tables (registered now so the orchestrator can find them for cleanup):
    FrsScreen, FrsUiComponent, FrsEndpoint, FrsDataEntity,
    FrsBusinessRule, FrsAcceptanceScenario, FrsFunctionalRequirement,
    FrsTraceability,
)

FRS_TABLE_MAP: dict[str, type] = {
    "frs_modules":                  FrsModule,
    "frs_module_actors":            FrsModuleActor,
    "frs_module_responsibilities":  FrsModuleResponsibility,
    "frs_module_interfaces":        FrsModuleInterface,
    "frs_module_data_entities":     FrsModuleDataEntity,
    "frs_specs":                    FrsSpec,
    "frs_spec_decisions":           FrsSpecDecision,
    # Stage B (not written in Stage A; registered for queries + Stage B):
    "frs_screens":                  FrsScreen,
    "frs_ui_components":            FrsUiComponent,
    "frs_endpoints":                FrsEndpoint,
    "frs_data_entities":            FrsDataEntity,
    "frs_business_rules":           FrsBusinessRule,
    "frs_acceptance_scenarios":     FrsAcceptanceScenario,
    "frs_functional_requirements":  FrsFunctionalRequirement,
}


# Per-table column whitelist for upserts (excludes versioning columns + id)
FRS_TYPED_COLS: dict[str, list[str]] = {
    "frs_modules": [
        "name", "slug", "layer", "scope_in", "scope_out", "summary",
        "figma_root_link", "completeness", "confidence",
    ],
    "frs_module_actors": [
        "module_row_key", "actor_name", "relationship", "notes",
    ],
    "frs_module_responsibilities": [
        "module_row_key", "responsibility", "frs_refs",
    ],
    "frs_module_interfaces": [
        "module_row_key", "interface_kind", "direction", "transport",
        "name", "counterpart", "user_role", "purpose", "frs_ref",
    ],
    "frs_module_data_entities": [
        "module_row_key", "entity_name", "business_purpose", "source_of_truth",
    ],
    "frs_specs": [
        "module_row_key", "title", "priority", "layer", "br_refs",
        "nfr_refs", "depends_on", "narrative", "independent_test",
        "data_and_validation", "errors_and_edge_cases", "observability",
        "implementation_tasks", "completeness", "confidence",
    ],
    "frs_spec_decisions": [
        "spec_row_key", "module_row_key", "question", "options",
        "recommended_index", "recommended_rationale",
        "user_chosen_index", "resolution_status",
    ],
    # Stage B columns (in same map for orchestrator reuse):
    # … (defined in E4c-frs-functional-design.md plan)
}
```

### 3.6 DSPy Signature + mock fixture

**File**: `backend/app/services/skills/dspy_frs.py` (NEW — Stage A section only here)

The full Pydantic schema for `FrsModularizeOutput` is in the PRD §6.2; the implementation
follows the BRD pattern verbatim:

```python
"""DSPy module for FRS Modularization (Stage A).

Pattern follows dspy_brd.py: Pydantic output → DSPy Signature → DSPy Module
(ChainOfThought) → async runner with mock short-circuit.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Literal

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).parent.parent / "llm" / "fixtures"


def _configure() -> None:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURE_DIR / f"{name}.json").read_text())


# … Pydantic schema (FrsActorRow, FrsResponsibilityRow, FrsInterfaceRow,
#    FrsModuleDataRow, FrsBacklogStub, FrsModuleInventoryRow, FrsSpecDecisionRow,
#    FrsOpenQuestion, FrsModularizeOutput) — per PRD §6.2 …


class FrsModularizeSignature(dspy.Signature):
    """[Full docstring from PRD §6.2 — HARD RULES, CROSS-CUTTING STANDARDS, BACKLOG STUBS,
    AMBIGUITY sections — included verbatim]"""
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    brief: str = dspy.InputField()
    brd_context: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    current_modules: str = dspy.InputField()
    locked_modules: str = dspy.InputField()
    result: FrsModularizeOutput = dspy.OutputField()


class FrsModularizeModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(FrsModularizeSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_modularize(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("frs_modularize")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: FrsModularizeModule()(**kwargs))
```

**File**: `backend/app/services/llm/fixtures/frs_modularize.json` (NEW — hand-written)

A realistic fixture that exercises every code path. For the "claims chatbot" mock project:

```json
{
  "modules": [
    {
      "row_key": "MOD-001",
      "name": "Customer Intake",
      "slug": "customer-intake",
      "layer": "vertical",
      "scope_in": "- New customer claim submissions via chatbot\n- Initial validation of claim details\n- Routing to triage queue",
      "scope_out": "- Claim adjudication (owned by MOD-003 Claims Triage)\n- Notifications (owned by MOD-004 Notifications)",
      "summary": "Captures new claims initiated by customers through the chatbot interface, validates basic policy and identity fields, and hands off to triage.",
      "actors": [
        {"actor_name": "Customer", "relationship": "primary_user", "notes": "Initiates claim submission via chatbot"},
        {"actor_name": "Authentication Module", "relationship": "dependency", "notes": "Validates customer identity"},
        {"actor_name": "Claims Triage Module", "relationship": "downstream_consumer", "notes": "Receives validated claim payload"}
      ],
      "responsibilities": [
        {"responsibility": "Accept claim submission from chatbot UI", "frs_refs": ["M001-FRS001"]},
        {"responsibility": "Validate policy number and customer identity", "frs_refs": ["M001-FRS001", "M001-FRS002"]},
        {"responsibility": "Capture incident description and supporting documents", "frs_refs": ["M001-FRS002"]},
        {"responsibility": "Hand off validated claim to triage queue", "frs_refs": ["M001-FRS003"]}
      ],
      "interfaces": [
        {"interface_kind": "ui_surface", "name": "Claim Submission Form", "user_role": "Customer", "purpose": "Step-by-step intake flow"},
        {"interface_kind": "api", "direction": "outbound", "transport": "rest", "name": "validateCustomer", "counterpart": "Authentication Module", "purpose": "Verify policy ownership"},
        {"interface_kind": "event", "direction": "outbound", "transport": "event_bus", "name": "claim_submitted", "counterpart": "Claims Triage Module", "purpose": "Hand off validated claim"}
      ],
      "data_entities": [
        {"entity_name": "claim_draft", "business_purpose": "Stores in-progress claim during intake", "source_of_truth": "MOD-001 Customer Intake"}
      ],
      "frs_backlog": [
        {"row_key": "M001-FRS001", "title": "Customer Identity Validation", "priority": "P0", "br_refs": ["BR-001", "BR-007"], "description": "Validate policy number and identity before accepting claim details"},
        {"row_key": "M001-FRS002", "title": "Claim Intake Form", "priority": "P0", "br_refs": ["BR-002", "BR-003"], "description": "Step-by-step chatbot dialog to capture incident details"},
        {"row_key": "M001-FRS003", "title": "Triage Handoff", "priority": "P1", "br_refs": ["BR-004"], "description": "Publish claim_submitted event with validated payload"}
      ]
    },
    {
      "row_key": "MOD-002",
      "name": "Authentication",
      "slug": "authentication",
      "layer": "vertical",
      "scope_in": "- Customer authentication via policy number + DOB\n- Session management for the chatbot conversation",
      "scope_out": "- Operator authentication (out of scope for v1)",
      "summary": "Verifies customer identity before any claim-related action.",
      "actors": [
        {"actor_name": "Customer", "relationship": "primary_user", "notes": "Provides credentials"},
        {"actor_name": "Customer Intake Module", "relationship": "downstream_consumer", "notes": "Calls validateCustomer"},
        {"actor_name": "Claims Triage Module", "relationship": "downstream_consumer", "notes": "Reads validated identity"}
      ],
      "responsibilities": [
        {"responsibility": "Validate policy number + customer DOB", "frs_refs": ["M002-FRS001"]},
        {"responsibility": "Issue and manage chatbot session token", "frs_refs": ["M002-FRS002"]}
      ],
      "interfaces": [
        {"interface_kind": "api", "direction": "inbound", "transport": "rest", "name": "validateCustomer", "counterpart": "Customer Intake Module", "purpose": "Identity check"}
      ],
      "data_entities": [
        {"entity_name": "session_token", "business_purpose": "Tracks active chatbot conversation", "source_of_truth": "MOD-002 Authentication"}
      ],
      "frs_backlog": [
        {"row_key": "M002-FRS001", "title": "Customer Identity Check", "priority": "P0", "br_refs": ["BR-005"], "description": "Verify policy + DOB match"},
        {"row_key": "M002-FRS002", "title": "Session Management", "priority": "P1", "br_refs": ["BR-008"], "description": "Issue, refresh, and expire session tokens"}
      ]
    },
    {
      "row_key": "MOD-003",
      "name": "Claims Triage",
      "slug": "claims-triage",
      "layer": "vertical",
      "scope_in": "- Initial classification of claim type\n- Routing to appropriate operator queue\n- Setting expected resolution SLA",
      "scope_out": "- Claim adjudication (owned by operator workflow, out of v1 scope)",
      "summary": "Classifies and routes validated claims to operator queues based on severity and type.",
      "actors": [
        {"actor_name": "Customer Intake Module", "relationship": "dependency", "notes": "Provides validated claim payload"},
        {"actor_name": "Claims Operator", "relationship": "downstream_consumer", "notes": "Consumes triaged queue"},
        {"actor_name": "Notifications Module", "relationship": "downstream_consumer", "notes": "Receives SLA breach events"}
      ],
      "responsibilities": [
        {"responsibility": "Classify claim type (motor, health, property)", "frs_refs": ["M003-FRS001"]},
        {"responsibility": "Assign SLA based on severity", "frs_refs": ["M003-FRS002"]},
        {"responsibility": "Route to operator queue", "frs_refs": ["M003-FRS003"]}
      ],
      "interfaces": [
        {"interface_kind": "event", "direction": "inbound", "transport": "event_bus", "name": "claim_submitted", "counterpart": "Customer Intake Module", "purpose": "Consume validated claims"},
        {"interface_kind": "event", "direction": "outbound", "transport": "event_bus", "name": "sla_breach", "counterpart": "Notifications Module", "purpose": "Alert on overdue claims"}
      ],
      "data_entities": [
        {"entity_name": "triaged_claim", "business_purpose": "Routed and classified claim awaiting operator action", "source_of_truth": "MOD-003 Claims Triage"}
      ],
      "frs_backlog": [
        {"row_key": "M003-FRS001", "title": "Claim Classification", "priority": "P0", "br_refs": ["BR-009"], "description": "Apply rules-based classifier to assign claim type"},
        {"row_key": "M003-FRS002", "title": "SLA Assignment", "priority": "P0", "br_refs": ["BR-010"], "description": "Compute SLA timestamp from severity tier"},
        {"row_key": "M003-FRS003", "title": "Operator Queue Routing", "priority": "P0", "br_refs": ["BR-011"], "description": "Place claim in queue matching operator skill"}
      ]
    },
    {
      "row_key": "MOD-004",
      "name": "Notifications",
      "slug": "notifications",
      "layer": "vertical",
      "scope_in": "- Customer-facing status updates\n- Operator alerts for SLA breaches",
      "scope_out": "- Email template content (managed in MOD-000 Cross-cutting Standards)",
      "summary": "Sends asynchronous notifications to customers and operators based on claim events.",
      "actors": [
        {"actor_name": "Email Service", "relationship": "external_system", "notes": "External SaaS provider"},
        {"actor_name": "Claims Triage Module", "relationship": "dependency", "notes": "Source of sla_breach events"}
      ],
      "responsibilities": [
        {"responsibility": "Send claim status update emails", "frs_refs": ["M004-FRS001"]},
        {"responsibility": "Send SLA breach alerts to operators", "frs_refs": ["M004-FRS002"]}
      ],
      "interfaces": [
        {"interface_kind": "event", "direction": "inbound", "transport": "event_bus", "name": "claim_submitted", "counterpart": "Customer Intake Module", "purpose": "Trigger 'we got your claim' email"},
        {"interface_kind": "event", "direction": "inbound", "transport": "event_bus", "name": "sla_breach", "counterpart": "Claims Triage Module", "purpose": "Trigger operator alert"},
        {"interface_kind": "api", "direction": "outbound", "transport": "rest", "name": "sendEmail", "counterpart": "Email Service", "purpose": "Deliver email"}
      ],
      "data_entities": [
        {"entity_name": "notification_log", "business_purpose": "Audit trail of sent notifications", "source_of_truth": "MOD-004 Notifications"}
      ],
      "frs_backlog": [
        {"row_key": "M004-FRS001", "title": "Claim Acknowledgement Email", "priority": "P0", "br_refs": ["BR-013"], "description": "Send confirmation when claim is submitted"},
        {"row_key": "M004-FRS002", "title": "Operator SLA Alert", "priority": "P1", "br_refs": ["BR-014"], "description": "Notify operator when claim exceeds SLA"}
      ]
    },
    {
      "row_key": "MOD-000",
      "name": "Cross-cutting Standards",
      "slug": "cross-cutting-standards",
      "layer": "foundation",
      "scope_in": "- Common error response envelope\n- Audit logging convention\n- RBAC base policies\n- Reference data (claim types, severity tiers)",
      "scope_out": "- Module-specific business rules (handled per module)",
      "summary": "Foundation FRSes shared by all feature modules: error envelope, audit logging, RBAC, reference data.",
      "actors": [
        {"actor_name": "All feature modules", "relationship": "downstream_consumer", "notes": "Reference these standards via depends_on"}
      ],
      "responsibilities": [
        {"responsibility": "Define common error response envelope", "frs_refs": ["M000-FRS001"]},
        {"responsibility": "Define audit logging requirements", "frs_refs": ["M000-FRS002"]}
      ],
      "interfaces": [],
      "data_entities": [
        {"entity_name": "audit_log_entry", "business_purpose": "Standardised audit trail row", "source_of_truth": "MOD-000 Cross-cutting Standards"}
      ],
      "frs_backlog": [
        {"row_key": "M000-FRS001", "title": "Common Error Envelope", "priority": "P0", "br_refs": ["BR-006"], "description": "Standardise error response shape across all backend services"},
        {"row_key": "M000-FRS002", "title": "Audit Logging Standard", "priority": "P0", "br_refs": ["BR-006"], "description": "Audit pattern referenced by all feature modules"}
      ]
    }
  ],
  "spec_decisions": [
    {
      "row_key": "MOD-001-DEC-1",
      "module_row_key": "MOD-001",
      "question": "Should the chatbot session token be stored client-side (cookie) or server-side (Redis)?",
      "options": [
        {"label": "Server-side (Redis)", "description": "Token in Redis with TTL; client holds opaque session ID", "implications": "Easier revocation; requires Redis dependency"},
        {"label": "Client-side (signed JWT)", "description": "Stateless JWT signed with rotating key", "implications": "No Redis dep; harder to revoke mid-session"}
      ],
      "recommended_index": 0,
      "recommended_rationale": "Project app brain indicates Redis is already in use for the BRD claims chatbot; consistency + easier revocation."
    }
  ],
  "open_questions": [],
  "completeness": 92,
  "confidence": "high"
}
```

### 3.7 Orchestrator

**File**: `backend/app/services/artifacts/frs_orchestrator.py` (NEW)

```python
"""FRS orchestrator — Stage A (modularize) + Stage A persistence + readiness check + helpers.

Stage B's `generate_frs_design_module` is added to this same file in the Stage B plan.

Patterns mirrored from brd_orchestrator.py:
- VersionedRow upsert with diff detection
- Atomic JSONB unit_status merge
- Idempotent regen (current_rows / locked_rows context to LLM)
- Soft-delete by status
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text as sa_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import (
    ArtifactDocument, ArtifactMessage, ArtifactSource,
)
from app.models.document import Document
from app.models.project import Project
from app.services.artifacts.manifest.frs import (
    FRS_MANIFEST_BY_KEY, FRS_TABLE_MAP, FRS_TYPED_COLS,
)
from app.services.context.project_context import (
    ProjectContextBundle, gather_project_context,
)
from app.services.context.projection import project_for_unit
from app.services.skills.dspy_frs import run_modularize

log = logging.getLogger(__name__)


# ── Document lifecycle ──────────────────────────────────────────────────────────

async def _ensure_frs_document(project_id: uuid.UUID, db: AsyncSession) -> ArtifactDocument:
    """Get-or-create the FRS ArtifactDocument for a project. Idempotent + race-safe."""
    doc = (await db.execute(
        select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == "frs",
        )
    )).scalar_one_or_none()
    if doc is not None:
        return doc

    try:
        async with db.begin_nested():
            doc = ArtifactDocument(
                project_id=project_id, artifact_type="frs", status="in_interview",
            )
            db.add(doc)
            await db.flush()
            # Auto-enroll every project document as a source
            doc_ids = (await db.execute(
                select(Document.id).where(Document.project_id == project_id)
            )).scalars().all()
            for did in doc_ids:
                db.add(ArtifactSource(
                    artifact_document_id=doc.id, source_document_id=did, included=True,
                ))
            await db.flush()
        return doc
    except IntegrityError:
        # Race: another caller created it first
        doc = (await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "frs",
            )
        )).scalar_one()
        return doc


# ── Generic versioned-row upsert (the rugged core) ──────────────────────────────

async def upsert_frs_rows(
    table_name: str,
    document_id: uuid.UUID,
    rows: list[dict[str, Any]],
    source: str,
    db: AsyncSession,
    *,
    scope_keys: set[str] | None = None,
    actor_user_id: uuid.UUID | None = None,
) -> int:
    """Versioned upsert. Returns count of NEW versions created.

    For each row by row_key:
      1. If no existing current row: insert as v1.
      2. If existing current row equals the new content (typed cols match): no-op.
      3. If existing row is locked: skip (preserve verbatim).
      4. Otherwise: mark old is_current=False; insert new with version+1.

    Rows in `scope_keys` not present in `rows` get status='removed'.

    Atomic per-row via savepoints — a single bad row doesn't poison the batch.
    """
    model = FRS_TABLE_MAP[table_name]
    typed_cols = FRS_TYPED_COLS[table_name]
    new_count = 0

    for row_dict in rows:
        row_key = row_dict["row_key"]
        try:
            async with db.begin_nested():
                existing = (await db.execute(
                    select(model).where(
                        model.document_id == document_id,
                        model.row_key == row_key,
                        model.is_current.is_(True),
                    )
                )).scalar_one_or_none()

                if existing is not None and existing.is_locked:
                    continue  # locked — skip

                # Coerce types (per BRD pattern, integer cols receive strings sometimes)
                row_dict = _coerce_row_types(table_name, row_dict, existing)

                if existing is not None and _row_unchanged(existing, row_dict, typed_cols):
                    continue  # no diff

                if existing is not None:
                    existing.is_current = False

                new_version = (existing.version + 1) if existing else 1
                new_row = model(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    row_key=row_key,
                    version=new_version,
                    is_current=True,
                    is_locked=False,
                    status="active",
                    source=source,
                    created_by=actor_user_id,
                    created_at=datetime.now(timezone.utc),
                    **{c: row_dict.get(c) for c in typed_cols if c in row_dict},
                )
                db.add(new_row)
                new_count += 1
        except Exception as e:
            log.warning(
                f"upsert_frs_rows: row {row_key} in {table_name} failed: {e}",
                extra={"row_dict": row_dict},
            )
            # Continue with next row — partial success better than total failure

    # Mark rows in scope_keys not in `rows` as removed
    if scope_keys is not None:
        provided_keys = {r["row_key"] for r in rows}
        to_remove = scope_keys - provided_keys
        if to_remove:
            for rk in to_remove:
                row = (await db.execute(
                    select(model).where(
                        model.document_id == document_id,
                        model.row_key == rk,
                        model.is_current.is_(True),
                    )
                )).scalar_one_or_none()
                if row and not row.is_locked:
                    row.status = "removed"

    return new_count


def _row_unchanged(existing, row_dict: dict, typed_cols: list[str]) -> bool:
    """Compare current row's typed columns to incoming dict."""
    for col in typed_cols:
        if col not in row_dict:
            continue
        if getattr(existing, col) != row_dict[col]:
            return False
    return True


_FRS_INT_COLS: dict[str, set[str]] = {
    "frs_specs": {"completeness"},
    "frs_modules": {"completeness"},
    "frs_spec_decisions": {"recommended_index", "user_chosen_index"},
}


def _coerce_row_types(table: str, row_dict: dict, existing) -> dict:
    """Coerce string-encoded ints to ints (LLMs sometimes return '5' instead of 5)."""
    int_cols = _FRS_INT_COLS.get(table, set())
    out = dict(row_dict)
    for col in int_cols:
        if col in out and isinstance(out[col], str):
            try:
                out[col] = int(out[col])
            except (ValueError, TypeError):
                out[col] = getattr(existing, col) if existing else None
    return out


# ── Stage A: modularize ─────────────────────────────────────────────────────────

async def generate_frs_modularize(
    project: Project,
    doc: ArtifactDocument,
    bundle: ProjectContextBundle,
    db: AsyncSession,
    *,
    discover_context: str = "",
) -> dict:
    """Run the modularize DSPy unit and persist its output across 6 tables.

    Atomic + idempotent. Existing locked rows are preserved verbatim.
    """
    spec = FRS_MANIFEST_BY_KEY["modularize"]

    # Set _current_unit so the theater knows we're on Phase A
    await _set_current_unit(doc.id, "modularize", db)

    # Project context to what modularize needs
    unit_ctx = project_for_unit(bundle, "frs", "modularize")
    qa_pairs = await _gather_frs_unit_qa(doc.id, "modularize", db)
    if discover_context:
        qa_pairs = discover_context + ("\n\n" + qa_pairs if qa_pairs != "(none yet)" else "")

    brief = await _read_initial_brief(doc.id, db)
    current_modules = await _serialize_current_modules_with_children(doc.id, db)
    locked_modules = [m for m in current_modules if m.get("_is_locked")]

    log.info(
        "frs.modularize.start",
        extra={
            "project_id": str(project.id), "doc_id": str(doc.id),
            "brd_status": bundle.brd.brd_status if bundle.brd else None,
            "module_count_before": len(current_modules),
            "locked_count": len(locked_modules),
        },
    )

    try:
        result = await asyncio.wait_for(
            run_modularize(
                project_name=project.name,
                business_unit=project.business_unit or "—",
                brief=brief,
                brd_context=bundle.brd.formatted_context if bundle.brd else "(no BRD)",
                cb_context=bundle.cb.formatted_context,
                app_brain=bundle.apps.formatted_context,
                source_sections=unit_ctx.doc_sections,
                qa_pairs=qa_pairs,
                current_modules=json.dumps(current_modules),
                locked_modules=json.dumps(locked_modules),
            ),
            timeout=spec.timeout_seconds,
        )
    except asyncio.TimeoutError:
        log.error("frs.modularize.timeout", extra={"doc_id": str(doc.id)})
        await _record_unit_error(doc.id, "modularize", "Modularization timed out after 90s.", db)
        raise

    log.info(
        "frs.modularize.complete",
        extra={
            "doc_id": str(doc.id),
            "module_count": len(result.get("modules", [])),
            "decision_count": len(result.get("spec_decisions", [])),
            "completeness": result.get("completeness"),
            "confidence": result.get("confidence"),
        },
    )

    await _persist_modularize_result(doc.id, result, db)

    # Atomic unit_status update
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb),"
        "    updated_at  = NOW() "
        "WHERE id = :doc_id"
    ), {
        "patch": json.dumps({
            "modularize": {
                "completeness": result.get("completeness", 0),
                "confidence": result.get("confidence", "low"),
            },
            "_current_unit": None,
        }),
        "doc_id": str(doc.id),
    })

    await _emit_modularize_messages(doc, result, db)
    return result


async def _persist_modularize_result(document_id: uuid.UUID, result: dict, db: AsyncSession):
    """Route the modularize output to the 6 Stage-A tables.

    Order matters: modules first (FK dependency from sub-rows).
    """
    modules = result.get("modules", [])

    # 1. frs_modules
    module_rows = [{
        "row_key": m["row_key"],
        "name": m["name"],
        "slug": m["slug"],
        "layer": m["layer"],
        "scope_in": m["scope_in"],
        "scope_out": m["scope_out"],
        "summary": m["summary"],
        "figma_root_link": m.get("figma_root_link"),
        "completeness": result.get("completeness", 0),
        "confidence": result.get("confidence", "low"),
    } for m in modules]
    module_keys = {m["row_key"] for m in module_rows}
    await upsert_frs_rows("frs_modules", document_id, module_rows, "ai", db,
                          scope_keys=module_keys)

    # 2. Child tables — one per module
    for m in modules:
        # Actors
        actor_rows = []
        for i, a in enumerate(m.get("actors", []), 1):
            actor_rows.append({
                "row_key": f"{m['row_key']}-ACT-{i}",
                "module_row_key": m["row_key"],
                "actor_name": a["actor_name"],
                "relationship": a["relationship"],
                "notes": a.get("notes", ""),
            })
        actor_keys = {r["row_key"] for r in actor_rows}
        await upsert_frs_rows("frs_module_actors", document_id, actor_rows, "ai", db,
                              scope_keys=actor_keys)

        # Responsibilities
        resp_rows = []
        for i, r in enumerate(m.get("responsibilities", []), 1):
            resp_rows.append({
                "row_key": f"{m['row_key']}-R-{i}",
                "module_row_key": m["row_key"],
                "responsibility": r["responsibility"],
                "frs_refs": r.get("frs_refs", []),
            })
        resp_keys = {r["row_key"] for r in resp_rows}
        await upsert_frs_rows("frs_module_responsibilities", document_id, resp_rows, "ai", db,
                              scope_keys=resp_keys)

        # Interfaces
        iface_rows = []
        for i, iface in enumerate(m.get("interfaces", []), 1):
            iface_rows.append({
                "row_key": f"{m['row_key']}-IF-{i}",
                "module_row_key": m["row_key"],
                "interface_kind": iface["interface_kind"],
                "direction": iface.get("direction"),
                "transport": iface.get("transport"),
                "name": iface["name"],
                "counterpart": iface.get("counterpart"),
                "user_role": iface.get("user_role"),
                "purpose": iface.get("purpose", ""),
                "frs_ref": iface.get("frs_ref"),
            })
        iface_keys = {r["row_key"] for r in iface_rows}
        await upsert_frs_rows("frs_module_interfaces", document_id, iface_rows, "ai", db,
                              scope_keys=iface_keys)

        # Data entities (module-level)
        de_rows = []
        for i, de in enumerate(m.get("data_entities", []), 1):
            de_rows.append({
                "row_key": f"{m['row_key']}-E-{i}",
                "module_row_key": m["row_key"],
                "entity_name": de["entity_name"],
                "business_purpose": de.get("business_purpose", ""),
                "source_of_truth": de.get("source_of_truth", ""),
            })
        de_keys = {r["row_key"] for r in de_rows}
        await upsert_frs_rows("frs_module_data_entities", document_id, de_rows, "ai", db,
                              scope_keys=de_keys)

        # Backlog stubs → frs_specs (stub form)
        stub_rows = []
        for stub in m.get("frs_backlog", []):
            stub_rows.append({
                "row_key": stub["row_key"],
                "module_row_key": m["row_key"],
                "title": stub["title"],
                "priority": stub["priority"],
                "layer": m["layer"],
                "br_refs": stub.get("br_refs", []),
                "nfr_refs": [],
                "depends_on": [],
                "narrative": stub.get("description", ""),  # description → narrative seed
                "independent_test": "",
                "data_and_validation": "",
                "errors_and_edge_cases": "",
                "observability": "",
                "implementation_tasks": [],
                "completeness": 0,
                "confidence": "low",
            })
        await upsert_frs_rows("frs_specs", document_id, stub_rows, "ai", db)
        # NOTE: no scope_keys for frs_specs — Stage B may add specs that didn't come from
        # this modularize run; we don't want to mark them as removed.

    # 3. Decisions (module-scoped only)
    decision_rows = []
    for d in result.get("spec_decisions", []):
        if d.get("spec_row_key"):  # spec-scoped — defer to Stage B
            continue
        decision_rows.append({
            "row_key": d["row_key"],
            "module_row_key": d.get("module_row_key"),
            "spec_row_key": None,
            "question": d["question"],
            "options": d["options"],
            "recommended_index": d["recommended_index"],
            "recommended_rationale": d.get("recommended_rationale", ""),
            "user_chosen_index": None,
            "resolution_status": "open",
        })
    await upsert_frs_rows("frs_spec_decisions", document_id, decision_rows, "ai", db)


# ── Helpers ─────────────────────────────────────────────────────────────────────

async def _set_current_unit(doc_id: uuid.UUID, unit_key: str | None, db: AsyncSession):
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb) "
        "WHERE id = :doc_id"
    ), {"patch": json.dumps({"_current_unit": unit_key}), "doc_id": str(doc_id)})


async def _read_initial_brief(doc_id: uuid.UUID, db: AsyncSession) -> str:
    msg = (await db.execute(
        select(ArtifactMessage).where(
            ArtifactMessage.document_id == doc_id,
            ArtifactMessage.role == "user",
            ArtifactMessage.meta["is_initial_brief"].as_boolean().is_(True),
        ).order_by(ArtifactMessage.seq.desc()).limit(1)
    )).scalar_one_or_none()
    return msg.content if msg else ""


async def _gather_frs_unit_qa(doc_id: uuid.UUID, unit_key: str, db: AsyncSession) -> str:
    """Gather discover Q&A + general refinement Q&A for this unit."""
    rows = (await db.execute(
        select(ArtifactMessage).where(
            ArtifactMessage.document_id == doc_id,
            ArtifactMessage.role.in_(("question", "user", "synthesis")),
        ).order_by(ArtifactMessage.seq)
    )).scalars().all()
    relevant = []
    for m in rows:
        uk = m.meta.get("unit_key") if m.meta else None
        if uk is None or uk == unit_key:
            role = m.role
            prefix = {"question": "Q", "user": "A", "synthesis": "S"}.get(role, role)
            relevant.append(f"{prefix}: {m.content}")
    return "\n".join(relevant) or "(none yet)"


async def _serialize_current_modules_with_children(doc_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """JSON-serialize the current state of modules + all child rows for idempotent regen."""
    from app.models.frs import (
        FrsModule, FrsModuleActor, FrsModuleResponsibility,
        FrsModuleInterface, FrsModuleDataEntity, FrsSpec,
    )

    modules = (await db.execute(
        select(FrsModule).where(
            FrsModule.document_id == doc_id,
            FrsModule.is_current.is_(True),
            FrsModule.status == "active",
        )
    )).scalars().all()

    async def _children(model, mod_row_key):
        return [{
            "row_key": c.row_key,
            **{col: getattr(c, col) for col in FRS_TYPED_COLS[model.__tablename__]
               if col not in ("module_row_key",)},
            "_is_locked": c.is_locked,
        } for c in (await db.execute(
            select(model).where(
                model.document_id == doc_id,
                model.module_row_key == mod_row_key,
                model.is_current.is_(True),
                model.status == "active",
            )
        )).scalars().all()]

    out = []
    for m in modules:
        out.append({
            "row_key": m.row_key,
            "name": m.name, "slug": m.slug, "layer": m.layer,
            "scope_in": m.scope_in, "scope_out": m.scope_out, "summary": m.summary,
            "_is_locked": m.is_locked,
            "actors": await _children(FrsModuleActor, m.row_key),
            "responsibilities": await _children(FrsModuleResponsibility, m.row_key),
            "interfaces": await _children(FrsModuleInterface, m.row_key),
            "data_entities": await _children(FrsModuleDataEntity, m.row_key),
            "frs_backlog": await _children(FrsSpec, m.row_key),
        })
    return out


async def _emit_modularize_messages(doc: ArtifactDocument, result: dict, db: AsyncSession):
    """Emit artifact_messages for: synthesis summary + each open SpecDecision."""
    seq = await _next_frs_seq(doc.id, db)

    # 1. Synthesis message
    mod_count = len(result.get("modules", []))
    total_stubs = sum(len(m.get("frs_backlog", [])) for m in result.get("modules", []))
    synthesis = (
        f"Modularization complete: {mod_count} module{'s' if mod_count != 1 else ''}, "
        f"{total_stubs} FRS backlog stub{'s' if total_stubs != 1 else ''}. "
        f"Confidence: {result.get('confidence', 'low')}."
    )
    db.add(ArtifactMessage(
        document_id=doc.id, project_id=doc.project_id,
        role="synthesis", content=synthesis, citations=[], meta={"unit_key": "modularize"},
        seq=seq,
    ))
    seq += 1

    # 2. SpecDecision messages — one per open module-scoped decision
    for d in result.get("spec_decisions", []):
        if d.get("spec_row_key"):
            continue
        body = (
            f"[SPEC-DECISION] {d['question']}\n"
            f"AI recommends option {d['recommended_index']}: {d['recommended_rationale']}"
        )
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=doc.project_id,
            role="question", content=body, citations=[],
            meta={
                "unit_key": "modularize",
                "type": "spec_decision_open",
                "decision_row_key": d["row_key"],
                "module_row_key": d.get("module_row_key"),
            },
            seq=seq,
        ))
        seq += 1


async def _next_frs_seq(doc_id: uuid.UUID, db: AsyncSession) -> int:
    from sqlalchemy import func
    cur = await db.scalar(
        select(func.coalesce(func.max(ArtifactMessage.seq), 0)).where(
            ArtifactMessage.document_id == doc_id
        )
    )
    return (cur or 0) + 1


# Full FRS pipeline (Stage A + Stage B; Stage B added in E4c-frs-functional-design plan)

async def generate_frs_all(project: Project, db: AsyncSession, *, brief: str | None = None) -> dict:
    doc = await _ensure_frs_document(project.id, db)

    if brief and brief.strip():
        seq = await _next_frs_seq(doc.id, db)
        db.add(ArtifactMessage(
            document_id=doc.id, project_id=project.id, role="user",
            content=brief.strip(), citations=[], meta={"is_initial_brief": True}, seq=seq,
        ))
        await db.flush()
        await db.commit()

    # Reset unit_status so the theater starts clean
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id, artifact_type="frs")

    # Stage A — modularize
    await generate_frs_modularize(project, doc, bundle, db)
    await db.commit()

    # Stage B (when shipped) is triggered next; for Stage-A-only mode, return here.
    # Default behavior: status stays at "generating" so caller decides next move.
    # When Stage B is built, this method continues; for v1-with-only-Stage-A:
    doc.status = "in_interview"
    await db.commit()
    return await get_frs_detail(project.id, db)


async def get_frs_detail(project_id: uuid.UUID, db: AsyncSession) -> dict:
    """Hydrate the full FRS state for the GET endpoint."""
    # … see PRD §6 for full implementation; returns:
    # { document, modules: {<mod_row_key>: {module + actors + ... + backlog}}, messages, sources }
    pass  # implementation in actual file
```

### 3.8 Validator (Stage A rules)

**File**: `backend/app/services/artifacts/validators/frs.py` (NEW — Stage A section)

See PRD §6.5 for the validation rules. Implementation follows the BRD validator pattern with
these specific checks:

- Critical: `zero_modules`, `module_zero_backlog`, `cross_module_cycle`
- Major: `module_tech_name` (capability-language enforcement)
- Coverage: `br_uncovered_in_modules` (Must-priority BRs not in any backlog stub)
- Warnings: `module_under_decomposed` (<2 stubs), `module_over_loaded` (>15 stubs),
  `open_module_decision`

Helpers reused: `_active_rows`, `_finding`, `_GROUP_ORDER` from `validators/brd.py`.

The cycle detector:

```python
def _detect_cross_module_cycle(interfaces: list) -> list[str] | None:
    """Build a directed graph of inter-module dependencies and detect cycles via DFS."""
    graph: dict[str, set[str]] = {}
    for iface in interfaces:
        if iface.direction == "outbound" and iface.counterpart:
            graph.setdefault(iface.module_row_key, set()).add(iface.counterpart)
    visited: dict[str, str] = {}  # WHITE/GREY/BLACK
    path: list[str] = []
    def dfs(node: str) -> list[str] | None:
        if visited.get(node) == "GREY":
            idx = path.index(node)
            return path[idx:] + [node]
        if visited.get(node) == "BLACK":
            return None
        visited[node] = "GREY"; path.append(node)
        for nb in graph.get(node, set()):
            cycle = dfs(nb)
            if cycle: return cycle
        path.pop(); visited[node] = "BLACK"
        return None
    for n in list(graph.keys()):
        if visited.get(n) != "BLACK":
            cycle = dfs(n)
            if cycle: return cycle
    return None
```

### 3.9 API endpoints

**File**: `backend/app/api/frs.py` (NEW — Stage A endpoints only here; Stage B extends)

Routes per PRD §6.6. Key details:

- **All POST mutations** return the full FRS detail (mirror of BRD endpoints) so the frontend
  doesn't need a second GET to refresh.
- **POST /generate** returns immediately with status='generating'; client polls /artifacts/frs
  every 2s. (Long-running generation runs in Celery; mock mode runs in-process.)
- **POST /reset-generating** is the safety hatch when a Celery worker dies mid-modularize.
- **Edit endpoint** accepts optional `expected_version` for optimistic concurrency:

```python
class _RowEditIn(BaseModel):
    fields: dict[str, Any]
    expected_version: int | None = None
    lock: bool = False

@router.post("/projects/{project_id}/artifacts/frs/{table}/{row_id}/edit")
async def edit_frs_row(...):
    if body.expected_version is not None and row.version != body.expected_version:
        err("version_conflict", f"Row was modified by another session (now v{row.version})", 409)
    # … proceed with versioned edit …
```

### 3.10 Celery task

**File**: `backend/workers/tasks.py` (EXTEND)

```python
@celery_app.task(name="generate_frs", bind=True)
def generate_frs(self, project_id: str):
    return _run_async(_generate_frs(uuid.UUID(project_id)))


async def _generate_frs(project_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        project = (await db.execute(
            select(Project).where(Project.id == project_id)
        )).scalar_one()
        await generate_frs_all(project, db)
```

**File**: `backend/workers/dispatch.py` (EXTEND)

Register `generate_frs` and the future `incorporate_frs_answer`, `regenerate_frs_module`
tasks.

### 3.11 Observability

Every key transition logs a structured event with `extra=` fields:

| Event | Fields | Triggered |
|-------|--------|-----------|
| `frs.modularize.start` | doc_id, brd_status, locked_count | Before LLM call |
| `frs.modularize.complete` | doc_id, module_count, decision_count, completeness, confidence | After persist |
| `frs.modularize.timeout` | doc_id | LLM exceeded 90s |
| `frs.row.edit` | doc_id, table, row_key, version, source | edit_frs_row called |
| `frs.row.lock` | doc_id, table, row_key | is_locked → True |
| `frs.validate.run` | doc_id, finding_counts | run_frs_validation |
| `frs.decision.resolve` | doc_id, decision_row_key, chosen_index | Decision MCQ resolved |

All flow into the existing audit log machinery (`AuditEvent`).

---

## 4. Frontend — brilliant UI (detailed)

### 4.1 Visual design tokens (FRS-specific extensions)

All FRS-specific tokens are added to `app/globals.css` `:root` — same token system the BRD
and CB use. **No new colour palettes; just semantic aliases** so theming stays one-file.

```css
:root {
  /* ── FRS Layer accents (semantic aliases of existing tokens) ── */
  --frs-layer-foundation:        #B45309;   /* amber-700 — Layer 0 (cross-cutting standards) */
  --frs-layer-foundation-bg:     #FEF3C7;   /* amber-100 */
  --frs-layer-foundation-border: #FCD34D;   /* amber-300 */

  --frs-layer-vertical:          var(--accent);          /* emerald — Layer 1 (feature) */
  --frs-layer-vertical-bg:       var(--accent-subtle);
  --frs-layer-vertical-border:   var(--accent-subtle);

  --frs-layer-cross-cutting:     #2C5A7A;   /* deep-info — Layer 2 (cross-cutting overlay) */
  --frs-layer-cross-cutting-bg:  #E0F2FE;
  --frs-layer-cross-cutting-border: #BAE6FD;

  /* ── FRS Priority pill colours (MoSCoW for FRS uses P0–P3) ── */
  --frs-priority-p0:        #DC2626;   /* red-600 — must-have */
  --frs-priority-p0-bg:     #FEE2E2;
  --frs-priority-p1:        #D97706;   /* amber-600 — should */
  --frs-priority-p1-bg:     #FEF3C7;
  --frs-priority-p2:        #2563EB;   /* blue-600 — could */
  --frs-priority-p2-bg:     #DBEAFE;
  --frs-priority-p3:        #6B7280;   /* gray-500 — won't */
  --frs-priority-p3-bg:     #F3F4F6;

  /* ── FRS Trace chip colours (new target kinds for Stage A) ── */
  --frs-trace-brd-bg:       #FCE7F3;   /* pink-100; differentiates from CB green */
  --frs-trace-brd:          #BE185D;   /* pink-700 */
  --frs-trace-brd-border:   #F9A8D4;

  --frs-trace-cb-bg:        var(--accent-subtle);
  --frs-trace-cb:           var(--accent);
  --frs-trace-cb-border:    var(--accent);

  --frs-trace-app-bg:       #DBEAFE;
  --frs-trace-app:          #1E40AF;
  --frs-trace-app-border:   #93C5FD;

  --frs-trace-doc-bg:       #E0F2FE;
  --frs-trace-doc:          #0369A1;
  --frs-trace-doc-border:   #7DD3FC;

  --frs-trace-qa-bg:        #EDE9FE;
  --frs-trace-qa:           #6D28D9;
  --frs-trace-qa-border:    #C4B5FD;

  /* ── FRS Module-rail accents ── */
  --frs-rail-active-bg:     var(--accent-subtle);
  --frs-rail-active-border: var(--accent);
  --frs-rail-hover-bg:      var(--bg-elevated);

  /* ── Construction-site theater accents ── */
  --frs-theater-bg:         #FAFAF9;       /* stone-50 — calm */
  --frs-theater-step-done:  var(--accent);
  --frs-theater-step-current: #2563EB;      /* blue-600 */
  --frs-theater-step-queue: #D6D3D1;        /* stone-300 */
}
```

**Layer icons** (lucide-react) auto-picked from `Layer` enum:
- Layer 0 `foundation` → `<Anchor>` (16px, amber-700)
- Layer 1 `vertical`  → `<Layers>` (16px, emerald accent)
- Layer 2 `cross_cutting` → `<Network>` (16px, deep-info)

**Capability icons** (lucide-react) heuristically picked from module `slug`:
| Slug contains | Icon |
|---------------|------|
| `auth`, `identity`, `login` | `<KeyRound>` |
| `notif`, `email`, `alert` | `<Bell>` |
| `intake`, `submission`, `onboarding`, `registration` | `<UserPlus>` |
| `triage`, `routing`, `classification` | `<GitBranch>` |
| `payment`, `billing`, `settlement` | `<CreditCard>` |
| `audit`, `compliance`, `log` | `<ScrollText>` |
| `cross-cutting`, `standards`, `foundation` | `<Anchor>` |
| _default_ | `<Box>` |

### 4.2 Workspace chip update

**File**: `frontend/app/projects/[id]/page.tsx` (EXTEND — already partially done in BRD work)

Add `useSWR` for FRS detail next to the existing BRD detail hook, and wire the chip to gate
on `brdValidated`:

```tsx
const { data: brdDetail } = useSWR(
  `brd-detail-${projectId}`,
  () => api.brd.get(projectId),
  { revalidateOnFocus: false },
)
const { data: frsDetail } = useSWR(
  `frs-detail-${projectId}`,
  () => api.frs.get(projectId),
  {
    revalidateOnFocus: false,
    refreshInterval: (data) => {
      const status = data?.document?.status
      if (status === 'generating') return 2000
      if (data?.document?.unit_status?.['_current_unit']) return 2000
      return 0
    },
  },
)

const brdValidated = brdDetail?.document?.status === 'validated'
const frsStatus = frsDetail?.document?.status ?? null

function frsStatusBadge() {
  if (!frsStatus) return null
  if (frsStatus === 'generating')
    return <span className="text-[9px] rounded px-1.5 py-0.5 bg-blue-100 text-blue-700 font-semibold animate-pulse">Generating…</span>
  if (frsStatus === 'validated')
    return <span className="text-[9px] rounded px-1.5 py-0.5 bg-emerald-100 text-emerald-700 font-semibold">Validated ✓</span>
  if (frsStatus === 'in_interview')
    return <span className="text-[9px] rounded px-1.5 py-0.5 bg-amber-100 text-amber-700 font-semibold">Draft</span>
  return null
}

const frsSublabel = !frsStatus
  ? (brdValidated ? 'Functional Specifications' : 'Unlocks after BRD')
  : frsStatus === 'generating' ? 'Generating…'
  : frsStatus === 'validated' ? 'Validated'
  : 'Draft · in progress'

// In the artifact rail:
<NavItem
  label="FRS"
  sublabel={frsSublabel}
  icon={<Layers size={14} />}
  active={view === 'frs'}
  locked={!brdValidated}
  badge={frsStatusBadge()}
  onClick={brdValidated ? () => setView('frs') : undefined}
/>
```

When `view === 'frs'`, the workspace renders `<FrsBuilderView projectId={projectId} onBack={() => setView(null)} />`.

### 4.3 The 7 builder surfaces

The `FrsBuilderView` is a state machine that renders one of 7 surfaces based on the artifact
state:

| State | Trigger | Surface rendered |
|-------|---------|------------------|
| **S0 — Readiness blocked** | `readiness.can_generate === false` | `FrsBlockedState` (banner) |
| **S1 — Empty** | `doc === null` | `FrsEmptyState` |
| **S2 — Discover** | `doc !== null && messages.some(role=='discover_q')` | `FrsDiscoverPhase` (reuses `DiscoverPhase`) |
| **S3 — Generating** | `doc.status === 'generating'` | `FrsConstructionTheater` |
| **S4 — Builder** | `doc.status === 'in_interview'` | `FrsBuilderBody` (module rail + active surface) |
| **S5 — Findings drawer** | `showFindings === true` | `FrsModularizeFindings` slides over S4 |
| **S6 — Validated** | `doc.status === 'validated'` | S4 with all locks visible + Continue banner |

Each surface is detailed below.

### 4.4 S1 — Empty state (the warm welcome)

**File**: `frontend/app/components/frs/FrsEmptyState.tsx` (NEW)

The empty state must do four jobs in one screen:
1. Communicate that this is a 2-stage pipeline (set expectations)
2. Show the 4-layer grounding (build trust in provenance)
3. Capture an optional brief (let the user shape the modularization)
4. Nudge upload of NFR/Architecture docs (improve grounding)

**Wireframe**:

```
                              ┌────────────────────────────────┐
                              │                                │
                              │            ✦                   │
                              │     (w-16 h-16 amber-50         │
                              │      ring, gentle pulse)        │
                              │                                │
                              └────────────────────────────────┘

                        Build the Functional Specifications

         Decompose your validated BRD into business-capability modules.
         Stage 1 of 2 — Stage 2 (per-module design) runs automatically
         after Stage 1 completes.

   ┌──────────────────────────────────────────────────────────────────────┐
   │  ⚡ Grounded in 4 sources:                                            │
   │                                                                       │
   │  ╔══════════════╗  ╔══════════════╗  ╔══════════════╗  ╔══════════╗  │
   │  ║ App Brain    ║  ║ Documents    ║  ║ Concept Brief║  ║ BRD      ║  │
   │  ║ 2 apps · 47  ║  ║ 5 docs       ║  ║ Validated v2 ║  ║ Validated║  │
   │  ║ facts        ║  ║ ready        ║  ║ 2 days ago   ║  ║ v1 · 2d  ║  │
   │  ║ ✓ ready      ║  ║ ✓ ready      ║  ║ ✓ ready      ║  ║ ✓ ready  ║  │
   │  ╚══════════════╝  ╚══════════════╝  ╚══════════════╝  ╚══════════╝  │
   └──────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────────────┐
   │ Optional brief — what's the focus of this FRS bundle?               │
   │                                                                       │
   │  e.g., "MVP for claims chatbot — focus on intake + triage flows.    │
   │  Notifications module should be its own unit."                       │
   │                                                                       │
   │                                                       [✦ AI Enhance] │
   └──────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────────────┐
   │ ℹ  Recommended: upload NFR / Architecture docs                       │
   │   Detected so far: 0 files matching nfr*, architecture*, technical-* │
   │   The AI will ground modularization on whatever exists.              │
   │   [Upload now]                                                        │
   └──────────────────────────────────────────────────────────────────────┘

                            ┌──────────────────────────┐
                            │  Discover & Continue →  │
                            └──────────────────────────┘
```

**Micro-interactions**:
- Each source card animates in with a 220 ms staggered fade-up (50 ms delay per card)
- The `✦` icon at the top has a subtle 2s breathing pulse (scale 1 → 1.04 → 1), gated by `useReducedMotion`
- `[✦ AI Enhance]` is a one-shot button that calls `api.frs.discoverEnhance({brief})`, returns a polished version, fades it into the textarea (300 ms cross-fade)
- The CTA is `disabled` while `readiness.can_generate === false`; tooltip explains why
- If any source card status is `pending`, the CTA shows "Waiting for sources…" instead and polls readiness every 3s

**Brilliant touches**:
- Source cards use the **3-state visual language** (ready=emerald check, pending=amber clock, stale=red triangle) — same as BRD's SourceStrip
- The brief textarea has **content-aware placeholder** showing 1 of 3 randomized example briefs each visit (subtle freshness)
- "AI Enhance" button has a tiny chevron arrow that animates ↓ on hover (signals "enhance below")

### 4.5 S2 — Discover phase (FRS catalog wired in)

**File**: `frontend/app/components/frs/FrsDiscoverPhase.tsx` (NEW — thin wrapper)

Reuses the existing `DiscoverPhase` component from `app/components/`. Just routes the
catalog:

```tsx
import { DiscoverPhase } from '@/app/components/DiscoverPhase'
import { FRS_DISCOVER_CATEGORIES, FRS_DISCOVER_QUESTIONS } from '@/lib/frs-manifest'

export function FrsDiscoverPhase({ projectId, onComplete }: { projectId: string; onComplete: () => void }) {
  return (
    <DiscoverPhase
      artifactType="frs"
      categories={FRS_DISCOVER_CATEGORIES}
      questions={FRS_DISCOVER_QUESTIONS.filter(q =>
        // Only show questions mapped to Stage A's modularize unit
        ['frs_1a', 'frs_1b', 'frs_2a', 'frs_3a', 'frs_3b', 'frs_4a', 'frs_9a'].includes(q.key)
      )}
      onAnalyze={async (brief) => api.frs.discoverAnalyze(projectId, brief)}
      onAnswer={(qKey, answer) => api.frs.discoverAnswer(projectId, qKey, { answer })}
      onEnhance={(brief) => api.frs.discoverEnhance(projectId, brief)}
      onContinue={async () => {
        await api.frs.generate(projectId)
        onComplete()
      }}
    />
  )
}
```

**Brilliant touches inherited from `DiscoverPhase`**:
- Per-category progress segments (`🎯 Scope ▰▰▱` etc.)
- AI-inferred answers shown with subtle dotted underline + source badge
- "Why this matters" tooltip per question explaining its impact on the FRS module

**FRS-specific extras**:
- For Stage A, only 7 of the 12 FRS questions are surfaced (the modularize-mapped ones)
- The "Continue" CTA changes label to "Discover & Modularize →" to set Phase A expectation

### 4.6 S3 — Construction site theater (the hero moment)

**File**: `frontend/app/components/frs/FrsConstructionTheater.tsx` (NEW)

This is **the** brilliant-UI moment for Stage A. A naive impl shows a spinner; the
construction-site theater shows what the AI is *internally* doing across 5 sub-steps.

**Wireframe**:

```
                         Modularizing your BRD…
                 (est. 30–60 s • Stage 1 of 2)

  ┌──────────────────────────────────────────────────────────────────────────┐
  │                                                                            │
  │   ◐ 1. Identifying bounded contexts           ✓                             │
  │     ───────────────────────────────────                                     │
  │     ↳ Grouped 14 BRs into 5 candidate capability clusters                   │
  │                                                                            │
  │   ◐ 2. Validating module boundaries           ◐                             │
  │     ───────────────────────────────────                                     │
  │     ↳ Cohesion vs coupling check… merging Auth + Onboarding rejected       │
  │                                                                            │
  │   ◐ 3. Mapping cross-module contracts         ○                             │
  │     ───────────────────────────────────                                     │
  │                                                                            │
  │   ◐ 4. Generating FRS backlog                 ○                             │
  │     ───────────────────────────────────                                     │
  │                                                                            │
  │   ◐ 5. Hoisting cross-cutting rules           ○                             │
  │     ───────────────────────────────────                                     │
  │                                                                            │
  │                                                                            │
  │                     [ Resume from here ]  ← always visible                  │
  └──────────────────────────────────────────────────────────────────────────┘

           ◐  Right now: validating module boundaries…
              Grounded in: 14 BRs · 6 objectives · 7 discover answers
```

**How it works** (the theatrical simulation):
- DSPy makes ONE call (~30–60s). The 5 sub-steps are a UX layer that **interpolates** progress.
- Frontend timer: each step gets a budget (5s, 8s, 12s, 12s, 5s = ~42s total). State
  transitions on a stepped schedule, with the LLM call running in parallel.
- If the LLM finishes faster than the timer (mock mode: ~1s), all 5 steps flash to ✓ in
  sequence over 600ms (cascade).
- If the LLM exceeds the timer, the **last visible step pulses** (◐) indefinitely until the
  call completes or times out at 90s.

**Implementation**:

```tsx
const STEPS = [
  { key: 'identify',   label: 'Identifying bounded contexts',         budget: 5000 },
  { key: 'validate',   label: 'Validating module boundaries',         budget: 8000 },
  { key: 'contracts',  label: 'Mapping cross-module contracts',       budget: 12000 },
  { key: 'backlog',    label: 'Generating FRS backlog',               budget: 12000 },
  { key: 'crosscut',   label: 'Hoisting cross-cutting rules',         budget: 5000 },
] as const

function FrsConstructionTheater({ projectId, onComplete, onCancel }: Props) {
  const reduce = useReducedMotion()
  const [stepIdx, setStepIdx] = useState(0)
  const [completed, setCompleted] = useState(false)

  // Poll the FRS detail every 2s while generating
  const { data: detail } = useSWR(
    `frs-detail-${projectId}`,
    () => api.frs.get(projectId),
    { refreshInterval: 2000 },
  )
  const status = detail?.document?.status
  const modularizeStatus = detail?.document?.unit_status?.modularize

  // Drive the theatrical timer
  useEffect(() => {
    if (status !== 'generating') return
    let cumulative = 0
    const timers: number[] = []
    for (let i = 0; i < STEPS.length; i++) {
      cumulative += STEPS[i].budget
      timers.push(window.setTimeout(() => setStepIdx(i + 1), cumulative))
    }
    return () => timers.forEach(clearTimeout)
  }, [status])

  // Detect actual completion via polling
  useEffect(() => {
    if (status === 'in_interview' && modularizeStatus?.completeness > 0) {
      // Animate all remaining steps to ✓ before transitioning
      if (!completed) {
        setCompleted(true)
        const remaining = STEPS.length - stepIdx
        if (remaining > 0) {
          for (let i = 0; i < remaining; i++) {
            setTimeout(() => setStepIdx(stepIdx + i + 1), i * 120)
          }
        }
        setTimeout(onComplete, remaining * 120 + 600)
      }
    }
  }, [status, modularizeStatus, completed, stepIdx])

  const currentLabel = stepIdx < STEPS.length ? STEPS[stepIdx].label : 'Finalizing'

  return (
    <div className="flex flex-col h-full bg-[var(--frs-theater-bg)]">
      <div className="shrink-0 h-12 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4">
        <button onClick={onCancel} className="text-sm text-[var(--text-tertiary)]">
          <ArrowLeft size={14} /> Back
        </button>
        <span className="text-sm font-semibold">FRS Builder</span>
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-blue-100 text-blue-700 border border-blue-200">
          <Loader2 size={9} className="animate-spin" /> Modularizing… (Stage 1 of 2)
        </span>
        <div className="flex-1" />
        <button
          onClick={async () => {
            await api.frs.resetGenerating(projectId)
            onCancel()
          }}
          title="If generation is stuck, click to recover — existing modules are preserved"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
        >
          <AlertTriangle size={12} className="text-amber-500" />
          Resume from here
        </button>
      </div>

      <div className="flex-1 overflow-auto px-8 py-12">
        <div className="mx-auto max-w-2xl">
          <p className="text-center text-2xl font-semibold text-[var(--text-primary)]">
            Modularizing your BRD…
          </p>
          <p className="text-center text-sm text-[var(--text-tertiary)] mt-2">
            est. 30–60 s &nbsp;·&nbsp; Stage 1 of 2
          </p>

          <div className="mt-12 space-y-3">
            {STEPS.map((step, i) => {
              const state: 'done' | 'current' | 'queue' =
                i < stepIdx ? 'done' : i === stepIdx ? 'current' : 'queue'
              return (
                <FrsTheaterStep
                  key={step.key}
                  number={i + 1}
                  label={step.label}
                  state={state}
                  reduce={reduce}
                />
              )
            })}
          </div>

          <div className="mt-10 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] px-4 py-3">
            <div className="flex items-center gap-3">
              {reduce ? (
                <Loader2 size={14} className="text-blue-600" />
              ) : (
                <Loader2 size={14} className="text-blue-600 animate-spin" />
              )}
              <p className="text-sm text-[var(--text-secondary)]">
                Right now: <span className="font-semibold">{currentLabel.toLowerCase()}…</span>
              </p>
            </div>
            <p className="mt-1 ml-7 text-[11px] text-[var(--text-tertiary)]">
              Grounded in: {detail?.bundle?.brd_summary?.br_count ?? 0} BRs ·{' '}
              {detail?.bundle?.brd_summary?.objective_count ?? 0} objectives ·{' '}
              {detail?.bundle?.brd_summary?.discover_answer_count ?? 0} discover answers
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function FrsTheaterStep({ number, label, state, reduce }: {
  number: number
  label: string
  state: 'done' | 'current' | 'queue'
  reduce: boolean
}) {
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: 'easeOut' }}
      className={cn(
        'flex items-center gap-3 rounded-xl border px-4 py-3',
        state === 'done' && 'border-[var(--accent)] bg-[var(--accent-subtle)]',
        state === 'current' && 'border-blue-300 bg-blue-50',
        state === 'queue' && 'border-[var(--border-default)] bg-[var(--bg-elevated)] opacity-60',
      )}
    >
      <div className={cn(
        'w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0',
        state === 'done' && 'bg-[var(--accent)] text-white',
        state === 'current' && 'bg-blue-600 text-white',
        state === 'queue' && 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]',
      )}>
        {state === 'done' ? <Check size={12} /> :
         state === 'current' ? <Loader2 size={12} className={reduce ? '' : 'animate-spin'} /> :
         number}
      </div>
      <p className={cn(
        'text-sm font-medium',
        state === 'done' && 'text-[var(--text-primary)]',
        state === 'current' && 'text-blue-900',
        state === 'queue' && 'text-[var(--text-tertiary)]',
      )}>
        {label}
      </p>
    </motion.div>
  )
}
```

**Reduced-motion path**: replaces the spinner with a static dot; cards still get colour
transitions but no scale/pulse animations.

### 4.7 S4 — The Builder body (the main surface)

The builder is a 2-column layout: **Module Rail** on the left (288px) + **active surface**
on the right.

**File**: `frontend/app/components/frs/FrsBuilderBody.tsx` (NEW)

```tsx
function FrsBuilderBody({ projectId, detail, onMutate, onBack, onShowFindings, onContinueStageB }: Props) {
  const { modules, messages } = detail
  const [activeModuleKey, setActiveModuleKey] = useState<string | null>(
    modules?.[0]?.row_key ?? null
  )
  const [showCoverage, setShowCoverage] = useState(false)

  const activeModule = modules?.find(m => m.row_key === activeModuleKey) ?? null
  const validated = detail.document.status === 'validated'

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--bg-base)]">
      {/* Sticky header */}
      <FrsBuilderHeader
        projectId={projectId}
        detail={detail}
        validated={validated}
        onBack={onBack}
        onShowFindings={onShowFindings}
        onShowCoverage={() => setShowCoverage(true)}
        onContinueStageB={onContinueStageB}
      />

      {/* Two-column body */}
      <div className="flex flex-1 overflow-hidden">
        <FrsModuleRail
          modules={modules}
          activeModuleKey={activeModuleKey}
          onSelectModule={setActiveModuleKey}
          onMutate={onMutate}
        />

        <div className="flex-1 overflow-auto">
          <FrsSourceStrip projectId={projectId} readiness={detail.readiness} />
          <FrsBrdEchoStrip brdSummary={detail.bundle?.brd_summary} projectId={projectId} />

          {activeModule ? (
            <FrsModulePanel
              projectId={projectId}
              module={activeModule}
              onMutate={onMutate}
            />
          ) : (
            <FrsModuleEmpty modules={modules} />
          )}
        </div>
      </div>

      {/* Continue to Stage 2 banner (when ready) */}
      {!validated && detail.findingsSummary?.blocking === 0 && (
        <FrsContinueStageBBanner
          moduleCount={modules?.length ?? 0}
          stubCount={modules?.flatMap(m => m.backlog ?? []).length ?? 0}
          onContinue={onContinueStageB}
        />
      )}

      {/* Coverage modal */}
      {showCoverage && (
        <FrsCoverageModal
          projectId={projectId}
          modules={modules}
          onClose={() => setShowCoverage(false)}
        />
      )}
    </div>
  )
}
```

#### 4.7.a SourceStrip (extended with 4th BRD layer)

**File**: `frontend/app/components/brd/SourceStrip.tsx` (EXTEND)

The existing `SourceStrip` is extended to accept an optional `brdStatus` and counts:

```tsx
interface Props {
  projectId: string
  readiness: BrdBundleReadiness | FrsBundleReadiness
  cbStatus?: string
  brdStatus?: string                      // NEW
  brdCounts?: { brs: number; objectives: number; risks: number; kpis: number }
  onManageSources?: () => void
}

export function SourceStrip({ readiness, cbStatus, brdStatus, brdCounts, onManageSources }: Props) {
  // … existing 3 rows (App Brain / Documents / Concept Brief) …

  // NEW 4th row — BRD layer (only when brdStatus is provided)
  if (brdStatus) {
    const brdStatusParsed = !brdStatus ? 'missing' :
      brdStatus === 'validated' ? 'ready' :
      brdStatus === 'generating' ? 'pending' :
      'stale'
    return (
      <>
        {/* … existing 3 rows … */}
        <SourceRow
          label="BRD"
          description={
            brdStatus === 'validated' && brdCounts
              ? `${brdCounts.brs} BRs · ${brdCounts.objectives} objectives · ${brdCounts.risks} risks · ${brdCounts.kpis} KPIs`
              : brdStatus === 'generating' ? 'Generating…'
              : 'Draft — not validated'
          }
          status={brdStatusParsed}
          accentColor="border-l-pink-500"           // pink to differentiate from CB green
          icon={<BookOpen size={13} />}
          expandedContent={
            brdStatus === 'validated' && brdCounts ? (
              <div className="space-y-1 text-xs text-[var(--text-secondary)]">
                <p>This FRS will be grounded on every BRD row.</p>
                <p>Click "Open BRD →" to view in read-only mode.</p>
              </div>
            ) : undefined
          }
        />
      </>
    )
  }
  // …
}
```

#### 4.7.b BRD Echo Strip

**File**: `frontend/app/components/frs/FrsBrdEchoStrip.tsx` (NEW)

A collapsed single-line strip below `SourceStrip` that summarises the BRD essence (mirrors
`CbEchoStrip` from BRD builder):

```
▸ BRD essence · 14 BRs · 6 objectives · 5 risks · 4 KPIs · "claims chatbot"   [Open BRD →]
```

Expanded:
```
▾ BRD essence
   Project: claims chatbot
   ───────────────────────────
   Top objectives:
     • [OBJ-001] (must) Reduce reconciliation time by 70%
     • [OBJ-002] (must) Improve customer claim experience
     • [OBJ-003] (should) Enable real-time SLA visibility
   Top BRs by priority:
     • [BR-001] (must) Reconcile premium collections within 7 days
     • [BR-002] (must) Validate customer identity at intake
     …
   Top risks:
     • [RSK-001] (high/medium) Integration with legacy CRM may delay launch
   [Open BRD →]
```

#### 4.7.c Module Rail (the navigation primitive)

**File**: `frontend/app/components/frs/FrsModuleRail.tsx` (NEW)

```
┌────────────────────────────────┐
│ MODULES         5 · 14 BR ✓    │  ← header w/ summary
│                                │
│ [filter/search bar]            │  ← collapses when ≤8 modules
│                                │
│ ─── Foundation ────────────    │  ← layer group header
│  ⚓ MOD-000 Cross-cutting   2  │  ← stub count badge
│     Standards                  │
│                                │
│ ─── Vertical ──────────────    │
│ ▶ 👤 MOD-001 Customer       3  │  ← active row: accent bg + bold + tick
│       Intake                   │
│ ▶ 🔑 MOD-002 Authentication 2  │
│ ▶ 🌿 MOD-003 Claims Triage  3  │
│ ▶ 🔔 MOD-004 Notifications  2  │
│                                │
│ [+ Add Module]                 │
└────────────────────────────────┘
```

**Visual rules**:
- **Layer grouping**: modules grouped by `layer` (Foundation first, then Vertical, then Cross-cutting). Group header is `text-[10px] uppercase tracking-widest text-tertiary` with a horizontal rule.
- **Capability icon**: auto-picked per §4.1 mapping. Background tint per layer (`--frs-layer-foundation-bg` for MOD-000 etc.).
- **Stub count badge**: small pill at the right, colored by completeness (0 = grey, 1–14 = neutral, >15 = amber warning, 0 = red critical).
- **Active row**: full-width accent-subtle background + left border 2px accent + bold name.
- **Locked module**: small 🔒 chip next to the count badge with tooltip "Locked — will be preserved on regenerate".
- **Hover state**: row reveals on hover, with an inline "Glance card" sliding out to the right (250ms ease-out):

```
                                    ┌────────────────────────────────────┐
▶ 👤 MOD-001 Customer Intake     3 │ 👤 Customer Intake  (Layer 1)        │
                                    │ ────────────────────────────────────│
                                    │ "Captures new claims initiated by   │
                                    │  customers through the chatbot…"    │
                                    │                                     │
                                    │ 3 backlog · 4 actors · 3 interfaces │
                                    │ Covers BRs: BR-001, BR-002, BR-003, │
                                    │             BR-004, BR-007          │
                                    │                                     │
                                    │ [Open] [Regenerate] [Lock] [Delete] │
                                    └────────────────────────────────────┘
```

- **Right-click context menu**: "Regenerate this module", "Lock all rows", "Open glance", "Copy module link", "Delete module"

**Filter/search bar** (appears when module count > 8):
- Input filter: instant filter on name/slug
- Layer filter chip: "All" | "Foundation" | "Vertical" | "Cross-cutting"
- Priority filter chip: shows when any module has flagged stubs (P0/P1)

```tsx
function FrsModuleRail({ modules, activeModuleKey, onSelectModule, onMutate }: Props) {
  const [filter, setFilter] = useState('')
  const [layerFilter, setLayerFilter] = useState<'all' | FrsLayer>('all')
  const showFilter = modules.length > 8

  const grouped = useMemo(() => {
    let filtered = modules.filter(m =>
      (filter === '' || m.name.toLowerCase().includes(filter.toLowerCase()) || m.slug.includes(filter)) &&
      (layerFilter === 'all' || m.layer === layerFilter)
    )
    const byLayer: Record<string, typeof modules> = {
      foundation: [], vertical: [], cross_cutting: [],
    }
    filtered.forEach(m => byLayer[m.layer].push(m))
    return byLayer
  }, [modules, filter, layerFilter])

  const totalStubs = modules.reduce((sum, m) => sum + (m.backlog?.length ?? 0), 0)
  const totalBRs = new Set(modules.flatMap(m => m.backlog?.flatMap(s => s.br_refs ?? []) ?? [])).size

  return (
    <aside className="w-72 shrink-0 flex flex-col border-r border-[var(--border-default)] bg-[var(--bg-surface)] overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-3 py-3 border-b border-[var(--border-subtle)]">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            Modules
          </p>
          <p className="text-[11px] text-[var(--text-tertiary)]">
            {modules.length} · {totalStubs} stubs · {totalBRs} BRs
          </p>
        </div>

        {showFilter && (
          <>
            <input
              value={filter} onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter modules…"
              className="mt-2 w-full rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-2 py-1 text-xs"
            />
            <div className="mt-2 flex gap-1 text-[10px]">
              {(['all', 'foundation', 'vertical', 'cross_cutting'] as const).map(l => (
                <button
                  key={l}
                  onClick={() => setLayerFilter(l)}
                  className={cn(
                    'rounded-full px-2 py-0.5',
                    layerFilter === l
                      ? 'bg-[var(--accent-subtle)] text-[var(--accent)] font-semibold'
                      : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'
                  )}
                >
                  {l === 'all' ? 'All' : LAYER_LABELS[l]}
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Module list grouped by layer */}
      <div className="flex-1 overflow-y-auto py-2">
        {(['foundation', 'vertical', 'cross_cutting'] as const).map(layer => {
          const rows = grouped[layer]
          if (rows.length === 0) return null
          return (
            <div key={layer} className="mb-3">
              <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
                {LAYER_LABELS[layer]}
              </p>
              {rows.map(m => (
                <FrsModuleRailItem
                  key={m.row_key}
                  module={m}
                  active={m.row_key === activeModuleKey}
                  onClick={() => onSelectModule(m.row_key)}
                  onMutate={onMutate}
                />
              ))}
            </div>
          )
        })}
      </div>

      {/* Footer */}
      <div className="shrink-0 px-3 py-3 border-t border-[var(--border-subtle)]">
        <button className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-[var(--border-default)] py-2 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors">
          <Plus size={13} /> Add Module
        </button>
      </div>
    </aside>
  )
}


function FrsModuleRailItem({ module: m, active, onClick, onMutate }: ItemProps) {
  const Icon = pickCapabilityIcon(m.slug)
  const stubCount = m.backlog?.length ?? 0
  const stubBadgeColour =
    stubCount === 0 ? 'bg-red-100 text-red-700' :
    stubCount > 15 ? 'bg-amber-100 text-amber-700' :
    stubCount < 2 ? 'bg-amber-50 text-amber-600' :
    'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'

  return (
    <button
      onClick={onClick}
      className={cn(
        'group w-full flex items-center gap-2 px-3 py-2 text-left transition-colors',
        active && 'bg-[var(--accent-subtle)] border-l-2 border-[var(--accent)]',
        !active && 'hover:bg-[var(--bg-elevated)] border-l-2 border-transparent',
      )}
    >
      <span className={cn('shrink-0', active ? 'text-[var(--accent)]' : 'text-[var(--text-secondary)]')}>
        <Icon size={14} />
      </span>
      <div className="flex-1 min-w-0">
        <p className={cn('text-sm truncate', active ? 'font-semibold text-[var(--text-primary)]' : 'text-[var(--text-secondary)]')}>
          {m.name}
        </p>
        <p className="text-[10px] text-[var(--text-tertiary)] truncate">
          {m.row_key}
        </p>
      </div>
      <span className={cn('shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold', stubBadgeColour)}>
        {stubCount}
      </span>
      {m.is_locked && <Lock size={11} className="text-amber-600" />}
    </button>
  )
}
```

#### 4.7.d Module Panel (the rich body)

**File**: `frontend/app/components/frs/FrsModulePanel.tsx` (NEW)

Renders the **Module Identity Card** at the top followed by 7 collapsible sections:
Scope, Actors, Responsibilities, UI Surfaces, APIs, Events, Data, Backlog. Plus inline
[SPEC-DECISION] banners.

**Wireframe**:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ ┌─ MODULE IDENTITY CARD ──────────────────────────────────────────────────┐ ║
║ │  👤  Customer Intake                            Layer 1 · Vertical Feature│ ║
║ │      ─────────────────────────                                          │ ║
║ │      MOD-001 · v3 · last edited 2m ago                                  │ ║
║ │                                                                          │ ║
║ │      "Captures new claims initiated by customers through the chatbot     │ ║
║ │       interface, validates basic policy and identity fields, and hands   │ ║
║ │       off to triage."                                                    │ ║
║ │                                                                          │ ║
║ │      [Edit] [Regenerate this module] [Lock] [⤴ History] [⋮ More]        │ ║
║ │                                                                          │ ║
║ │      ┌─────────────┬─────────────┬─────────────┬─────────────┐         │ ║
║ │      │ 3 backlog   │ 4 actors    │ 3 interfaces│ 1 entity    │         │ ║
║ │      │ stubs       │             │             │             │         │ ║
║ │      └─────────────┴─────────────┴─────────────┴─────────────┘         │ ║
║ │      Covers BRs: [BR-001] [BR-002] [BR-003] [BR-004] [BR-007] [+2 more]│ ║
║ └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                              ║
║ ⚠ 1 [SPEC-DECISION] pending — "Server-side vs client-side session token?"  ║
║   [Review →]                                                                 ║
║                                                                              ║
║ ▾ Scope                                                                      ║
║   In scope:                                                                  ║
║     • New customer claim submissions via chatbot                             ║
║     • Initial validation of claim details                                    ║
║     • Routing to triage queue                                                ║
║   Out of scope:                                                              ║
║     • Claim adjudication (owned by MOD-003 Claims Triage)                    ║
║     • Notifications (owned by MOD-004 Notifications)                         ║
║                                                                              ║
║ ▾ Actors & Dependencies (3)                                    [+ Add actor] ║
║   ┌────────────────┬────────────────────┬───────────────────────────────┐   ║
║   │ Customer       │ primary_user       │ Initiates claim submission    │ 🔒│
║   │ Auth Module    │ dependency         │ Validates customer identity   │   │
║   │ Triage Module  │ downstream_consumer│ Receives validated claim      │   │
║   └────────────────┴────────────────────┴───────────────────────────────┘   ║
║                                                                              ║
║ ▾ Responsibilities (4)                                          [+ Add]      ║
║   • Accept claim submission from chatbot UI    [→ M001-FRS001]              ║
║   • Validate policy + identity                  [→ M001-FRS001, M001-FRS002]║
║   • Capture incident description                [→ M001-FRS002]              ║
║   • Hand off validated claim to triage          [→ M001-FRS003]              ║
║                                                                              ║
║ ▾ Interfaces (5 — 1 UI · 1 API · 1 Event · 0 more)                         ║
║   [ Mini contract graph SVG goes here — see §4.7.e ]                        ║
║                                                                              ║
║   UI Surfaces (1):                                                           ║
║     ┌────────────────────────────────────────────────────────────────┐     ║
║     │ Claim Submission Form │ Customer │ Step-by-step intake flow → M001-FRS002│ ║
║     └────────────────────────────────────────────────────────────────┘     ║
║                                                                              ║
║   APIs (1 inbound · 1 outbound):                                             ║
║     ← out · rest │ validateCustomer    → Authentication Module → M001-FRS001║
║                                                                              ║
║   Events (1):                                                                ║
║     → out · event_bus │ claim_submitted → Claims Triage Module → M001-FRS003║
║                                                                              ║
║ ▾ Owned Data (1)                                                [+ Add]      ║
║   • claim_draft       MOD-001 Customer Intake    "In-progress claim during intake"║
║                                                                              ║
║ ▾ FRS Backlog (3 stubs)                                       [+ Add stub]   ║
║   ┌─ M001-FRS001 ── Customer Identity Validation ── [P0] ──────────────┐    ║
║   │  Trace: [← BR-001] [← BR-007]                                       │    ║
║   │  Stub: "Validate policy number and identity before…"                │    ║
║   │  Status: Stub awaiting Stage 2  [Design now →]                      │    ║
║   └────────────────────────────────────────────────────────────────────┘    ║
║   ┌─ M001-FRS002 ── Claim Intake Form ── [P0] ─────────────────────────┐    ║
║   │  Trace: [← BR-002] [← BR-003]                                       │    ║
║   │  Stub: "Step-by-step chatbot dialog to capture incident details"    │    ║
║   │  Status: Stub awaiting Stage 2  [Design now →]                      │    ║
║   └────────────────────────────────────────────────────────────────────┘    ║
║   ┌─ M001-FRS003 ── Triage Handoff ── [P1] ────────────────────────────┐    ║
║   │  Trace: [← BR-004]                                                  │    ║
║   │  Status: Stub awaiting Stage 2  [Design now →]                      │    ║
║   └────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**Section behaviour**:
- All sections collapsible; default expand = Scope + Backlog only (others collapsed for calm density)
- Each section header shows count: `Responsibilities (4)` etc.
- `[+ Add]` button at section header level creates a new row inline (auto-rowkey, blank fields)
- All rows are `EditableRows` (the BRD component) → click to edit, save on blur, version bump, "Saved ✓" toast
- Lock state per row: `is_locked=True` shows 🔒 chip; row body shows a subtle accent ring; double-click rejected with toast "Row is locked — click 🔒 to unlock first"
- Hover any row → reveal action bar on the right (Edit, Delete, Lock toggle, History)

**Module Identity Card**:
- 4-up stat grid that animates count changes (number flips with a 240 ms scale 1→1.15→1)
- "Covers BRs" chips are `FrsTraceChip`s with hover popover showing the BR text excerpt
- "Regenerate this module" calls `POST /artifacts/frs/modules/{row_key}/design` — but in
  Stage A, this re-runs the modularize unit narrowed to just this module (Stage B's per-
  module design endpoint exists in the same handler)

#### 4.7.e Cross-module contract mini-graph

**File**: `frontend/app/components/frs/FrsContractGraph.tsx` (NEW)

A tiny SVG visualisation inside the Interfaces section showing **this module's** inbound
and outbound contracts.

```
                           ┌──────────────┐
                           │  Customer    │  (primary actor)
                           └──────┬───────┘
                                  │ UI
                                  ▼
                    ╔═════════════════════╗
                    ║  MOD-001 Customer   ║   ← centerpiece (active module)
                    ║  Intake             ║
                    ╚════╤════════╤═══════╝
                         │        │
                  outbound API    outbound event
                  validateCustomer claim_submitted
                         │        │
                         ▼        ▼
                  ┌──────────┐  ┌─────────────┐
                  │ MOD-002  │  │ MOD-003     │
                  │ Auth     │  │ Triage      │
                  └──────────┘  └─────────────┘
```

**Implementation**:
- ~150 LOC SVG; auto-laid using a simple radial algorithm:
  - Active module = center (large pill)
  - Inbound dependencies = top half (arrows pointing in)
  - Outbound consumers = bottom half (arrows pointing out)
- Each arrow labeled with `transport` + `name`
- Click an external module → navigate to that module
- Click an arrow → opens that interface row in edit mode
- If a cycle is detected (current module is part of one), the cycle path is highlighted in red

#### 4.7.f Backlog stub cards

**File**: `frontend/app/components/frs/FrsBacklogStubCard.tsx` (NEW)

```tsx
function FrsBacklogStubCard({ stub, projectId, onMutate, onDesignStub }: Props) {
  const priorityCls = `bg-[var(--frs-priority-${stub.priority.toLowerCase()}-bg)] text-[var(--frs-priority-${stub.priority.toLowerCase()})]`
  const hasContent = stub.completeness > 0

  return (
    <div
      className={cn(
        'group rounded-xl border bg-[var(--bg-surface)] px-3 py-2.5 transition-all',
        hasContent
          ? 'border-[var(--accent)]/30 hover:border-[var(--accent)]/60'
          : 'border-dashed border-[var(--border-default)] hover:border-[var(--accent)]/30 hover:bg-[var(--accent-subtle)]/10',
        stub.is_locked && 'ring-1 ring-amber-300',
      )}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-semibold text-[var(--text-tertiary)]">
              {stub.row_key}
            </span>
            <span className={cn('text-[10px] font-semibold rounded px-1.5 py-0.5 border', priorityCls)}>
              {stub.priority}
            </span>
            {stub.is_locked && <Lock size={10} className="text-amber-600" />}
          </div>
          <p className="mt-0.5 text-sm font-medium text-[var(--text-primary)]">
            {stub.title}
          </p>
          <p className="mt-1 text-xs text-[var(--text-tertiary)] line-clamp-2">
            {stub.narrative || 'Stub awaiting Stage 2 design.'}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {stub.br_refs.map(br => (
              <FrsTraceChip
                key={br}
                kind="brd_business_requirement"
                ref={br}
                label={br}
              />
            ))}
          </div>
        </div>

        <div className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
          <button title="Edit stub" className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)]">
            <Pencil size={12} />
          </button>
          <button title="Lock" className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-amber-600">
            <Lock size={12} />
          </button>
          <button title="Delete" className="rounded-md p-1 text-[var(--text-tertiary)] hover:text-red-600">
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Status / action footer */}
      <div className="mt-2 pt-2 border-t border-[var(--border-subtle)] flex items-center gap-2">
        {!hasContent ? (
          <>
            <span className="text-[10px] text-[var(--text-tertiary)]">
              <Clock size={9} className="inline mr-1" /> Stub awaiting Stage 2
            </span>
            <div className="flex-1" />
            <button
              onClick={() => onDesignStub(stub.row_key)}
              className="inline-flex items-center gap-1 rounded-md bg-[var(--accent)] px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-[var(--accent-hover)] transition-colors"
            >
              Design now <ArrowRight size={10} />
            </button>
          </>
        ) : (
          <>
            <span className="text-[10px] text-[var(--accent)] font-semibold">
              <Check size={9} className="inline mr-1" /> Designed · v{stub.version}
            </span>
            <div className="flex-1" />
            <button className="text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent)]">
              Open spec →
            </button>
          </>
        )}
      </div>
    </div>
  )
}
```

#### 4.7.g Module Decision Prompt

**File**: `frontend/app/components/frs/FrsModuleDecisionPrompt.tsx` (NEW)

Triggered by a banner at the top of the module panel. Opens a Radix Popover anchored to the
banner. Layout per PRD §7.7 — three options, AI's pick marked with ⭐, three resolution
buttons.

Backend call on resolution:

```tsx
async function resolve(chosenIndex: number, status: 'accepted_ai' | 'overridden' | 'dismissed') {
  await api.frs.resolveDecision(projectId, decisionRowKey, {
    chosen_index: chosenIndex,
    status,
  })
  if (status === 'overridden') {
    toast.success('Decision overridden — re-modularizing affected scope…')
    onMutate()  // SWR re-fetch will show the regen progress
  } else {
    toast.success('Decision resolved')
    onMutate()
  }
}
```

The orchestrator handles the regen: on `overridden`, it schedules a new modularize call with
the user's choice surfaced in `resolved_decisions` input.

### 4.8 S5 — Findings drawer (Stage-A subset)

**File**: `frontend/app/components/frs/FrsModularizeFindings.tsx` (NEW)

Same shape as BRD's `FindingsDrawer` but with Stage-A finding groups only. The 5-group
hierarchy: **Critical / Major / Minor / Coverage / Warnings**. Each finding renders as a
collapsible card with:
- Severity icon (left)
- Description (bold)
- Suggested fix (smaller, italic)
- Action buttons: `[Accept fix]` (where mechanical), `[Jump to row →]` (smooth-scroll + 600ms red pulse on the target row), `[Edit manually]` (opens row editor modal)
- Inline "✓ Fixed" label after accept-fix runs

**Two-step validate pattern** (from BRD work):
1. User clicks `✓ Check & Validate` in header → calls `GET /findings` → drawer opens read-only
2. After resolving blocking findings, drawer's footer button enables: `[ Continue to Stage 2 → ]`
3. Click → calls `POST /validate` which sets Stage-A "validated"-equivalent state + auto-triggers Stage B

In Stage-A-only mode (without Stage B yet built), the button text is `[ Approve Stage A ]`
which just sets a `stage_a_approved` meta flag on the artifact_document. When Stage B ships,
this transitions to auto-trigger Stage B.

### 4.9 S6 — Continue to Stage 2 banner (the earned moment)

When Stage A is clean (0 critical + 0 major findings), a beautiful banner appears at the
bottom of the builder body:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                                │
│  ✓ Modularization complete · 6 modules · 18 backlog stubs · 14 of 14 BRs ✓    │
│                                                                                │
│  Ready for Stage 2 — per-module FRS design                                    │
│  Estimated 60–120 s, runs in parallel (3 modules at a time)                  │
│                                                                                │
│                            [ Continue to Stage 2 → ]                           │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Brilliant touches**:
- Banner slides up from the bottom with a 280ms ease-out
- Click triggers `BrdConfettiBurst` (reused) — 6 emerald particles, 600ms; gated by reduced-motion
- Then transitions to Stage B's generation theater
- If user dismisses banner via small X, it stays hidden for the session (sessionStorage key)

### 4.10 Refine composer (for follow-up Q&A)

**File**: `frontend/app/components/frs/FrsRefineComposer.tsx` (NEW)

Bottom-of-screen composer (same pattern as BRD's). The "affected scope" chip shows what will
regen when the user submits an answer:

```
[⤴ MOD-001 Customer Intake + dependents]   ← chip indicating regen scope
┌──────────────────────────────────────────────────────┐
│  Answer "Should email verification be its own        │
│   module?"                                            │
│                                       ⌘+Enter to send │
└──────────────────────────────────────────────────────┘
```

The chip is computed from the latest open question's `meta.module_row_key`. The orchestrator
treats answers as regen triggers: schedules a `regenerate_frs_module` Celery task for the
affected scope.

### 4.11 Animations & micro-interactions catalog

All animations respect `useReducedMotion()`. When reduced is true, all motion is replaced
with instant state changes.

| Where | Motion | Duration / curve |
|-------|--------|------------------|
| Source card fade-up on empty state | translate-y + opacity | 220ms ease-out, 50ms stagger |
| ✦ icon breathing pulse (empty state) | scale 1 → 1.04 → 1 | 2000ms ease-in-out infinite |
| Discover category segments fill | width 0 → N% | 600ms ease-out per fill |
| Theater step ○ → ◐ → ✓ transitions | colour + 1.08 scale pulse | 300ms ease-out |
| Theater step appearance | opacity + translate-y | 280ms ease-out |
| Module rail row hover lift | opacity 0 → 100 action bar | 150ms ease-out |
| Module rail glance card slide-out | translate-x + opacity | 250ms ease-out |
| Module identity card stat-flip on count change | scale 1 → 1.15 → 1 | 240ms ease-out |
| Section expand/collapse (Radix Accordion) | height auto | 220ms accordion-down keyframe |
| Module decision popover | scale 0.96 → 1, opacity 0 → 1 | 180ms ease-out (Radix default) |
| FRS trace chip hover popover | scale 0.96 → 1, opacity 0 → 1 | 180ms ease-out |
| Backlog stub appearance (new row) | scale 0.95 → 1, opacity 0 → 1 | 220ms ease-out |
| "Saved ✓" toast (after edit) | sonner default fade-slide | 100ms in, 200ms out |
| Findings drawer slide-in from right | translate-x-full → 0 | 280ms ease-out |
| Continue to Stage 2 banner slide-up | translate-y-full → 0 | 280ms ease-out |
| Confetti burst (validate success) | 6 particles, gravity sim | 600ms total |
| Section title pulse on smooth-scroll | bg-amber-50 flash | 600ms ease-in-out, single |

### 4.12 Keyboard shortcuts

Discoverable via `?` key (opens a small Command palette with shortcut list):

| Key | Action | Context |
|-----|--------|---------|
| `g r` | Focus module rail | Anywhere in builder |
| `g s` | Focus active module's scope section | Module panel open |
| `g b` | Focus backlog table | Module panel open |
| `j` / `k` | Next / previous module in rail | Rail focused |
| `o` | Open active module's first stub | Module panel open |
| `l` | Lock active row | Row hovered |
| `e` | Edit active row | Row hovered |
| `Esc` | Close drawer / popover / cancel edit | Anywhere |
| `/` | Focus composer | Anywhere in builder |
| `⌘+Enter` | Submit composer answer | Composer focused |
| `⌘+K` | Open command palette | Anywhere |
| `?` | Show keyboard shortcut help | Anywhere |

### 4.13 Accessibility

- **All interactive chips/rows are real `<button>`s** with `aria-label` describing the action.
- **Module rail** uses `aria-current="location"` on the active row.
- **Backlog stub cards** use `aria-expanded` on the toggle; `role="region"` on the body.
- **Layer icons** are decorative (`aria-hidden="true"`); the layer text is the accessible name.
- **Trace chips** read out as "Trace to BR-001, click to view source".
- **VoiceOver test pass**: every screen reads as a coherent narrative.
- **Focus rings** use `--accent-ring` (`rgba(47,107,76,0.30)`) — already in tokens.
- **Reduced motion**: all 16 animations have a static fallback (per §4.11).

### 4.14 Responsive breakpoints

- **≥ lg (1024px+)**: 2-column layout per §4.7
- **md (768–1023px)**: module rail collapses to a fly-out hamburger; rail opens as overlay on toggle
- **< md (mobile)**: tab switcher at top — `Modules · Active · Thread`. Active module renders full-screen; navigation via tabs.

---

## 5. File-by-file inventory

### 5.1 Backend files

| Path | Status | Purpose |
|------|--------|---------|
| `backend/app/models/frs.py` | new | All 14 FRS models (Stage A uses 7) |
| `backend/app/models/__init__.py` | extend | Export FRS models |
| `backend/app/alembic/versions/0019_frs_artifact.py` | new | Migration: 14 tables + 8 enums |
| `backend/app/services/context/brd_layer.py` | new | `build_brd_layer()` |
| `backend/app/services/context/project_context.py` | extend | Add `BrdLayer`, update `gather_project_context`, `_compute_readiness` |
| `backend/app/services/context/projection.py` | extend | Add `project_for_unit` FRS routing |
| `backend/app/services/artifacts/discover_catalog.py` | extend | `FRS_DISCOVER_QUESTIONS`, `FRS_UNIT_DISCOVER_MAP`, `get_catalog_for_artifact` |
| `backend/app/services/artifacts/manifest/frs.py` | new | `FrsUnitSpec`, `FRS_MANIFEST`, `FRS_TABLE_MAP`, `FRS_TYPED_COLS` |
| `backend/app/services/skills/dspy_frs.py` | new | `FrsModularizeSignature` + Module + runner |
| `backend/app/services/llm/fixtures/frs_modularize.json` | new | Mock fixture (claims chatbot example) |
| `backend/app/services/artifacts/frs_orchestrator.py` | new | `generate_frs_modularize`, `upsert_frs_rows`, `_persist_modularize_result`, helpers |
| `backend/app/services/artifacts/validators/frs.py` | new | `_validate_stage_a`, cycle detector |
| `backend/app/api/frs.py` | new | Stage-A endpoints (per PRD §6.6) |
| `backend/app/main.py` | extend | Mount FRS router |
| `backend/workers/tasks.py` | extend | `generate_frs` Celery task |
| `backend/workers/dispatch.py` | extend | Register `generate_frs` |
| `backend/tests/test_frs_modularize.py` | new | Smoke, idempotency, lock tests |
| `backend/tests/test_frs_validator_stage_a.py` | new | Validation rule tests |

### 5.2 Frontend files

| Path | Status | Purpose |
|------|--------|---------|
| `frontend/lib/types.ts` | extend | FRS row types (modules, sub-rows, stubs, decisions, readiness) |
| `frontend/lib/frs-manifest.ts` | new | Mirrors backend manifest; categories, colour maps |
| `frontend/lib/api.ts` | extend | `api.frs.*` namespace (Stage-A subset) |
| `frontend/lib/hooks/useFrsReadiness.ts` | new | SWR polling hook |
| `frontend/app/globals.css` | extend | FRS layer accent tokens, priority colours, trace chip palette |
| `frontend/app/projects/[id]/page.tsx` | extend | FRS chip wired to `brdValidated` gate |
| `frontend/app/projects/[id]/artifacts/frs/page.tsx` | new | Thin route → `<FrsBuilderView/>` |
| `frontend/app/components/brd/SourceStrip.tsx` | extend | Optional 4th BRD row |
| `frontend/app/components/frs/FrsBuilderView.tsx` | new | Root state machine |
| `frontend/app/components/frs/FrsBuilderHeader.tsx` | new | Sticky header (Sources / Coverage / Check & Validate / Export) |
| `frontend/app/components/frs/FrsEmptyState.tsx` | new | S1 |
| `frontend/app/components/frs/FrsDiscoverPhase.tsx` | new | S2 (wraps existing `DiscoverPhase`) |
| `frontend/app/components/frs/FrsConstructionTheater.tsx` | new | S3 — 5-step construction site |
| `frontend/app/components/frs/FrsBuilderBody.tsx` | new | S4 — rail + active surface |
| `frontend/app/components/frs/FrsBrdEchoStrip.tsx` | new | BRD essence summary |
| `frontend/app/components/frs/FrsModuleRail.tsx` | new | Left rail w/ groups, filter, glance |
| `frontend/app/components/frs/FrsModulePanel.tsx` | new | Active module body (7 sections + identity card) |
| `frontend/app/components/frs/FrsModuleIdentityCard.tsx` | new | Top card w/ capability icon + Layer ribbon + stats |
| `frontend/app/components/frs/FrsContractGraph.tsx` | new | Mini-SVG of inbound/outbound contracts |
| `frontend/app/components/frs/FrsBacklogTable.tsx` | new | Stub list inside module panel |
| `frontend/app/components/frs/FrsBacklogStubCard.tsx` | new | Individual stub card |
| `frontend/app/components/frs/FrsModuleDecisionPrompt.tsx` | new | Module-scoped [SPEC-DECISION] MCQ |
| `frontend/app/components/frs/FrsModularizeFindings.tsx` | new | Stage-A findings drawer |
| `frontend/app/components/frs/FrsContinueStageBBanner.tsx` | new | Bottom banner when Stage A is clean |
| `frontend/app/components/frs/FrsRefineComposer.tsx` | new | Bottom composer w/ affected-scope chip |
| `frontend/app/components/frs/FrsTraceChip.tsx` | new | Trace chip w/ new colour palette |
| `frontend/app/components/frs/FrsCoverageModal.tsx` | new | BR-coverage map (simple Stage-A version) |
| `frontend/app/components/frs/icons.ts` | new | Capability icon picker |

---

## 6. Implementation phases (with critical path)

### Phase F-A1 — Backend foundations (parallel-safe, ~3 days)
1. Models + Alembic migration → tested with `make migrate`
2. `BrdLayer` + context bundle update → tested manually
3. Discover catalog additions

### Phase F-A2 — Backend orchestration (depends on F-A1, ~4 days)
4. Manifest + DSPy Signature + mock fixture
5. Orchestrator (`generate_frs_modularize`, `upsert_frs_rows`, helpers)
6. Validator (Stage A rules + cycle detector)
7. API router (Stage-A endpoints)
8. Celery task + dispatch

### Phase F-B1 — Frontend foundations (parallel with F-A1, ~2 days)
9. Types + manifest mirror + API client + readiness hook
10. Workspace chip update
11. Empty state + readiness panel polish

### Phase F-B2 — Frontend atomic components (depends on F-B1, ~4 days)
12. Trace chips + popover
13. Source strip extension (4th BRD row)
14. BRD echo strip
15. Module rail (with layer grouping + filter + glance)
16. Module identity card
17. Backlog stub card + table
18. Contract graph SVG

### Phase F-B3 — Frontend hero surfaces (depends on F-B2, ~3 days)
19. Construction theater (5-step orchestration)
20. Module panel (7 sections + decision banner)
21. Decision prompt (MCQ Radix popover)
22. Continue-to-Stage-2 banner
23. Refine composer

### Phase F-B4 — Frontend integration (depends on F-A2 + F-B3, ~2 days)
24. `FrsBuilderView` state machine + route mount
25. Findings drawer (Stage-A subset)
26. Header actions (Check & Validate, Coverage, Export TBD)

### Phase F-V — Verification & polish (depends on everything, ~3 days)
27. Mock E2E walkthrough (§7.1)
28. Real-mode sanity (§7.2)
29. Automated tests
30. Visual regression via dev-browser
31. Reduced-motion + a11y + responsive QA

**Total**: ~17 days of focused work; BE + FE in parallel ≈ 11 calendar days.

---

## 7. Verification

### 7.1 Mock-mode E2E (step-by-step)

Prerequisites: `make migrate` applied; `LLM_PROVIDER=mock`; `claims chatbot` project with
validated BRD (from BRD work).

**Step 1 — workspace chip**
1. Open `/projects/<id>`. Verify FRS chip status: sublabel = "Functional Specifications",
   `locked=false` (because BRD is validated), no badge.
2. Click FRS chip → `view='frs'` → builder mounts.

**Step 2 — readiness gate**
3. If somehow BRD is reverted to `in_interview`: chip shows `locked=true` with sublabel
   "Unlocks after BRD". Click is a no-op.

**Step 3 — empty state**
4. Builder mounts in `S1 — Empty`. Verify:
   - 4 source cards (App Brain, Documents, Concept Brief, BRD) all show `✓ ready`
   - `✦` icon at top has 2s breathing pulse
   - Brief textarea has placeholder
   - "NFR/Architecture" hint card shows "0 files matching"
   - CTA `Discover & Continue →` is enabled

**Step 4 — AI Enhance**
5. Type a brief: "MVP for claims chatbot focusing on intake + triage"
6. Click `✦ AI Enhance` → toast "Enhancing…" → textarea content morphs to a polished version
   (mock returns a hand-crafted fixture)

**Step 5 — discover**
7. Click `Discover & Continue →` → `S2 — Discover` mounts
8. 7 questions appear across categories: 🎯 Scope (2), 👥 Personas (1), 🔄 Integrations (2),
   📊 Data (1), 🚀 Delivery (1)
9. Verify per-category progress segments at top fill independently as questions are answered
10. Answer at least 4 questions; verify "Why this matters" tooltip works
11. Click `Discover & Modularize →`

**Step 6 — generation theater**
12. `S3 — Construction Theater` mounts
13. Verify:
    - Header shows "Modularizing… (Stage 1 of 2)" badge
    - "Resume from here" button visible immediately
    - 5 steps render: ○ → ◐ → ✓ in sequence
    - Mock LLM returns in ~1s; remaining steps cascade to ✓ in 600ms
14. After ~2s, transition to `S4 — Builder`

**Step 7 — builder**
15. Module rail shows 5 modules grouped: 1 Foundation (MOD-000), 4 Vertical (MOD-001…004)
16. First module (MOD-001 by default) is active
17. Module Identity Card renders with:
    - 👤 capability icon
    - "Customer Intake" name
    - Layer 1 · Vertical Feature ribbon
    - 4-stat grid (3 backlog · 4 actors · 3 interfaces · 1 entity)
    - "Covers BRs" chips (5 BRs as pink trace chips)
18. Decision banner at top shows "⚠ 1 [SPEC-DECISION] pending"
19. Sections render correctly; Scope and Backlog expanded by default; others collapsed
20. Backlog shows 3 stubs (M001-FRS001, M001-FRS002, M001-FRS003) with priorities + BR chips

**Step 8 — interactions**
21. Hover a module in rail → glance card slides out with summary + actions
22. Click ⚠ decision banner → MCQ popover opens; pick "Accept AI recommendation"
23. Inline edit a responsibility: double-click → textarea → save → "Saved ✓" toast; row version v2
24. Lock the first stub → 🔒 chip appears; amber ring visible
25. Click "Re-modularize all" → theater opens, fixture rerun, locked stub preserved (verify by hash)

**Step 9 — findings**
26. Click "Check & Validate" → findings drawer slides in from right
27. Verify 5-group hierarchy: Critical (0), Major (0), Minor (0), Coverage (0), Warnings (1
    — open decision still showing as warning)
28. Resolve the decision; refresh findings → 0 warnings
29. The "Continue to Stage 2" banner appears at the bottom of the builder
30. Click → confetti burst + (Stage B mocked endpoint) state transition

**Step 10 — visual regression**
31. Open `dev-browser` skill against `/projects/<id>`
32. Verify pixel-perfect rendering of the 7 surfaces
33. Toggle "Reduce motion" in macOS → re-run; verify no animations except instant state changes

### 7.2 Real-mode sanity (Vertex)
- Run with `LLM_PROVIDER=vertex`. Modularize should complete in 30–60s.
- Verify the AI:
  - Produces 4–7 modules (not 1, not 20)
  - Uses BR row_keys verbatim in `br_refs` (no fabrications)
  - Hoists a Cross-cutting Standards module (MOD-000) when applicable
  - Module names are capability-language (no "API", "Service", "Lambda" tokens)
  - Cross-module contracts are symmetric (every outbound has a matching inbound)

### 7.3 Automated tests

**`backend/tests/test_frs_modularize.py`**:
```python
async def test_modularize_creates_5_modules_from_fixture():
    """Smoke: generate_frs_modularize against mock fixture produces expected counts."""

async def test_modularize_is_idempotent():
    """2nd call with same input produces 0 new versions."""

async def test_modularize_preserves_locked_modules():
    """Lock MOD-001, re-run; MOD-001 unchanged verbatim."""

async def test_modularize_soft_deletes_removed_modules():
    """Module not in 2nd output gets status='removed', not deleted."""

async def test_brd_layer_requires_validated_status():
    """If BRD is in_interview, FRS readiness returns can_generate=False."""

async def test_concurrent_modularize_calls_are_atomic():
    """Two concurrent generate_frs_modularize calls — no row corruption."""
```

**`backend/tests/test_frs_validator_stage_a.py`**:
```python
def test_zero_modules_is_critical():
def test_module_with_zero_backlog_is_critical():
def test_capability_language_rejects_api_suffix():
def test_cross_module_cycle_detected():
def test_must_priority_br_uncovered_is_finding():
def test_under_decomposed_module_is_warning():
def test_open_decision_is_warning():
```

**Frontend (Playwright via dev-browser)**:
- E2E flow: chip click → empty state → discover → theater → builder → findings → continue
- Visual regression snapshots of each surface
- Reduced-motion comparison snapshots

### 7.4 Performance budgets

- **Empty state TTI**: ≤ 1.2s
- **Builder TTI** (6 modules × 3 stubs): ≤ 1.5s
- **Module rail filter input → re-render**: ≤ 16ms / frame
- **Module identity card stat-flip**: ≤ 240ms (single transition)
- **Construction theater step transition**: ≤ 300ms
- **`gather_project_context` with BrdLayer** (validated BRD with 14 BRs): ≤ 800ms

### 7.5 Accessibility

- Tab through builder → every interactive element reachable in logical order
- VoiceOver test: builder reads as "FRS Builder, Customer Intake module, Layer 1 Vertical Feature, 3 backlog stubs, …"
- Reduced motion: all 16 animations have static fallback (per §4.11)
- Colour contrast: every text/bg pair passes WCAG AA (verified via `eslint-plugin-jsx-a11y` + manual)
- Keyboard shortcuts discoverable via `?` palette

### 7.6 Security

- All FRS endpoints require `Depends(get_current_user)` + `get_project_or_404`
- Edit endpoint accepts `expected_version` for optimistic concurrency (409 on conflict)
- No PII handling (per project-wide rule); FRS rows contain capability descriptions only
- Mock fixtures committed; `video-key.json` and `.env` excluded as always

---

## 8. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM produces tech-named modules ("Auth API") despite instruction | medium | medium | Validator catches with `module_tech_name` finding; UI surfaces clearly; one-click "Rename" action |
| Module count >12 (overwhelming rail) | low | low | Filter bar + layer grouping; auto-collapse all but active |
| Concurrent edit conflict in module panel | low | medium | Optimistic concurrency with `expected_version`; UI shows "Refresh — another tab edited" toast on 409 |
| Cycle in cross-module contracts (LLM mistake) | medium | medium | Validator's cycle detector; finding includes the exact cycle path; UI highlights in contract graph |
| Theater feels slow when Vertex is fast (sub-30s) | low | low | When LLM returns early, remaining steps cascade to ✓ in 600ms — feels rewarding not laggy |
| Theater feels frozen when Vertex is slow (>60s) | medium | medium | Last step pulses indefinitely; "Resume from here" button always visible; 90s timeout aborts cleanly |
| `BrdLayer` query is slow on large BRDs | low | medium | Tested with claims chatbot (14 BRs). For >100 BRs, add prefetch + caching layer |
| Mock fixture drifts from real DSPy output schema | medium | high | Pydantic validation on fixture load in tests; schema-pinned via DSPy Signature |
| Stage-A approval flag conflicts with future Stage B work | low | high | Use `unit_status._stage_a_approved` JSONB flag; Stage B reads it; no schema change needed |

---

## 9. Out of scope (deferred to Stage B / v2)

Covered in `E4c-frs-functional-design.md`:
- Full FRS spec authoring (UI / Backend / Data / Cross-Cutting / Scenarios / FRs)
- Figma link prompts and the [FIGMA-LINK-REQUIRED] gate
- Per-spec sub-row tables (screens, components, endpoints, entities, business rules,
  scenarios, functional requirements, traceability rows)
- Spec-scoped [SPEC-DECISION] MCQs
- Full validation drawer
- Coverage galaxy (BR ↔ FRS bezier visualisation)
- Export bundle (markdown files for modules + specs + traceability)

Permanently deferred (v2+):
- Figma API / MCP fetch (link only)
- Formal NFR Builder artifact
- Formal Architecture Builder artifact
- Cross-FRS auto-refactor
- Inline AI single-sentence rewrite
- Multi-user real-time editing
- Module merge / split as a first-class operation (manual edit only in v1)

---

## 10. Appendix · Quick reference component map

```
FrsBuilderView (state machine)
├── readiness blocked → FrsBlockedState
├── doc === null     → FrsEmptyState                              (S1)
│                          ├── 4-source grounding cards
│                          ├── AI Enhance brief textarea
│                          └── NFR/Architecture upload hint
├── discover phase   → FrsDiscoverPhase (wraps DiscoverPhase)     (S2)
├── generating       → FrsConstructionTheater                      (S3)
│                          ├── 5-step orchestration timeline
│                          ├── "Right now" subtitle card
│                          └── "Resume from here" recovery button
└── in_interview     → FrsBuilderBody                              (S4)
                          ├── FrsBuilderHeader
                          │     ├── Back · Status badge
                          │     ├── Sources / Coverage / Check & Validate / Export
                          ├── FrsModuleRail (sticky left)
                          │     ├── Layer-grouped module list
                          │     ├── Filter + search (when >8 modules)
                          │     ├── Hover glance card
                          │     └── + Add Module
                          ├── SourceStrip (extended: 4 layers)
                          ├── FrsBrdEchoStrip
                          ├── FrsModulePanel
                          │     ├── FrsModuleIdentityCard
                          │     ├── Decision banner (if open)
                          │     ├── Scope · Actors · Responsibilities
                          │     ├── Interfaces (with FrsContractGraph mini-SVG)
                          │     ├── Owned Data
                          │     ├── FrsBacklogTable
                          │     │     └── FrsBacklogStubCard[]
                          │     └── Inline EditableRows on every section
                          ├── FrsRefineComposer (bottom)
                          └── FrsContinueStageBBanner (when Stage A clean)
                                  └── BrdConfettiBurst on click
                                            (S6 = S4 + locked rows + Stage B trigger)

Overlays / modals:
  - FrsModularizeFindings (right-slide drawer)                    (S5)
  - FrsModuleDecisionPrompt (Radix Popover)
  - FrsCoverageModal (centered)
  - FrsTraceChip popovers (Radix Popover)
```
