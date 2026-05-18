# Security Standards for SPEC FORGE

Apply these rules whenever writing backend code, auth logic, API endpoints, or handling user data.

---

## Authentication (JWT)

- Use **HS256 with a 256-bit secret** minimum. Never hardcode the secret — always read from env var `JWT_SECRET`.
- Token expiry: **1 hour** for access tokens, **7 days** for refresh tokens. Issue both on login.
- Store refresh tokens in the database (hashed) so they can be revoked. Access tokens are stateless.
- JWT payload must contain only: `sub` (user_id as string), `role`, `exp`, `iat`, `jti` (unique token ID). Never put passwords, emails, or PII in the token.
- Validate token signature, expiry, and issuer on every request. Reject expired tokens with 401, not 403.
- Implement token refresh endpoint: `POST /api/auth/refresh` — accepts refresh token, returns new access + refresh pair, invalidates old refresh token (rotation).
- On logout, invalidate the refresh token in the database. Access tokens expire naturally.
- Frontend: store access token in memory (React state/context), refresh token in httpOnly cookie. Never localStorage for tokens.

## Password Security

- Hash passwords with **bcrypt** (passlib), cost factor **12** minimum.
- Enforce minimum password length of **8 characters** on the API (Pydantic validator).
- Never log passwords or include them in error messages.
- Never return password hashes in any API response — exclude from all Pydantic response schemas.
- Use constant-time comparison for password verification (passlib handles this).

## API Security

- **CORS**: Whitelist only the frontend origin (`FRONTEND_URL` env var). Never use `allow_origins=["*"]` in production.
- **Rate limiting**: Apply per-IP and per-user rate limits on auth endpoints (login: 5 attempts/minute, password reset: 3/hour). Use `slowapi` or Redis-based counters.
- **Input validation**: All request bodies validated via Pydantic schemas with strict types. Never pass raw user input to SQL, shell commands, or file paths.
- **SQL injection**: Always use SQLAlchemy ORM or parameterized queries. Never construct SQL strings with f-strings or `.format()`.
- **Request size limits**: Set `max_request_size` on FastAPI (10MB default, higher for file uploads with explicit limits).
- **HTTPS only**: Set `Secure` flag on all cookies. In production, redirect HTTP to HTTPS.

## Authorization (RBAC)

- Check permissions on **every** API endpoint using the `require_role()` dependency. No endpoint should be unprotected except `/api/auth/login`, `/api/auth/refresh`, and `/api/health`.
- Authorization checks must happen **server-side**. Frontend role checks are for UX only — never trust them for security.
- When accessing a resource (project, artifact), always verify the requesting user has access (ownership or membership). Never rely solely on role — check data-level access too.
- Use **403 Forbidden** for authenticated users without permission, **401 Unauthorized** for missing/invalid tokens, **404 Not Found** when the resource doesn't exist (don't leak whether it exists to unauthorized users).

## Data Protection

- Never log sensitive data: passwords, tokens, API keys, PII.
- Sanitize error messages in production — return generic messages, log detailed errors server-side.
- File uploads: validate content type (magic bytes, not just extension), scan filename for path traversal (`..`), generate random filenames for S3 storage.
- Set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block` headers via FastAPI middleware.
- Use `Content-Security-Policy` header on the frontend.

## API Keys & Secrets

- All external API keys (Google Imagen, Gemini, S3) must be in environment variables, never in code.
- Use `.env` files for local dev (gitignored). Use platform secrets (Railway, Vercel) for production.
- Rotate `JWT_SECRET` periodically — design token validation to support key rotation (check multiple secrets during transition).

## Dependency Security

- Pin all Python dependencies to exact versions in `requirements.txt`.
- Run `pip audit` or `safety check` before each release.
- Keep dependencies updated — especially security-critical ones (cryptography, python-jose, passlib).
