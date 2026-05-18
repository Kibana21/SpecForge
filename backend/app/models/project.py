import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    __table_args__ = (Index("idx_projects_deleted_at", "deleted_at"),)
