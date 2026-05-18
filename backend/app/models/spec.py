import uuid

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

SpecType = Enum(
    "functional", "technical", "user_stories", "review",
    name="spec_type", create_type=True,
)


class SpecVersion(TimestampMixin, Base):
    __tablename__ = "spec_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    spec_type: Mapped[str] = mapped_column(SpecType, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    project: Mapped["Project"] = relationship("Project", back_populates="spec_versions")  # noqa: F821
    review_comments: Mapped[list["ReviewComment"]] = relationship(  # noqa: F821
        "ReviewComment", back_populates="spec_version"
    )

    __table_args__ = (
        Index("idx_spec_versions_project_id", "project_id"),
        Index("idx_spec_versions_project_type_version", "project_id", "spec_type", "version_number"),
        CheckConstraint("version_number > 0", name="ck_spec_versions_version_positive"),
    )
