# FastAPI Hardening Patterns

Read this when working on: FastAPI app setup, dependencies (`Depends`), route handlers, middleware, CORS, rate limiting, Pydantic schemas for user-facing endpoints, SQLAlchemy queries with user input, file uploads, audit logging.

## Table of contents

1. Auth and RBAC dependencies
2. Resource-level authorization
3. CORS configuration
4. Rate limiting
5. Pydantic validation patterns
6. SQLAlchemy safe-query patterns
7. Security headers middleware
8. File upload hardening
9. Error handling
10. Audit logging
11. Settings module

---

## 1. Auth and RBAC dependencies

Centralize auth in dependencies. Route handlers never parse tokens themselves.

```python
# app/api/deps.py
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(creds.credentials)

    # Kill-switch check
    if await is_jti_revoked(payload["jti"]):
        raise HTTPException(401, "Token revoked")

    user = await db.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise HTTPException(401, "User not found or inactive")
    return user

def require_role(*roles: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            # 403 because authenticated but not authorized
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker
```

Usage:
```python
@router.get("/admin/users")
async def list_users(_: User = Depends(require_role("admin"))):
    ...

@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
```

**Unprotected endpoints (whitelist):**
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`
- `POST /api/auth/signup` (if applicable)
- `GET /api/health`

Every other endpoint goes through `require_user` or `require_role`. If you find yourself writing an endpoint without an auth dependency, stop and ask if it really should be public.

## 2. Resource-level authorization

Role alone is insufficient when users have access to specific resources. A `user` role can read `their own` projects, not all projects.

```python
async def require_project_access(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        # 404, not 403 — don't leak existence
        raise HTTPException(404, "Project not found")

    is_owner = project.owner_id == user.id
    is_member = await db.scalar(
        select(1).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    )
    is_admin = user.role == "admin"

    if not (is_owner or is_member or is_admin):
        # Still 404 — same response shape as "doesn't exist"
        raise HTTPException(404, "Project not found")
    return project

@router.get("/projects/{project_id}")
async def get_project(project: Project = Depends(require_project_access)):
    return ProjectResponse.model_validate(project)
```

Note: returning 404 (not 403) for unauthorized resource access prevents an attacker from confirming the existence of resources they shouldn't know about.

## 3. CORS configuration

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],  # exact origin, from env
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)
```

**Never** combine `allow_origins=["*"]` with `allow_credentials=True`. Browsers reject this combination, but if a misconfigured middleware accepts it, you've created a CSRF bypass.

For multi-environment setups, allow a small list:
```python
allow_origins=[settings.frontend_url, settings.frontend_url_staging]
```

Or use a regex when subdomains are involved:
```python
allow_origin_regex=r"^https://([a-z0-9-]+\.)?spec-forge\.example\.com$"
```

## 4. Rate limiting

```python
# app/core/rate_limit.py
from slowapi import Limiter
from slowapi.util import get_remote_address

def get_user_or_ip(request: Request) -> str:
    # Prefer authenticated user; fall back to IP
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_access_token(auth[7:])
            return f"user:{payload['sub']}"
        except Exception:
            pass
    return f"ip:{get_remote_address(request)}"

limiter = Limiter(key_func=get_user_or_ip)
```

```python
# app/main.py
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Recommended limits:**
- `POST /auth/login`: 5/minute per IP
- `POST /auth/password-reset/request`: 3/hour per IP
- `POST /auth/password-reset/confirm`: 5/hour per IP
- `POST /auth/signup`: 3/hour per IP
- Expensive operations (LLM calls, video generation): per-user limits matching plan/quota.
- Default for everything else: 100/minute per user.

For production behind a reverse proxy: ensure `X-Forwarded-For` is respected and trusted. Misconfigured, every request looks like it's from `127.0.0.1` and the limit is shared across all users.

## 5. Pydantic validation patterns

**Strict input schemas with explicit constraints:**

```python
from pydantic import BaseModel, EmailStr, Field, field_validator

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.lower() in {"password", "12345678", "qwertyui"}:
            raise ValueError("Password is too common")
        return v
```

**Response schemas exclude sensitive fields:**

```python
class UserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
    # NOTE: no password_hash, no internal flags, no MFA secret, no PII beyond email
```

Never return the SQLAlchemy model directly:
```python
# WRONG — exposes whatever fields exist
return user

# RIGHT — Pydantic filters
return UserResponse.model_validate(user)
```

**Request size limits** (FastAPI doesn't enforce by default; do it at the reverse proxy or via middleware):
```python
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
        return JSONResponse(status_code=413, content={"detail": "Request too large"})
    return await call_next(request)
```

## 6. SQLAlchemy safe queries

**Always:**
```python
# Parameterized via ORM — safe
stmt = select(User).where(User.email == user_input)

# Parameterized via text() — safe
stmt = text("SELECT * FROM users WHERE email = :email").bindparams(email=user_input)
```

**Never:**
```python
# SQL injection
stmt = text(f"SELECT * FROM users WHERE email = '{user_input}'")
stmt = text("SELECT * FROM users WHERE email = '{}'".format(user_input))
```

For dynamic column/table names (which can't be parameterized), validate against an allowlist:
```python
ALLOWED_SORT_COLUMNS = {"created_at", "updated_at", "name"}
if sort_col not in ALLOWED_SORT_COLUMNS:
    raise HTTPException(400, "Invalid sort column")
stmt = select(Project).order_by(text(sort_col))
```

## 7. Security headers middleware

```python
# app/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS only when behind HTTPS — let the reverse proxy add this in prod
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

Note: `X-XSS-Protection: 1; mode=block` is deprecated and can introduce vulnerabilities in older browsers. Don't set it. Use CSP instead (see `nextjs-patterns.md` for frontend CSP).

## 8. File upload hardening

```python
import magic  # python-magic
from fastapi import UploadFile, HTTPException

ALLOWED_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

@router.post("/upload")
async def upload(
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    # Read first 2KB to detect MIME from magic bytes (not the client-supplied header)
    head = await file.read(2048)
    detected_mime = magic.from_buffer(head, mime=True)
    if detected_mime not in ALLOWED_MIME:
        raise HTTPException(400, "Unsupported file type")

    # Read rest, enforcing size cap
    rest = await file.read()
    if len(head) + len(rest) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large")

    # Generate random filename — never trust client-supplied name for storage path
    ext = ALLOWED_MIME[detected_mime]
    storage_key = f"uploads/{user.id}/{uuid.uuid4().hex}{ext}"

    await s3.put_object(Bucket=..., Key=storage_key, Body=head + rest, ContentType=detected_mime)
    return {"key": storage_key}
```

**Never:**
- Trust `file.content_type` from the client.
- Use `file.filename` as part of a filesystem path.
- Save uploads to a publicly-served directory without checking content.

## 9. Error handling

```python
# app/main.py
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    logger.exception(
        "Unhandled exception",
        extra={"correlation_id": correlation_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "correlation_id": correlation_id,
        },
    )
```

The client gets a `correlation_id` they can quote in support requests; the server has the full stack trace. Stack traces never reach the client in production.

In dev, you can show more — gate on `settings.environment == "production"`.

## 10. Audit logging

Auth events get a structured audit log entry. Separate from application logs, ideally to a dedicated stream (database table, log topic, or audit log service).

```python
# app/core/audit.py
async def audit_log(
    event: str,
    user_id: str | None = None,
    email: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
    metadata: dict | None = None,
):
    entry = AuditEvent(
        id=str(uuid.uuid4()),
        event=event,
        user_id=user_id,
        email_hash=hashlib.sha256(email.encode()).hexdigest() if email else None,
        ip=ip,
        user_agent=user_agent[:255] if user_agent else None,
        correlation_id=correlation_id,
        metadata=metadata or {},
        created_at=now_utc(),
    )
    # Write to dedicated audit log destination
    await audit_writer.write(entry)
```

**Events to log:**

| Event | When |
|---|---|
| `login_success` | Successful login |
| `login_failed` | Bad credentials, bad password, locked account |
| `login_blocked_lockout` | Login attempted on locked account |
| `logout` | User logged out |
| `refresh_token_rotated` | Refresh succeeded |
| `refresh_token_reuse_detected` | Stolen token alarm |
| `password_reset_requested` | Reset email requested |
| `password_reset_confirmed` | Password actually changed |
| `password_changed` | Authenticated password change |
| `role_changed` | Admin changed a user's role |
| `permission_denied` | 403 on protected endpoint |
| `account_locked` | Progressive lockout triggered |
| `account_unlocked` | Admin or expiry unlocked |
| `mfa_enabled` / `mfa_disabled` | MFA state change |
| `api_key_created` / `api_key_revoked` | External API key lifecycle |

**Note**: store email as hash, not plaintext, in audit logs to limit PII exposure while still allowing investigation (search by hash of suspected email).

## 11. Settings module

Fail loudly at startup if required secrets are missing. Don't paper over with defaults.

```python
# app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Required — no defaults
    jwt_secret: str
    database_url: str
    frontend_url: str
    redis_url: str

    # Optional with safe defaults
    environment: str = "development"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bcrypt_rounds: int = 12

    # External services
    openai_api_key: str | None = None
    google_api_key: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()  # raises ValidationError at import if required vars missing
```

If `Settings()` raises at startup, the app refuses to boot. This is correct — a misconfigured app silently using a default JWT secret is worse than a clear failure.
