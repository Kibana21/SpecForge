import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class AppAskSession(TimestampMixin, Base):
    """A saved Ask-Brain chat thread. The whole transcript lives in one JSONB
    column (compact: role/content/mode + minimal citation refs) so a session is
    a single row — space-efficient and trivially replayable."""
    __tablename__ = "app_ask_sessions"
    __table_args__ = (Index("ix_ask_sessions_app_user", "app_id", "user_id", "updated_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
