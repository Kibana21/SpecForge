import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db import Base
from app.models.base import uuid_pk


class StorageFile(Base):
    """Metadata record for any file stored by the platform."""
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    blobs: Mapped[list["StorageFileBlob"]] = relationship(
        "StorageFileBlob",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="StorageFileBlob.chunk_no",
    )

    __table_args__ = (
        Index("idx_files_sha256", "sha256"),
        Index("idx_files_created_by", "created_by"),
    )


class StorageFileBlob(Base):
    """Binary chunk for a StorageFile (single chunk_no=0 for files ≤ chunk size)."""
    __tablename__ = "file_blobs"

    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_no: Mapped[int] = mapped_column(Integer, primary_key=True, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    file: Mapped["StorageFile"] = relationship("StorageFile", back_populates="blobs")
