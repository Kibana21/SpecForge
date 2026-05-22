import uuid

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

ParseStatus = Enum("pending", "done", "error", name="parse_status", create_type=True)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_status: Mapped[str] = mapped_column(
        ParseStatus, nullable=False, server_default="pending"
    )
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── E2 source-intake state (chunk/embed → PageIndex tree build) ─────────────
    indexing_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    index_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="documents")  # noqa: F821

    __table_args__ = (
        Index("idx_documents_project_id", "project_id"),
        CheckConstraint("size_bytes > 0", name="ck_documents_size_bytes_positive"),
    )
