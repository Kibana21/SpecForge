import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db import Base
from app.models.base import uuid_pk

GenerationTypeEnum = Enum(
    "ai", "human", "regeneration", "restore", "import",
    name="generation_type",
    create_type=True,
)


class VersionSnapshot(Base):
    """Immutable point-in-time record of a document at a given version number."""
    __tablename__ = "version_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_key: Mapped[str] = mapped_column(String(255), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_sections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    change_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_type: Mapped[str] = mapped_column(GenerationTypeEnum, nullable=False, default="human")
    is_immutable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Pointer to stored content: filesystem path or "file:<uuid>" for DB-backed blobs
    content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("document_key", "version_no", name="uq_version_snapshots_key_ver"),
        Index("idx_version_snapshots_document_key", "document_key"),
        Index("idx_version_snapshots_actor_id", "actor_id"),
    )
