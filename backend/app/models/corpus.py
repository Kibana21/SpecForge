import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import uuid_pk

IndexStatusEnum = Enum(
    "pending", "running", "done", "error",
    name="index_status_enum",
    create_type=False,
)


class AppCorpusDoc(Base):
    __tablename__ = "app_corpus_docs"

    id: Mapped[uuid.UUID] = uuid_pk()
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_status: Mapped[str] = mapped_column(IndexStatusEnum, nullable=False, default="pending")
    index_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    app: Mapped["App"] = relationship("App", back_populates="corpus_docs")
    chunks: Mapped[list["AppChunk"]] = relationship(
        "AppChunk", back_populates="doc", cascade="all, delete-orphan"
    )


class AppChunk(Base):
    __tablename__ = "app_chunks"
    __table_args__ = (UniqueConstraint("doc_id", "chunk_no", name="uq_app_chunks_doc_chunk"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_corpus_docs.id", ondelete="CASCADE"), nullable=False
    )
    chunk_no: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    embedding = Column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    doc: Mapped["AppCorpusDoc"] = relationship("AppCorpusDoc", back_populates="chunks")


class AppDocTree(Base):
    """PageIndex reasoning tree for an app corpus doc (hybrid App Brain retrieval)."""
    __tablename__ = "app_doc_trees"
    __table_args__ = (Index("idx_app_doc_trees_app", "app_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    corpus_doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_corpus_docs.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    tree_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    page_texts: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    node_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


from app.models.app import App  # noqa: E402
