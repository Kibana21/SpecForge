import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── E2 portfolio + intake fields ────────────────────────────────────────────
    human_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    business_unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    completion_pct: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    go_live_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    stage_progress: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    ru_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # Relationships
    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    extracted_requirements: Mapped[list["ExtractedRequirement"]] = relationship(  # noqa: F821
        "ExtractedRequirement", back_populates="project", cascade="all, delete-orphan"
    )
    spec_versions: Mapped[list["SpecVersion"]] = relationship(  # noqa: F821
        "SpecVersion", back_populates="project", cascade="all, delete-orphan"
    )
    gap_questions: Mapped[list["GapQuestion"]] = relationship(  # noqa: F821
        "GapQuestion", back_populates="project", cascade="all, delete-orphan"
    )
    review_comments: Mapped[list["ReviewComment"]] = relationship(  # noqa: F821
        "ReviewComment", back_populates="project", cascade="all, delete-orphan"
    )
    members: Mapped[list["ProjectMember"]] = relationship(  # noqa: F821
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_projects_deleted_at", "deleted_at"),
        Index("idx_projects_owner_id", "owner_id"),
    )


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="members")

    __table_args__ = (Index("idx_project_members_user_id", "user_id"),)
