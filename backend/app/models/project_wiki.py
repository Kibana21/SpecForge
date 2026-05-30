"""Project Wiki (E2) — emergent, source-grounded knowledge compiled from a
project's own uploaded documents. Mirrors the App Brain wiki (models/wiki.py)
scoped to a project instead of an app, so the same compile core + frontend can
serve both. See .claude/plans/E2-intelligent-intake.md.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import uuid_pk


class ProjectWikiSummary(Base):
    """One per project document — that document's compiled wiki summary page."""
    __tablename__ = "project_wiki_summaries"
    __table_args__ = (
        UniqueConstraint("project_id", "document_id", name="uq_pwiki_summaries_proj_doc"),
        Index("ix_pwiki_summaries_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    related_slugs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, default="short")
    compiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )


class ProjectWikiConcept(Base):
    """Emergent cross-document topic page synthesized from a project's documents."""
    __tablename__ = "project_wiki_concepts"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_pwiki_concepts_proj_slug"),
        Index("ix_pwiki_concepts_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
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
