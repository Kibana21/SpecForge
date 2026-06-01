"""Test Cases typed tables — test_suites, test_plans, test_cases + traceability.

Stage A (plan_journeys) writes: test_suites (one per FRS module), test_plans
(one STUB per FRS spec).

Stage B (author_plan, one DSPy call per FRS spec) writes: test_plans (filled
out), test_cases, test_case_traceability.

All versioned tables share the row mixin pattern (document_id FK, row_key,
version, is_current, is_locked, status, source, created_by, created_at)
established by the Concept Brief + BRD + FRS tables.

test_case_traceability is NOT versioned (replace-all on regen), mirroring
FrsTraceability.
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
from app.models.base import uuid_pk

# Test-cases-specific enum types (created in migration 0024)
TcTestType = Enum(
    "functional", "integration", "e2e", "negative", "edge_case", "responsive",
    name="tc_test_type", create_type=False,
)
TcPriority = Enum(
    "P0", "P1", "P2", "P3",
    name="tc_priority", create_type=False,
)
TcSourceKind = Enum(
    "acceptance_scenario", "functional_requirement", "business_rule",
    "independent_test", "screen", "manual",
    name="tc_source_kind", create_type=False,
)
TcTraceKind = Enum(
    "frs_spec", "frs_acceptance_scenario", "frs_functional_requirement",
    "frs_business_rule", "frs_screen", "brd_business_requirement",
    "within_test_cases",
    name="tc_trace_kind", create_type=False,
)

# Shared enums reused from the artifact infrastructure (migration 0015)
from app.models.artifact import ArtifactRowSource, ArtifactRowStatus  # noqa: E402


# ── 1. test_suites (one per FRS module) ─────────────────────────────────────────

class TestSuite(Base):
    """A module-level test journey: framing narrative + strategy + outcomes."""
    __tablename__ = "test_suites"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_test_suites_doc_key_ver"),
        Index("idx_test_suites_current", "document_id", postgresql_where="is_current"),
        Index("idx_test_suites_module", "document_id", "module_row_key"),
        CheckConstraint("version > 0", name="ck_test_suites_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)  # TS-{module_row_key}
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    journey_overview: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    test_strategy: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    outcomes_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="low")


# ── 2. test_plans (one per FRS spec) ────────────────────────────────────────────

class TestPlan(Base):
    """A per-FRS-spec test plan. Stage A creates stubs; Stage B fills them out."""
    __tablename__ = "test_plans"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_test_plans_doc_key_ver"),
        Index("idx_test_plans_current", "document_id", postgresql_where="is_current"),
        Index("idx_test_plans_spec", "document_id", "spec_row_key"),
        Index("idx_test_plans_suite", "document_id", "suite_row_key"),
        CheckConstraint("version > 0", name="ck_test_plans_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)  # TP-{spec_row_key}
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    suite_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    preconditions: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    test_data_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    coverage_targets: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    outcomes_summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    priority: Mapped[str] = mapped_column(TcPriority, nullable=False, server_default="P1")
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="low")


# ── 3. test_cases ───────────────────────────────────────────────────────────────

class TestCase(Base):
    """A single test case. row_key is {plan_row_key}-TC-NNN (unique per plan)."""
    __tablename__ = "test_cases"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_test_cases_doc_key_ver"),
        Index("idx_test_cases_current", "document_id", postgresql_where="is_current"),
        Index("idx_test_cases_plan", "document_id", "plan_row_key"),
        Index("idx_test_cases_spec", "document_id", "spec_row_key"),
        Index("idx_test_cases_module", "document_id", "module_row_key"),
        Index("idx_test_cases_type", "document_id", "test_type"),
        CheckConstraint("version > 0", name="ck_test_cases_version"),
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
    plan_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    spec_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    module_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    test_type: Mapped[str] = mapped_column(TcTestType, nullable=False, server_default="functional")
    source_kind: Mapped[str] = mapped_column(TcSourceKind, nullable=False, server_default="acceptance_scenario")
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    given: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    when: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    then: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    preconditions: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    key_assertions: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    test_data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    expected_result: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    expected_observability: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    viewports: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    auth_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    auth_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(TcPriority, nullable=False, server_default="P1")
    fr_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    scenario_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    br_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


# ── 4. test_case_traceability (NOT versioned — replace-all per regen) ───────────

class TestCaseTraceability(Base):
    """Outward traceability: test rows → FRS elements + (transitive) BRD BRs.

    Every test case must have ≥1 traceability entry to an FRS element. Plans add
    a frs_spec trace + transitive brd_business_requirement traces. Replace-all
    semantics: re-running author_plan replaces all rows for the affected source.
    """
    __tablename__ = "test_case_traceability"
    __table_args__ = (
        Index("idx_tc_traceability_doc", "document_id"),
        Index("idx_tc_traceability_source", "document_id", "source_table", "source_row_key"),
        Index("idx_tc_traceability_target", "document_id", "target_kind", "target_ref"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    source_table: Mapped[str] = mapped_column(Text, nullable=False)  # test_cases | test_plans | test_suites
    source_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(TcTraceKind, nullable=False)
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)
    target_label: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="high")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
