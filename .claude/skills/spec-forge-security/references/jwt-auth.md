# JWT Auth, Sessions, and Auth Flows

Read this when working on: login, logout, token refresh, password reset, email verification, JWT issuance or validation, session revocation, account lockout, or anything that creates or destroys an auth credential.

## Table of contents

1. JWT issuance and validation
2. Refresh token rotation
3. Kill-switch (JTI blocklist)
4. Algorithm pinning and confusion attacks
5. Login flow
6. Logout flow
7. Password reset flow
8. Email verification flow
9. Account lockout and brute-force defense
10. Enumeration prevention
11. Password hashing

---

## 1. JWT issuance and validation

**Tokens:**
- Access token: **15 minutes** (not 1 hour — short lifetimes reduce blast radius of leak).
- Refresh token: **7 days**, single-use (rotated on each refresh), stored hashed in DB.

**Claims (access token):**
```
{
  "sub": "<user_id as string>",
  "role": "<role>",
  "exp": <unix ts>,
  "iat": <unix ts>,
  "jti": "<uuid4>",
  "iss": "spec-forge"
}
```

Never include email, password, name, or any PII in the JWT. The token is base64-decodable by anyone who has it.

**Settings module:**
```python
# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str  # required — fail at startup if missing
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    issuer: str = "spec-forge"

    class Config:
        env_file = ".env"

settings = Settings()  # raises if jwt_secret missing — that's intentional
```

**Issuance:**
```python
# app/core/security.py
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt
from app.core.config import settings

def create_access_token(user_id: str, role: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iat": now,
        "jti": jti,
        "iss": settings.issuer,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti
```

**Validation:**
```python
# app/core/security.py
from jose import jwt, JWTError
from fastapi import HTTPException, status

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],  # pinned — never trust header
            issuer=settings.issuer,
            options={"require": ["exp", "iat", "sub", "jti", "iss"]},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
```

**Critical**: `algorithms=[...]` is a list. Passing `algorithm=` (singular) is wrong in `python-jose` and may be silently ignored. With `pyjwt`, omitting it allows algorithm confusion (attacker submits an `alg: none` token, library accepts).

## 2. Refresh token rotation

Refresh tokens are single-use. On refresh, the old one is invalidated and a new one issued. Reuse of an already-rotated refresh token is a strong signal of theft — when detected, invalidate the entire token family for that user.

**DB schema:**
```python
# app/models/refresh_token.py
from sqlalchemy import String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String, index=True)  # sha256 of token
    family_id: Mapped[str] = mapped_column(String, index=True)  # rotated tokens share family
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
```

**Refresh endpoint:**
```python
# app/api/auth.py
@router.post("/refresh")
async def refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw = request.cookies.get("refresh_token")
    if not raw:
        raise HTTPException(401, "Missing refresh token")

    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    record = (await db.execute(stmt)).scalar_one_or_none()

    if not record:
        # token not in DB — either forged or already rotated long ago
        raise HTTPException(401, "Invalid refresh token")

    if record.revoked:
        # REUSE DETECTED — token was rotated but someone is presenting the old one
        # Invalidate the entire family
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == record.family_id)
            .values(revoked=True)
        )
        await db.commit()
        await audit_log(
            event="refresh_token_reuse_detected",
            user_id=record.user_id,
            ip=request.client.host,
        )
        raise HTTPException(401, "Token reuse detected; all sessions revoked")

    if record.expires_at < now_utc():
        raise HTTPException(401, "Refresh token expired")

    # Rotate: mark old as revoked, issue new with same family_id
    record.revoked = True
    new_token = await issue_refresh_token(
        db, user_id=record.user_id, family_id=record.family_id
    )
    access_token, _ = create_access_token(user_id=record.user_id, role=...)

    response = JSONResponse({"access_token": access_token})
    response.set_cookie(
        "refresh_token",
        new_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=settings.refresh_token_days * 86400,
        path="/api/auth",
    )
    await db.commit()
    return response
```

## 3. Kill-switch: JTI blocklist

Stateless JWTs can't be revoked individually — but you need a kill-switch for emergencies (compromise, immediate role downgrade, account suspension).

Pattern: a Redis set of revoked JTIs, with TTL equal to access token lifetime. The auth dependency checks membership on every request.

```python
# app/core/security.py
async def is_jti_revoked(jti: str) -> bool:
    return await redis.sismember("revoked_jti", jti)

async def revoke_jti(jti: str, ttl_seconds: int):
    await redis.sadd("revoked_jti", jti)
    await redis.expire("revoked_jti", ttl_seconds)  # bulk expire is fine
```

This is bounded — the set never grows beyond `~tokens issued per access_token_minutes`. Use this for: forced logout, immediate role change, account suspension. Don't use it for normal logout (refresh token deletion handles that).

## 4. Algorithm pinning

The most common JWT vulnerability is library misconfiguration that allows `alg: none` or HS/RS confusion. Always:

```python
# CORRECT
payload = jwt.decode(token, secret, algorithms=["HS256"])

# WRONG — library may accept whatever's in the token header
payload = jwt.decode(token, secret)

# WRONG — singular `algorithm` is ignored by python-jose on decode
payload = jwt.decode(token, secret, algorithm="HS256")
```

If you ever migrate algorithms (HS256 → RS256), the validation code should accept BOTH temporarily, then drop the old. Never accept "any of [HS256, none]" — `"none"` should never appear in `algorithms`.

## 5. Login flow

```python
# app/api/auth.py
from slowapi import Limiter
limiter = Limiter(key_func=lambda r: r.client.host)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # NOTE: no user object here — fetch via /me

@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == body.email.lower()))

    # Constant-time-ish: always run bcrypt even if user is None, to avoid timing oracle
    if user is None:
        await bcrypt_dummy_verify()  # verify against a fixed hash
        await audit_log(event="login_failed", email=body.email, ip=request.client.host)
        raise HTTPException(401, "Invalid credentials")  # generic — no enumeration

    if user.locked_until and user.locked_until > now_utc():
        await audit_log(event="login_blocked_lockout", user_id=user.id, ip=request.client.host)
        raise HTTPException(401, "Invalid credentials")  # don't reveal lockout

    if not bcrypt.verify(body.password, user.password_hash):
        await register_failed_attempt(db, user)
        await audit_log(event="login_failed", user_id=user.id, ip=request.client.host)
        raise HTTPException(401, "Invalid credentials")

    if not user.email_verified:
        raise HTTPException(403, "Email not verified")

    await reset_failed_attempts(db, user)
    await audit_log(event="login_success", user_id=user.id, ip=request.client.host)

    access_token, jti = create_access_token(user_id=user.id, role=user.role)
    refresh_token = await issue_refresh_token(db, user_id=user.id, family_id=str(uuid.uuid4()))

    response = JSONResponse({"access_token": access_token, "token_type": "bearer"})
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=True, samesite="lax",
        max_age=settings.refresh_token_days * 86400,
        path="/api/auth",
    )
    return response
```

Key points:
- Both branches (user-not-found, wrong password) return identical response and similar timing.
- Lockout is opaque to the caller — still returns "Invalid credentials".
- Audit log distinguishes the cases server-side for monitoring.

## 6. Logout flow

```python
@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    raw = request.cookies.get("refresh_token")
    if raw:
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )

    # Optionally also kill-switch the current access token
    payload = decode_access_token(extract_bearer(request))
    await revoke_jti(payload["jti"], ttl_seconds=settings.access_token_minutes * 60)

    await audit_log(event="logout", user_id=current_user.id, ip=request.client.host)
    response = JSONResponse({"status": "ok"})
    response.delete_cookie("refresh_token", path="/api/auth")
    return response
```

## 7. Password reset flow

The most-broken auth flow in the wild. Rules:

- Reset token is a **single-use, 15-minute** random value (32+ bytes from `secrets.token_urlsafe`).
- Token is **hashed at rest** (same as refresh tokens).
- **Always** return success regardless of whether the email exists (enumeration).
- On successful reset: **invalidate all existing refresh tokens** for that user and **revoke active access tokens** via JTI blocklist (or accept that they expire within 15 min).
- Send the email **outside the request cycle** if possible (background job), but the API response time must not differ based on whether the email exists — add a small fixed delay or always enqueue a no-op.

```python
class PasswordResetRequest(BaseModel):
    email: EmailStr

@router.post("/password-reset/request", status_code=204)
@limiter.limit("3/hour")
async def request_password_reset(
    request: Request,
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user:
        token = secrets.token_urlsafe(32)
        await db.execute(insert(PasswordResetToken).values(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=now_utc() + timedelta(minutes=15),
        ))
        await db.commit()
        await enqueue_password_reset_email(user.email, token)
    else:
        await enqueue_noop()  # equalize timing
    await audit_log(event="password_reset_requested", email=body.email, ip=request.client.host)
    return  # 204 regardless

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

@router.post("/password-reset/confirm", status_code=204)
@limiter.limit("5/hour")
async def confirm_password_reset(
    request: Request,
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    record = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > now_utc(),
        )
    )
    if not record:
        raise HTTPException(400, "Invalid or expired reset token")

    record.used = True
    user = await db.get(User, record.user_id)
    user.password_hash = bcrypt.hash(body.new_password)

    # Invalidate all active sessions for this user
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
    )
    await db.commit()
    await audit_log(event="password_reset_confirmed", user_id=user.id, ip=request.client.host)
    return
```

## 8. Email verification

Same pattern as password reset: random token, hashed at rest, 24-hour expiry, single use. Unverified users can log in but cannot access protected endpoints (or have a restricted role).

## 9. Account lockout and brute-force defense

Rate limiting (5/min/IP) is necessary but not sufficient — a distributed attacker bypasses it. Add per-account progressive lockout:

```python
async def register_failed_attempt(db, user: User):
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= 5:
        # Progressive: 5 min, then 15, then 60
        lockout_minutes = {5: 5, 6: 15, 7: 60}.get(user.failed_login_count, 60)
        user.locked_until = now_utc() + timedelta(minutes=lockout_minutes)
    await db.commit()

async def reset_failed_attempts(db, user: User):
    user.failed_login_count = 0
    user.locked_until = None
    await db.commit()
```

Lockout is invisible to the caller (still returns "Invalid credentials") to prevent attackers from probing which accounts are locked.

## 10. Enumeration prevention

Signup, login, password reset, and "resend verification" must not reveal whether an email is registered.

- **Signup**: if email exists, send a "your account already exists, log in or reset password" email to that address. API still returns success.
- **Login**: identical response for "no such user" and "wrong password".
- **Password reset**: 204 regardless of whether email exists.
- **Resend verification**: same.

If business requirements force enumeration in one place (e.g., a B2B admin invite UI), document it explicitly and ensure that endpoint is admin-only.

## 11. Password hashing

```python
from passlib.hash import bcrypt

# Hash
password_hash = bcrypt.using(rounds=12).hash(plain_password)

# Verify (constant-time inside passlib)
ok = bcrypt.verify(plain_password, stored_hash)
```

- Cost factor 12 minimum. Increase to 13–14 on faster hardware if login latency budget allows.
- Truncate input at 72 bytes? Bcrypt does this silently — to avoid surprise, enforce `max_length=128` in Pydantic and pre-hash with SHA-256 if you must support longer passwords. Default is: cap at 128, accept bcrypt's 72-byte limit (well within range).
- Never log the password, even in debug. Never return the hash in any response.
