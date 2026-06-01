"""NFR (Non-Functional Requirements) typed tables — 8 versioned tables + traceability.

The NFR artifact captures quality requirements across seven categories
(performance, security, availability, usability, scalability, maintainability,
portability) as testable, solution-agnostic `NFR-nnn` rows with a MoSCoW
priority and traceability back to BRD objectives/requirements, plus governance
rows (risks, trade-offs, open questions, pending decisions, references, glossary)
and overview/objectives prose.

All versioned tables share the row mixin pattern (document_id FK, row_key,
version, is_current, is_locked, status, source, created_by, created_at)
established by the Concept Brief + BRD + FRS tables. Created in migration 0025.

nfr_traceability is NOT versioned (replace-all semantics on regen), mirroring
frs_traceability / test_case_traceability.
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

# NFR-specific enum types (created in migration 0025)
NfrCategory = Enum(
    "performance", "security", "availability", "usability",
    "scalability", "maintainability", "portability",
    name="nfr_category", create_type=False,
)
NfrPriority = Enum(
    "must", "should", "could", "wont",
    name="nfr_priority", create_type=False,
)
NfrTraceKind = Enum(
    "brd_objective", "brd_business_requirement", "brd_kpi", "brd_risk",
    "brd_text_block", "app_fact", "doc_section", "discover_qa", "within_nfr",
    name="nfr_trace_kind", create_type=False,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Core: the 7-category requirement table
# ═══════════════════════════════════════════════════════════════════════════════

class NfrRequirement(Base):
    """One row per NFR (NFR-nnn, global sequential across categories).

    Testable, solution-agnostic requirement with a measurement (the testability
    proof), a MoSCoW priority, and links back to BRD rows via brd_refs.
    """
    __tablename__ = "nfr_requirements"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_requirements_doc_key_ver"),
        Index("idx_nfr_requirements_current", "document_id", postgresql_where="is_current"),
        Index("idx_nfr_requirements_category", "document_id", "category", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_requirements_version"),
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
    category: Mapped[str] = mapped_column(NfrCategory, nullable=False)
    attribute: Mapped[str] = mapped_column(Text, nullable=False)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(NfrPriority, nullable=False, server_default="should")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    measurement: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    brd_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    completeness: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="low")
    na: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


# ═══════════════════════════════════════════════════════════════════════════════
# Governance tables (§9–§12 of the template)
# ═══════════════════════════════════════════════════════════════════════════════

class NfrRisk(Base):
    __tablename__ = "nfr_risks"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_risks_doc_key_ver"),
        Index("idx_nfr_risks_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_risks_version"),
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
    risk_id: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    affected_attribute: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    impact: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    likelihood: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    mitigation: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    risk_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")


class NfrTradeoff(Base):
    __tablename__ = "nfr_tradeoffs"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_tradeoffs_doc_key_ver"),
        Index("idx_nfr_tradeoffs_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_tradeoffs_version"),
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
    tradeoff: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    options_considered: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    decision: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decided_on: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_maker: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class NfrOpenQuestion(Base):
    __tablename__ = "nfr_open_questions"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_open_questions_doc_key_ver"),
        Index("idx_nfr_open_questions_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_open_questions_version"),
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
    question: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    due_date: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    oq_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")


class NfrDecision(Base):
    """Pending decisions (template §11.2)."""
    __tablename__ = "nfr_decisions"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_decisions_doc_key_ver"),
        Index("idx_nfr_decisions_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_decisions_version"),
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
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    owner: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    target_date: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    decision_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")


class NfrReference(Base):
    __tablename__ = "nfr_references"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_references_doc_key_ver"),
        Index("idx_nfr_references_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_references_version"),
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
    ref_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    location: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class NfrGlossary(Base):
    __tablename__ = "nfr_glossary"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_glossary_doc_key_ver"),
        Index("idx_nfr_glossary_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_glossary_version"),
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
    term: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    definition: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class NfrTextBlock(Base):
    """Prose blocks: overview, objectives (template §1–§2)."""
    __tablename__ = "nfr_text_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_nfr_text_blocks_doc_key_ver"),
        Index("idx_nfr_text_blocks_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_nfr_text_blocks_version"),
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
    block_kind: Mapped[str] = mapped_column(Text, nullable=False)  # overview | objectives
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── nfr_traceability (NOT versioned — replace-all per regen) ───────────────────

class NfrTraceability(Base):
    """Outward traceability: NFR rows → BRD/Apps/Docs/Discover sources.

    Every non-N/A NFR should have ≥1 traceability entry to a BRD objective or
    business requirement. Replace-all semantics: re-running the governance unit
    replaces the document's traceability rows.
    """
    __tablename__ = "nfr_traceability"
    __table_args__ = (
        Index("idx_nfr_traceability_doc", "document_id"),
        Index("idx_nfr_traceability_source", "document_id", "source_table", "source_row_key"),
        Index("idx_nfr_traceability_target", "document_id", "target_kind", "target_ref"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    source_table: Mapped[str] = mapped_column(Text, nullable=False)  # 'nfr_requirements'
    source_row_key: Mapped[str] = mapped_column(Text, nullable=False)  # NFR-nnn
    target_kind: Mapped[str] = mapped_column(NfrTraceKind, nullable=False)
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)  # BRD row_key (e.g. "BR-001" / "OBJ-001")
    target_label: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="high")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
