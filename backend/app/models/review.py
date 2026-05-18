import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

ReviewSeverity = Enum(
    "critical", "warning", "suggestion",
    name="review_severity", create_type=True,
)
ReviewCategory = Enum(
    "completeness", "ambiguity", "security", "data", "implementation",
    name="review_category", create_type=True,
)


class ReviewComment(TimestampMixin, Base):
    __tablename__ = "review_comments"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    spec_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spec_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    section: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(ReviewSeverity, nullable=False)
    category: Mapped[str] = mapped_column(ReviewCategory, nullable=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="review_comments")  # noqa: F821
    spec_version: Mapped["SpecVersion | None"] = relationship("SpecVersion", back_populates="review_comments")  # noqa: F821

    __table_args__ = (
        Index("idx_review_comments_project_id", "project_id"),
        Index("idx_review_comments_spec_version_id", "spec_version_id"),
        Index("idx_review_comments_project_dismissed_severity", "project_id", "dismissed", "severity"),
    )
