import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class ProjectAskSession(TimestampMixin, Base):
    """A saved Project Copilot chat thread. The whole transcript lives in one JSONB
    column (compact: role/content + minimal citation refs) so a session is a single
    row — space-efficient and trivially replayable. Mirrors AppAskSession."""
    __tablename__ = "project_ask_sessions"
    __table_args__ = (
        Index("ix_project_ask_sessions_project_user", "project_id", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
