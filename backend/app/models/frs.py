"""FRS typed tables — 14 typed tables + traceability (Stage A + Stage B).

Stage A (modularize) writes to: frs_modules, frs_module_actors,
frs_module_responsibilities, frs_module_interfaces, frs_module_data_entities,
frs_specs (stubs), frs_spec_decisions (module-scoped).

Stage B (design_module) writes to: frs_specs (fills out), frs_screens,
frs_ui_components, frs_endpoints, frs_data_entities, frs_business_rules,
frs_acceptance_scenarios, frs_functional_requirements, frs_spec_decisions
(spec-scoped), frs_traceability.

All versioned tables share the row mixin pattern (document_id FK, row_key,
version, is_current, is_locked, status, source, created_by, created_at)
established by the Concept Brief + BRD tables.

frs_traceability is NOT versioned (replace-all semantics on regen).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer,
    Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.artifact import ArtifactRowSource, ArtifactRowStatus
from app.models.base import uuid_pk

# FRS-specific enum types (created in migration 0019)
FrsModuleLayer = Enum(
    "foundation", "vertical", "cross_cutting",
    name="frs_module_layer", create_type=False,
)
FrsActorRelationship = Enum(
    "primary_user", "dependency", "external_system", "downstream_consumer",
    name="frs_actor_relationship", create_type=False,
)
FrsInterfaceKind = Enum(
    "ui_surface", "api", "event",
    name="frs_interface_kind", create_type=False,
)
FrsInterfaceDirection = Enum(
    "inbound", "outbound",
    name="frs_interface_direction", create_type=False,
)
FrsPriority = Enum(
    "P0", "P1", "P2", "P3",
    name="frs_priority", create_type=False,
)
FrsDecisionStatus = Enum(
    "open", "accepted_ai", "overridden", "dismissed",
    name="frs_decision_status", create_type=False,
)
FrsHttpMethod = Enum(
    "GET", "POST", "PUT", "PATCH", "DELETE",
    name="frs_http_method", create_type=False,
)
FrsTraceKind = Enum(
    "brd_business_requirement", "brd_objective", "brd_kpi", "brd_risk",
    "brd_text_block", "nfr_driver", "app_fact", "doc_section",
    "discover_qa", "within_frs",
    name="frs_trace_kind", create_type=False,
)


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE A — Module-level tables (5) + spec stub + module decisions
# ═══════════════════════════════════════════════════════════════════════════════


# ── 1. frs_modules ─────────────────────────────────────────────────────────────

class FrsModule(Base):
    """A business-capability module: scope, layer, actors, responsibilities, interfaces."""
    __tablename__ = "frs_modules"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_modules_doc_key_ver"),
        Index("idx_frs_modules_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_frs_modules_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)  # MOD-000 / MOD-001 / …
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str] = mapped_column(FrsModuleLayer, nullable=False, server_default="vertical")
    scope_in: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    scope_out: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    figma_root_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="low")


# ── 2. frs_module_actors ───────────────────────────────────────────────────────

class FrsModuleActor(Base):
    """Capability/role actors + external systems a module interacts with."""
    __tablename__ = "frs_module_actors"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_actors_doc_key_ver"),
        Index("idx_frs_mod_actors_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_mod_actors_module", "document_id", "module_row_key"),
        CheckConstraint("version > 0", name="ck_frs_mod_actors_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    actor_name: Mapped[str] = mapped_column(Text, nullable=False)
    relationship: Mapped[str] = mapped_column(FrsActorRelationship, nullable=False, server_default="primary_user")
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── 3. frs_module_responsibilities ─────────────────────────────────────────────

class FrsModuleResponsibility(Base):
    """A module's responsibilities; each maps to ≥1 FRS backlog stub."""
    __tablename__ = "frs_module_responsibilities"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_resp_doc_key_ver"),
        Index("idx_frs_mod_resp_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_mod_resp_module", "document_id", "module_row_key"),
        CheckConstraint("version > 0", name="ck_frs_mod_resp_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    responsibility: Mapped[str] = mapped_column(Text, nullable=False)
    frs_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


# ── 4. frs_module_interfaces ───────────────────────────────────────────────────

class FrsModuleInterface(Base):
    """Black-box interface inventory: UI surfaces, APIs (in/out), events."""
    __tablename__ = "frs_module_interfaces"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_if_doc_key_ver"),
        Index("idx_frs_mod_if_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_mod_if_module", "document_id", "module_row_key"),
        CheckConstraint("version > 0", name="ck_frs_mod_if_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    interface_kind: Mapped[str] = mapped_column(FrsInterfaceKind, nullable=False)
    direction: Mapped[str | None] = mapped_column(FrsInterfaceDirection, nullable=True)  # NULL for ui_surface
    transport: Mapped[str | None] = mapped_column(Text, nullable=True)  # rest|grpc|mq|webhook|event_bus
    name: Mapped[str] = mapped_column(Text, nullable=False)
    counterpart: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_role: Mapped[str | None] = mapped_column(Text, nullable=True)  # ui_surface only
    purpose: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    frs_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── 5. frs_module_data_entities ────────────────────────────────────────────────

class FrsModuleDataEntity(Base):
    """Conceptual data ownership at the module level (NO schema; that's in Stage B)."""
    __tablename__ = "frs_module_data_entities"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_mod_de_doc_key_ver"),
        Index("idx_frs_mod_de_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_mod_de_module", "document_id", "module_row_key"),
        CheckConstraint("version > 0", name="ck_frs_mod_de_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    business_purpose: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    source_of_truth: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── 6. frs_specs (stub form in Stage A; full form in Stage B) ──────────────────

class FrsSpec(Base):
    """An FRS slice. Stage A creates stubs (completeness=0); Stage B fills out."""
    __tablename__ = "frs_specs"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_specs_doc_key_ver"),
        Index("idx_frs_specs_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_specs_module", "document_id", "module_row_key"),
        CheckConstraint("version > 0", name="ck_frs_specs_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)  # M001-FRS001 / M002-FRS003 / …
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(FrsPriority, nullable=False, server_default="P1")
    layer: Mapped[str] = mapped_column(FrsModuleLayer, nullable=False, server_default="vertical")
    br_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    nfr_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    depends_on: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    narrative: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    independent_test: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    data_and_validation: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    errors_and_edge_cases: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    observability: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    implementation_tasks: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="low")


# ── 7. frs_spec_decisions ──────────────────────────────────────────────────────

class FrsSpecDecision(Base):
    """[SPEC-DECISION] MCQ-style ambiguity. Module-scoped (Stage A) or spec-scoped (Stage B)."""
    __tablename__ = "frs_spec_decisions"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_dec_doc_key_ver"),
        Index("idx_frs_dec_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_dec_status", "document_id", "resolution_status"),
        CheckConstraint("version > 0", name="ck_frs_dec_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str | None] = mapped_column(Text, nullable=True)   # spec-scoped (Stage B)
    module_row_key: Mapped[str | None] = mapped_column(Text, nullable=True) # module-scoped (Stage A)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    recommended_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recommended_rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    user_chosen_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_status: Mapped[str] = mapped_column(FrsDecisionStatus, nullable=False, server_default="open")


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE B — Spec sub-row tables (7) + traceability
# ═══════════════════════════════════════════════════════════════════════════════


# ── 8. frs_screens ─────────────────────────────────────────────────────────────

class FrsScreen(Base):
    """UI Spec §1.1 — one row per screen on a spec. Figma link is the blocking gate."""
    __tablename__ = "frs_screens"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_screens_doc_key_ver"),
        Index("idx_frs_screens_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_screens_spec", "document_id", "spec_row_key"),
        CheckConstraint("version > 0", name="ck_frs_screens_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    screen_name: Mapped[str] = mapped_column(Text, nullable=False)
    figma_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    user_roles: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    layout: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    navigation: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    interactive_behavior: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── 9. frs_ui_components ───────────────────────────────────────────────────────

class FrsUiComponent(Base):
    """UI Spec §1.2 — one row per field/button/control on a screen."""
    __tablename__ = "frs_ui_components"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_ui_comp_doc_key_ver"),
        Index("idx_frs_ui_comp_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_ui_comp_spec", "document_id", "spec_row_key"),
        Index("idx_frs_ui_comp_screen", "document_id", "screen_row_key"),
        CheckConstraint("version > 0", name="ck_frs_ui_comp_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    screen_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    component_name: Mapped[str] = mapped_column(Text, nullable=False)
    component_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="input")
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    behavior: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    data_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")


# ── 10. frs_endpoints ──────────────────────────────────────────────────────────

class FrsEndpoint(Base):
    """Backend Spec §2.2 — one row per service endpoint."""
    __tablename__ = "frs_endpoints"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_endpoints_doc_key_ver"),
        Index("idx_frs_endpoints_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_endpoints_spec", "document_id", "spec_row_key"),
        CheckConstraint("version > 0", name="ck_frs_endpoints_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    service_name: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    endpoint_name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    protocol: Mapped[str] = mapped_column(Text, nullable=False, server_default="HTTPS")
    method: Mapped[str] = mapped_column(FrsHttpMethod, nullable=False, server_default="POST")
    sync_async: Mapped[str] = mapped_column(Text, nullable=False, server_default="sync")
    idempotent: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    request_spec: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    response_spec: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    error_handling: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    security: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    operational: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    integration_target: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── 11. frs_data_entities ──────────────────────────────────────────────────────

class FrsDataEntity(Base):
    """Data Spec §3.2 — full schema detail per entity (FRS-level)."""
    __tablename__ = "frs_data_entities"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_data_ent_doc_key_ver"),
        Index("idx_frs_data_ent_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_data_ent_spec", "document_id", "spec_row_key"),
        CheckConstraint("version > 0", name="ck_frs_data_ent_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    data_store_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="RDBMS")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    expected_volume: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    columns: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    keys_constraints: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    indexes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    relationships: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    access_logic: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cache_spec: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retention_policy: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── 12. frs_business_rules ─────────────────────────────────────────────────────

class FrsBusinessRule(Base):
    """Cross-Cutting §4.1 — one row per business rule (table form)."""
    __tablename__ = "frs_business_rules"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_br_doc_key_ver"),
        Index("idx_frs_br_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_br_spec", "document_id", "spec_row_key"),
        CheckConstraint("version > 0", name="ck_frs_br_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False)  # local within FRS, e.g. "BR-1"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    logic_decision: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── 13. frs_acceptance_scenarios ───────────────────────────────────────────────

class FrsAcceptanceScenario(Base):
    """Gherkin scenarios. ≥6 per spec, ≥2 negative (enforced by validator)."""
    __tablename__ = "frs_acceptance_scenarios"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_as_doc_key_ver"),
        Index("idx_frs_as_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_as_spec", "document_id", "spec_row_key"),
        CheckConstraint("version > 0", name="ck_frs_as_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    given: Mapped[str] = mapped_column(Text, nullable=False)
    when: Mapped[str] = mapped_column(Text, nullable=False)
    then: Mapped[str] = mapped_column(Text, nullable=False)
    is_negative: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    fr_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


# ── 14. frs_functional_requirements ────────────────────────────────────────────

class FrsFunctionalRequirement(Base):
    """FR-N rows. Each must reference ≥1 acceptance scenario."""
    __tablename__ = "frs_functional_requirements"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_frs_fr_doc_key_ver"),
        Index("idx_frs_fr_current", "document_id", postgresql_where="is_current"),
        Index("idx_frs_fr_spec", "document_id", "spec_row_key"),
        CheckConstraint("version > 0", name="ck_frs_fr_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    fr_id: Mapped[str] = mapped_column(Text, nullable=False)  # local within FRS, e.g. "FR-1"
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    scenario_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


# ── 15. frs_traceability (NOT versioned — replace-all per regen) ───────────────

class FrsTraceability(Base):
    """Outward traceability: FRS rows → BRD/NFR/Apps/Docs/Discover sources.

    Every FRS spec must have ≥1 traceability entry to a BR. Each FR/scenario can emit
    additional traces. Replace-all semantics: re-running design_module replaces all
    rows for the affected spec.
    """
    __tablename__ = "frs_traceability"
    __table_args__ = (
        Index("idx_frs_traceability_doc", "document_id"),
        Index("idx_frs_traceability_source", "document_id", "source_table", "source_row_key"),
        Index("idx_frs_traceability_target", "document_id", "target_kind", "target_ref"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    source_table: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(FrsTraceKind, nullable=False)
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)
    # target_ref format per kind:
    #   brd_business_requirement → row_key (e.g. "BR-001")
    #   brd_objective            → row_key (e.g. "OBJ-001")
    #   brd_kpi/risk/text_block  → row_key
    #   nfr_driver               → identifier in NFR doc (e.g. "N-005")
    #   app_fact                 → "{app_name}:{kind}:{text_hash}"
    #   doc_section              → "{filename}:{section_title}"
    #   discover_qa              → question_key (e.g. "frs_2a")
    #   within_frs               → "{table}:{row_key}" (e.g. "frs_specs:M001-FRS001")
    target_label: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="high")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
