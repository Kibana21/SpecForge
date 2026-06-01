"""SDLC Artifact models: shared infrastructure + Concept Brief typed tables."""
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

# ── Shared enums (created in migration 0015) ──────────────────────────────────

ArtifactType = Enum("concept_brief", "brd", "frs", "test_cases", name="artifact_type", create_type=False)
ArtifactStatus = Enum("in_interview", "validated", "generating", "in_discover", name="artifact_status", create_type=False)
ArtifactRowStatus = Enum("active", "removed", name="artifact_row_status", create_type=False)
ArtifactRowSource = Enum("ai", "human", "regeneration", name="artifact_row_source", create_type=False)
ArtifactMessageRole = Enum("ai", "user", "question", "synthesis", name="artifact_message_role", create_type=False)


# ── Shared tables ─────────────────────────────────────────────────────────────

class ArtifactDocument(Base):
    """One per (project, artifact_type). Anchor for all versioned rows."""
    __tablename__ = "artifact_documents"
    __table_args__ = (
        UniqueConstraint("project_id", "artifact_type", name="uq_artifact_documents_project_type"),
        Index("idx_artifact_documents_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[str] = mapped_column(ArtifactType, nullable=False)
    status: Mapped[str] = mapped_column(ArtifactStatus, nullable=False, server_default="in_interview")
    unit_status: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    validated_snapshot_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    discover_analyzing: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")


class ArtifactMessage(Base):
    """Q&A transcript for an artifact document."""
    __tablename__ = "artifact_messages"
    __table_args__ = (
        Index("idx_artifact_messages_document_seq", "document_id", "seq"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(ArtifactMessageRole, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")


class ArtifactSource(Base):
    """Which uploaded project documents are curated as source material for a brief."""
    __tablename__ = "artifact_sources"
    __table_args__ = (
        UniqueConstraint("artifact_document_id", "source_document_id", name="uq_artifact_sources"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    artifact_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")


# ── Concept Brief typed tables ────────────────────────────────────────────────

class CbTextBlock(Base):
    """Prose blocks: business_context, problem_statement, value_hypothesis_if, value_hypothesis_then."""
    __tablename__ = "cb_text_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_text_blocks_doc_key_ver"),
        Index("idx_cb_text_blocks_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_text_blocks_version"),
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


class CbContextMap(Base):
    """6-row context map with fixed dimension row_keys."""
    __tablename__ = "cb_context_map"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_context_map_doc_key_ver"),
        Index("idx_cb_context_map_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_context_map_version"),
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
    dimension: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class CbOutcome(Base):
    __tablename__ = "cb_outcomes"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_outcomes_doc_key_ver"),
        Index("idx_cb_outcomes_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_outcomes_version"),
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
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class CbMetric(Base):
    __tablename__ = "cb_metrics"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_metrics_doc_key_ver"),
        Index("idx_cb_metrics_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_metrics_version"),
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
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    quantifiable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class CbCapability(Base):
    __tablename__ = "cb_capabilities"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_capabilities_doc_key_ver"),
        Index("idx_cb_capabilities_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_capabilities_version"),
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
    capability: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


class CbScopeItem(Base):
    __tablename__ = "cb_scope_items"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_scope_items_doc_key_ver"),
        Index("idx_cb_scope_items_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_scope_items_version"),
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


class CbMilestone(Base):
    __tablename__ = "cb_milestones"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_milestones_doc_key_ver"),
        Index("idx_cb_milestones_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_milestones_version"),
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


class CbGateCriterion(Base):
    __tablename__ = "cb_gate_criteria"
    __table_args__ = (
        UniqueConstraint("document_id", "row_key", "version", name="uq_cb_gate_criteria_doc_key_ver"),
        Index("idx_cb_gate_criteria_current", "document_id", postgresql_where="is_current"),
        CheckConstraint("version > 0", name="ck_cb_gate_criteria_version"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False)
    row_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    status: Mapped[str] = mapped_column(ArtifactRowStatus, nullable=False, server_default="active")
    source: Mapped[str] = mapped_column(ArtifactRowSource, nullable=False, server_default="ai")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    criterion: Mapped[str] = mapped_column(Text, nullable=False)
    gate_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="Pending")
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")


# ── Discover Phase tables (migration 0017) ────────────────────────────────────

class CbDiscoverQuestion(Base):
    """One row per (artifact_document, question_key). Upserted by analyze_brief."""
    __tablename__ = "cb_discover_questions"
    __table_args__ = (
        UniqueConstraint("artifact_document_id", "question_key", name="uq_cb_discover_questions_doc_key"),
        Index("ix_cb_discover_questions_doc", "artifact_document_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    artifact_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False
    )
    question_key: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")


class CbDiscoverEnhancedBrief(Base):
    """Stores original + enhanced brief text with attribution, for audit trail."""
    __tablename__ = "cb_discover_enhanced_briefs"
    __table_args__ = (
        Index("ix_cb_discover_enhanced_briefs_doc", "artifact_document_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    artifact_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifact_documents.id", ondelete="CASCADE"), nullable=False
    )
    original_brief: Mapped[str] = mapped_column(Text, nullable=False)
    enhanced_brief: Mapped[str] = mapped_column(Text, nullable=False)
    doc_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    app_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
