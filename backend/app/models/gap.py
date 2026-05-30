import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

GapCategory = Enum(
    "scope", "data", "security", "integration", "ux",
    name="gap_category", create_type=True,
)
GapSeverity = Enum(
    "blocker", "major", "minor",
    name="gap_severity", create_type=True,
)


class GapQuestion(TimestampMixin, Base):
    __tablename__ = "gap_questions"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    ext_id: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(GapCategory, nullable=False)
    severity: Mapped[str] = mapped_column(GapSeverity, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    resolution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── E2 workspace open-question fields ───────────────────────────────────────
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="gap_detector")

    # ── Clarification Engine (E2) metadata — additive, nullable ─────────────────
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)  # contradiction|ambiguity|gap
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")  # tokens
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="gap_questions")  # noqa: F821

    __table_args__ = (
        Index("idx_gap_questions_project_id", "project_id"),
        Index("idx_gap_questions_project_resolved", "project_id", "resolved"),
    )
