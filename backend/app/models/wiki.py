import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import uuid_pk


class AppWikiSummary(Base):
    """One per corpus doc — the document's compiled wiki summary page."""
    __tablename__ = "app_wiki_summaries"
    __table_args__ = (
        UniqueConstraint("app_id", "doc_id", name="uq_wiki_summaries_app_doc"),
        Index("ix_wiki_summaries_app", "app_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_corpus_docs.id", ondelete="CASCADE"), nullable=False
    )
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    related_slugs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, default="short")
    compiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class AppWikiConcept(Base):
    """Emergent cross-document topic page synthesized from corpus docs."""
    __tablename__ = "app_wiki_concepts"
    __table_args__ = (
        UniqueConstraint("app_id", "slug", name="uq_wiki_concepts_app_slug"),
        Index("ix_wiki_concepts_app", "app_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    source_doc_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_slugs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tree_node_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    compiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
