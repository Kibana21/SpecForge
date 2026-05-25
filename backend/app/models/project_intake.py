import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

# Reuse the confidence_level enum created in migration 0001 (do not re-create).
ConfidenceLevel = Enum("high", "medium", "low", name="confidence_level", create_type=False)


class ProjectApp(Base):
    """An application selected as in-scope for a project (apps-in-scope)."""
    __tablename__ = "project_apps"
    __table_args__ = (
        UniqueConstraint("project_id", "app_id", name="uq_project_apps_project_app"),
        Index("idx_project_apps_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    suggested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    app_brain_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    impact_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class Assumption(TimestampMixin, Base):
    """Assumption ledger entry (shared with Module 2)."""
    __tablename__ = "assumptions"
    __table_args__ = (Index("idx_assumptions_project_id", "project_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    ext_id: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(ConfidenceLevel, nullable=False, server_default="medium")
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")


class ReuseSelection(Base):
    """Provenance of a similar-project asset reused into a new project."""
    __tablename__ = "reuse_selections"
    __table_args__ = (Index("idx_reuse_selections_project", "project_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    asset_category: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class ProjectEmbedding(Base):
    """Project-level embedding for similar-project discovery + app suggestion."""
    __tablename__ = "project_embeddings"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    embedding = Column(Vector(768), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class TriageItem(Base):
    """Materialized per-user triage item (recomputed by Beat)."""
    __tablename__ = "triage_items"
    __table_args__ = (Index("idx_triage_items_user_priority", "user_id", "priority"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(String(500), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
