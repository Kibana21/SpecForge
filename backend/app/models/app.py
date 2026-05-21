import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk


class App(TimestampMixin, Base):
    __tablename__ = "apps"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    tier: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("tier BETWEEN 1 AND 3", name="ck_apps_tier"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    domain_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rebuild_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    members: Mapped[list["AppMember"]] = relationship(
        "AppMember", back_populates="app", cascade="all, delete-orphan"
    )
    corpus_docs: Mapped[list["AppCorpusDoc"]] = relationship(
        "AppCorpusDoc", back_populates="app", cascade="all, delete-orphan"
    )
    facts: Mapped[list["AppFact"]] = relationship(
        "AppFact", back_populates="app", cascade="all, delete-orphan"
    )


class AppMember(Base):
    __tablename__ = "app_members"

    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("apps.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    kind: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("kind IN ('owner', 'delegate')", name="ck_app_members_kind"),
        nullable=False,
        default="delegate",
    )
    added_at: Mapped[str] = mapped_column(server_default=text("now()"), nullable=False)

    app: Mapped["App"] = relationship("App", back_populates="members")


from app.models.corpus import AppCorpusDoc  # noqa: E402
from app.models.fact import AppFact  # noqa: E402
