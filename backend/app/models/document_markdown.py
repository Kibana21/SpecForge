import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import uuid_pk


class DocumentMarkdown(Base):
    """Cached markdown output from the markdown converter service.

    source_hash (SHA-256 of raw bytes) is the primary dedup key — identical content
    from different uploads is only converted once.  correlation_id links the row back
    to the calling entity (corpus_doc.id, document.id, …) for traceability.
    """

    __tablename__ = "document_markdown"
    __table_args__ = (
        Index("ix_docmd_source_hash", "source_hash"),
        Index("ix_docmd_correlation_id", "correlation_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    markdown_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
