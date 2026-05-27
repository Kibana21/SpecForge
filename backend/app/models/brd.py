"""BRD typed tables — 21 typed tables + traceability.

All tables share the VersionedRow mixin pattern (document_id FK, row_key, version,
is_current, is_locked, status, source, created_by, created_at) established by the
Concept Brief tables, extended with BRD-specific typed columns.
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

# BRD-specific enum types (created in migration 0018)
BrdPriority = Enum("must", "should", "could", "wont", name="brd_priority", create_type=False)
BrdCategory = Enum(
    "functional", "non_functional", "data", "integration", "reporting", "compliance", "operational",
    name="brd_category", create_type=False,
)
BrdTraceKind = Enum(
    "cb_text_block", "cb_outcome", "cb_metric", "cb_capability", "cb_scope_item",
    "cb_milestone", "app_fact", "doc_section", "discover_qa", "within_brd",
    name="brd_trace_kind", create_type=False,
)
BrdRiskSeverity = Enum("critical", "high", "medium", "low", name="brd_risk_severity", create_type=False)
BrdRiskLikelihood = Enum("high", "medium", "low", name="brd_risk_likelihood", create_type=False)
BrdStakeholderType = Enum(
    "sponsor", "owner", "user", "operations", "compliance", "technical", "external",
    name="brd_stakeholder_type", create_type=False,
)
BrdProcessStepType = Enum("asis", "tobe", name="brd_process_step_type", create_type=False)


# ── Shared row mixin columns ───────────────────────────────────────────────────

def _versioned_row_cols():
    """SQLAlchemy column definitions shared by all BRD row tables."""
    return {
        "id": uuid_pk,
        "version": lambda: mapped_column(Integer, nullable=False),
        "is_current": lambda: mapped_column(Boolean, nullable=False, server_default="true"),
        "is_locked": lambda: mapped_column(Boolean, nullable=False, server_default="false"),
        "status": lambda: mapped_column(ArtifactRowStatus, nullable=False, server_default="active"),
        "source": lambda: mapped_column(ArtifactRowSource, nullable=False),
        "created_at": lambda: mapped_column(DateTime(timezone=True), nullable=False, server_default="now()"),
    }


# ── §1–2: Prose text blocks ────────────────────────────────────────────────────

class BrdTextBlock(Base):
    """Prose sections: business_context, problem_statement, exec_summary, etc."""
    __tablename__ = "brd_text_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_text_blocks_doc_key_ver"),
        Index("idx_brd_text_blocks_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_text_blocks_version"),
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
    field_key: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── §3: Objectives ─────────────────────────────────────────────────────────────

class BrdObjective(Base):
    __tablename__ = "brd_objectives"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_objectives_doc_key_ver"),
        Index("idx_brd_objectives_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_objectives_version"),
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
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="strategic")
    priority: Mapped[str] = mapped_column(BrdPriority, nullable=False, server_default="must")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cb_outcome_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── §4: Stakeholders ───────────────────────────────────────────────────────────

class BrdStakeholder(Base):
    __tablename__ = "brd_stakeholders"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_stakeholders_doc_key_ver"),
        Index("idx_brd_stakeholders_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_stakeholders_version"),
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
    name: Mapped[str] = mapped_column(Text, nullable=False)
    stakeholder_type: Mapped[str] = mapped_column(BrdStakeholderType, nullable=False, server_default="user")
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    interest: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    influence: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class BrdActor(Base):
    """System actors (human or system) that interact with the solution."""
    __tablename__ = "brd_actors"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_actors_doc_key_ver"),
        Index("idx_brd_actors_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_actors_version"),
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
    name: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="human")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    interactions: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── §5: Scope ──────────────────────────────────────────────────────────────────

class BrdScopeItem(Base):
    __tablename__ = "brd_scope_items"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_scope_items_doc_key_ver"),
        Index("idx_brd_scope_items_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_scope_items_version"),
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
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # in_scope | out_of_scope | assumption
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cb_scope_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── §6: Process steps ─────────────────────────────────────────────────────────

class BrdProcessStep(Base):
    """As-is and to-be process steps."""
    __tablename__ = "brd_process_steps"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_process_steps_doc_key_ver"),
        Index("idx_brd_process_steps_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_process_steps_version"),
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
    step_type: Mapped[str] = mapped_column(BrdProcessStepType, nullable=False)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    actor: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    action: Mapped[str] = mapped_column(Text, nullable=False)
    pain_point: Mapped[str | None] = mapped_column(Text, nullable=True)   # asis only
    improvement: Mapped[str | None] = mapped_column(Text, nullable=True)  # tobe only


# ── §7: Business Requirements (keystone) ──────────────────────────────────────

class BrdBusinessRequirement(Base):
    __tablename__ = "brd_business_requirements"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_br_doc_key_ver"),
        Index("idx_brd_br_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_br_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)  # BR-001, BR-002, …
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    priority: Mapped[str] = mapped_column(BrdPriority, nullable=False, server_default="must")
    category: Mapped[str] = mapped_column(BrdCategory, nullable=False, server_default="functional")
    acceptance_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # acceptance_criteria: list of {given: str, when: str, then: str}
    objective_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # objective_refs: list of row_key strings pointing to brd_objectives
    stakeholder_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    # stakeholder_refs: list of row_key strings pointing to brd_stakeholders
    rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="low")


# ── §8: Data & Reporting ──────────────────────────────────────────────────────

class BrdDataEntity(Base):
    __tablename__ = "brd_data_entities"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_data_entities_doc_key_ver"),
        Index("idx_brd_data_entities_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_data_entities_version"),
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
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner_system: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    data_sensitivity: Mapped[str] = mapped_column(Text, nullable=False, server_default="standard")
    key_attributes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


class BrdReportRequirement(Base):
    __tablename__ = "brd_report_requirements"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_report_req_doc_key_ver"),
        Index("idx_brd_report_req_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_report_req_version"),
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
    report_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    audience: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    frequency: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    key_metrics: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


# ── §9: Assumptions, Constraints, Dependencies ────────────────────────────────

class BrdAssumption(Base):
    __tablename__ = "brd_assumptions"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_assumptions_doc_key_ver"),
        Index("idx_brd_assumptions_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_assumptions_version"),
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
    assumption: Mapped[str] = mapped_column(Text, nullable=False)
    impact_if_wrong: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    cb_scope_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


class BrdConstraint(Base):
    __tablename__ = "brd_constraints"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_constraints_doc_key_ver"),
        Index("idx_brd_constraints_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_constraints_version"),
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
    constraint_text: Mapped[str] = mapped_column(Text, nullable=False)
    constraint_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="business")
    source_ref: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class BrdDependency(Base):
    __tablename__ = "brd_dependencies"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_dependencies_doc_key_ver"),
        Index("idx_brd_dependencies_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_dependencies_version"),
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
    dependency: Mapped[str] = mapped_column(Text, nullable=False)
    dependency_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="external")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    due_date: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── §10: Risks & Issues ───────────────────────────────────────────────────────

class BrdRisk(Base):
    __tablename__ = "brd_risks"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_risks_doc_key_ver"),
        Index("idx_brd_risks_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_risks_version"),
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
    risk: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    severity: Mapped[str] = mapped_column(BrdRiskSeverity, nullable=False, server_default="medium")
    likelihood: Mapped[str] = mapped_column(BrdRiskLikelihood, nullable=False, server_default="medium")
    mitigation: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── §11: Implementation & Phasing ─────────────────────────────────────────────

class BrdPhase(Base):
    __tablename__ = "brd_phases"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_phases_doc_key_ver"),
        Index("idx_brd_phases_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_phases_version"),
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
    phase_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    target_date: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    included_br_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")


class BrdMilestone(Base):
    __tablename__ = "brd_milestones"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_milestones_doc_key_ver"),
        Index("idx_brd_milestones_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_milestones_version"),
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
    milestone: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    phase_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    cb_milestone_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── §12: KPIs ─────────────────────────────────────────────────────────────────

class BrdKpi(Base):
    __tablename__ = "brd_kpis"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_kpis_doc_key_ver"),
        Index("idx_brd_kpis_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_kpis_version"),
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
    kpi_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    baseline: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    target: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    timeframe: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    data_source: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    objective_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    cb_metric_ref: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── §13: Open Questions & Decisions ───────────────────────────────────────────

class BrdOpenQuestion(Base):
    __tablename__ = "brd_open_questions"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_open_q_doc_key_ver"),
        Index("idx_brd_open_q_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_open_q_version"),
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
    question: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    due_date: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class BrdDecision(Base):
    __tablename__ = "brd_decisions"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_decisions_doc_key_ver"),
        Index("idx_brd_decisions_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_decisions_version"),
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
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_date: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    alternatives_considered: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── §14: References & Glossary ────────────────────────────────────────────────

class BrdReference(Base):
    __tablename__ = "brd_references"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_references_doc_key_ver"),
        Index("idx_brd_references_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_references_version"),
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
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reference_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="document")
    location: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class BrdGlossaryEntry(Base):
    __tablename__ = "brd_glossary_entries"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_brd_glossary_doc_key_ver"),
        Index("idx_brd_glossary_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_brd_glossary_version"),
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
    term: Mapped[str] = mapped_column(Text, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── Traceability (cross-cutting) ───────────────────────────────────────────────

class BrdTraceability(Base):
    """Outward traceability: links from BRD rows to their source references.

    Every BR, KPI, objective, and risk row must have ≥1 traceability entry.
    target_kind distinguishes outward (CB/app/doc) from within-BRD links.
    """
    __tablename__ = "brd_traceability"
    __table_args__ = (
        Index("idx_brd_traceability_doc", "document_id"),
        Index("idx_brd_traceability_source_row", "document_id", "source_row_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    source_table: Mapped[str] = mapped_column(Text, nullable=False)
    source_row_key: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(BrdTraceKind, nullable=False)
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)
    # target_ref format per kind:
    #   cb_text_block     → row_key (e.g. "problem_statement")
    #   cb_outcome        → row_key (e.g. "OC-1")
    #   cb_capability     → row_key (e.g. "CAP-2")
    #   app_fact          → "{app_name}:{kind}:{text_hash}"
    #   doc_section       → "{filename}:{section_title}"
    #   discover_qa       → question_key (e.g. "1b")
    #   within_brd        → "{table}:{row_key}" (e.g. "brd_objectives:OBJ-1")
    target_label: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="high")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
