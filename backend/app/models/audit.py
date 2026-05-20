from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    project_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    document_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    affected_sections: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_audit_events_actor_id", "actor_id"),
        Index("idx_audit_events_event", "event"),
        Index("idx_audit_events_ts", "ts"),
        Index("idx_audit_events_project_id", "project_id"),
    )
