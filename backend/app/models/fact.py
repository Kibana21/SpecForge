import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

FactKindEnum = Enum(
    "capability", "constraint", "limitation", "integration", "gotcha",
    name="fact_kind_enum",
    create_type=False,
)
FactConfidenceEnum = Enum(
    "high", "medium", "low",
    name="fact_confidence_enum",
    create_type=False,
)
FactStatusEnum = Enum(
    "active", "proposed", "dismissed",
    name="fact_status_enum",
    create_type=False,
)


class AppFact(TimestampMixin, Base):
    __tablename__ = "app_facts"

    id: Mapped[uuid.UUID] = uuid_pk()
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(FactKindEnum, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[str] = mapped_column(FactConfidenceEnum, nullable=False, default="medium")
    status: Mapped[str] = mapped_column(FactStatusEnum, nullable=False, default="active")
    chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    app: Mapped["App"] = relationship("App", back_populates="facts")


from app.models.app import App  # noqa: E402
