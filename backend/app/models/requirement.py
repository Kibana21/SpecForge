import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

RequirementCategory = Enum(
    "functional", "non_functional", "constraint", "assumption", "stakeholder",
    name="requirement_category", create_type=True,
)
ConfidenceLevel = Enum(
    "high", "medium", "low",
    name="confidence_level", create_type=True,
)


class ExtractedRequirement(TimestampMixin, Base):
    __tablename__ = "extracted_requirements"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(RequirementCategory, nullable=False)
    ext_id: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(ConfidenceLevel, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="extracted_requirements")  # noqa: F821

    __table_args__ = (
        Index("idx_extracted_requirements_project_id", "project_id"),
        Index("idx_extracted_requirements_project_category", "project_id", "category"),
        Index("idx_extracted_requirements_document_id", "document_id"),
    )
