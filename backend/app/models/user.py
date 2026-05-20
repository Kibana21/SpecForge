import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, uuid_pk

UserRoleEnum = Enum(
    "business_analyst",
    "product_owner",
    "solution_architect",
    "app_owner",
    "qa_lead",
    "compliance_reviewer",
    "platform_admin",
    name="user_role",
    create_type=False,
)

UserStatusEnum = Enum(
    "active",
    "locked",
    "disabled",
    name="user_status",
    create_type=False,
)

ALL_ROLES = {
    "business_analyst",
    "product_owner",
    "solution_architect",
    "app_owner",
    "qa_lead",
    "compliance_reviewer",
    "platform_admin",
}


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(UserRoleEnum, nullable=False)
    status: Mapped[str] = mapped_column(UserStatusEnum, nullable=False, server_default="active")
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_status", "status"),
    )
