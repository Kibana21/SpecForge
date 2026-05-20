import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
import re

from pydantic import BaseModel, Field
from pydantic.functional_validators import AfterValidator
from typing import Annotated

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("Invalid email address")
    return v


EmailField = Annotated[str, AfterValidator(_normalize_email)]
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.audit import emit as audit_emit
from app.core.rbac import get_current_user
from app.core.redis_client import revoke_jti
from app.core.security import (
    bcrypt_dummy_verify,
    create_access_token,
    decode_access_token,
    generate_raw_token,
    hash_password,
    sha256_hex,
    verify_password,
)
from app.db import get_db
from app.limiter import limiter
from app.models.auth import PasswordResetToken, RefreshToken
from app.models.user import User
from app.schemas.envelope import ok

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _issue_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    family_id: str,
) -> str:
    settings = get_settings()
    raw = generate_raw_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=sha256_hex(raw),
        family_id=family_id,
        expires_at=_now() + timedelta(days=settings.refresh_token_days),
    )
    db.add(record)
    return raw


def _set_refresh_cookie(response: JSONResponse, raw: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "refresh_token",
        raw,
        httponly=True,
        secure=settings.environment != "development",
        samesite="lax",
        max_age=settings.refresh_token_days * 86_400,
        path="/",
    )


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailField
    password: str = Field(min_length=8, max_length=128)


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")[:255]

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        bcrypt_dummy_verify()
        await audit_emit(db, event="login_failed", email=body.email, ip=ip, user_agent=ua)
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if user.locked_until and user.locked_until > _now():
        await audit_emit(db, event="login_blocked_lockout", actor_id=str(user.id), ip=ip, user_agent=ua)
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if user.status == "disabled":
        bcrypt_dummy_verify()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not verify_password(body.password, user.password_hash):
        user.failed_login_count = (user.failed_login_count or 0) + 1
        lockout_map = {5: 5, 6: 15}
        if user.failed_login_count >= 5:
            minutes = lockout_map.get(user.failed_login_count, 60)
            user.locked_until = _now() + timedelta(minutes=minutes)
            user.status = "locked"
        await audit_emit(db, event="login_failed", actor_id=str(user.id), ip=ip, user_agent=ua)
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    # Successful login — clear lockout state
    user.failed_login_count = 0
    user.locked_until = None
    if user.status == "locked":
        user.status = "active"

    access_token, _ = create_access_token(user_id=str(user.id), role=user.role)
    raw_refresh = await _issue_refresh_token(db, user_id=user.id, family_id=str(uuid.uuid4()))

    await audit_emit(db, event="login_success", actor_id=str(user.id), ip=ip, user_agent=ua)
    await db.commit()

    response = JSONResponse(content=ok({"access_token": access_token, "token_type": "bearer"}))
    _set_refresh_cookie(response, raw_refresh)
    return response


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing refresh token")

    token_hash = sha256_hex(raw)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if record.revoked:
        # Reuse detected — revoke entire token family
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == record.family_id)
            .values(revoked=True)
        )
        await audit_emit(
            db,
            event="refresh_token_reuse_detected",
            actor_id=str(record.user_id),
            ip=ip,
        )
        await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session invalidated")

    if record.expires_at < _now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")

    result2 = await db.execute(select(User).where(User.id == record.user_id))
    user = result2.scalar_one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    # Rotate: mark old revoked, issue new with same family
    record.revoked = True
    new_raw = await _issue_refresh_token(db, user_id=user.id, family_id=record.family_id)
    access_token, _ = create_access_token(user_id=str(user.id), role=user.role)

    await audit_emit(db, event="refresh_token_rotated", actor_id=str(user.id), ip=ip)
    await db.commit()

    response = JSONResponse(content=ok({"access_token": access_token, "token_type": "bearer"}))
    _set_refresh_cookie(response, new_raw)
    return response


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    ip = _client_ip(request)

    raw = request.cookies.get("refresh_token")
    if raw:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == sha256_hex(raw))
            .values(revoked=True)
        )

    # Kill-switch the access token's JTI so it can't be replayed within its lifetime
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_access_token(auth_header[7:])
            await revoke_jti(payload["jti"], ttl_seconds=settings.access_token_minutes * 60)
        except Exception:
            pass

    await audit_emit(db, event="logout", actor_id=str(current_user.id), ip=ip)
    await db.commit()

    response = JSONResponse(content=ok({"status": "ok"}))
    response.delete_cookie("refresh_token", path="/")
    return response


# ── Me ────────────────────────────────────────────────────────────────────────

class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    status: str
    is_test: bool

    model_config = {"from_attributes": True}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return ok(UserMeResponse.model_validate(current_user).model_dump(mode="json"))


# ── Password reset ────────────────────────────────────────────────────────────

class PasswordResetRequestBody(BaseModel):
    email: EmailField


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password-reset/request", status_code=204)
@limiter.limit("3/hour")
async def request_password_reset(
    request: Request,
    body: PasswordResetRequestBody,
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if user:
        raw_token = generate_raw_token()
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=sha256_hex(raw_token),
            expires_at=_now() + timedelta(minutes=15),
        ))
        # TODO E1: enqueue password reset email via Celery

    # Always 204 — never reveal whether email exists
    await audit_emit(db, event="password_reset_requested", email=body.email, ip=ip)
    await db.commit()


@router.post("/password-reset/confirm", status_code=204)
@limiter.limit("5/hour")
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirmBody,
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    token_hash = sha256_hex(body.token)
    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,  # noqa: E712
            PasswordResetToken.expires_at > _now(),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    record.used = True
    result2 = await db.execute(select(User).where(User.id == record.user_id))
    user = result2.scalar_one_or_none()
    if user:
        user.password_hash = hash_password(body.new_password)
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
        )

    await audit_emit(
        db,
        event="password_reset_confirmed",
        actor_id=str(user.id) if user else None,
        ip=ip,
    )
    await db.commit()
