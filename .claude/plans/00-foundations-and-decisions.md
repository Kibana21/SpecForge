# SpecForge — Foundations & Decisions (Tier 1)

This document captures the decisions every milestone plan depends on: tech stack, repo layout, and the cross-cutting standards (auth, RBAC, audit, storage, jobs, versioning, provenance, testing). Write it once; the per-epic deep plans reference it instead of re-deciding.

**Companion docs:** [`01-master-roadmap.md`](01-master-roadmap.md) (sequencing) and the requirement source of truth in [`../prd/`](../prd/prd-00-index.md) (71 BRs across 6 modules).

**Binding skills (consult before writing code):**
- **[`spec-forge-security`](../skills/spec-forge-security/SKILL.md)** — all auth/RBAC/JWT/CORS/rate-limit/upload/secrets/error/logging rules for the **FastAPI backend and Next.js frontend**. Read the matching reference file per task: `references/jwt-auth.md`, `references/fastapi-patterns.md`, `references/nextjs-patterns.md`, `references/anti-patterns.md`.
- **[`postgres`](../skills/postgres.md)** — PostgreSQL / SQLAlchemy / Alembic best practices for models, migrations, and queries.

---

## 1. Tech stack (locked)

| Layer | Choice | Notes |
|---|---|---|
| Backend | **Python 3.11+, FastAPI** | Async API; Pydantic v2 for schemas/validation |
| ORM / migrations | **SQLAlchemy 2.x (async) + Alembic** | Parameterized queries only (spec-forge-security + postgres skills) |
| Database | **PostgreSQL** | Single store to start; `pgvector` extension for embeddings |
| Vector search | **pgvector** | Keeps RAG DB-first; no separate vector DB now |
| File storage | **DB-first, behind a `StorageBackend` interface** | Bytes in Postgres now; swap to **Azure Blob** later without touching callers |
| Background jobs | **Celery** (broker + result backend = **Redis**) | Ingestion, generation, staleness recompute, exports, analytics; **Celery Beat** for scheduled recompute |
| Cache / rate-limit | **Redis** | Rate-limit counters (spec-forge-security skill: login 5/min, reset 3/hr) |
| Auth | **JWT (HS256), passlib[bcrypt]** | Per spec-forge-security skill exactly |
| Frontend | **Next.js (App Router) + TypeScript** | Per spec-forge-security skill (Next.js + `nextjs-patterns.md`); server actions/route handlers for API proxy; **TanStack Query** for server state; access token in memory + refresh token in httpOnly cookie; CSRF via SameSite + double-submit |
| Design system | **CSS variables / design tokens** | BR-M0-005; single token source |
| LLM / AI | **Provider abstraction** (BR-M4-010) | Pluggable; model routing + governed prompt/skill versions; default provider configurable |
| Deploy | **Railway / Vercel** now | Azure later (aligns with Azure Blob migration) |

**Deferred-but-planned migration:** storage `postgres → azure-blob`. Everything reads/writes through `StorageBackend`; only the file *bytes* location is abstracted — file **metadata always lives in Postgres**.

---

## 2. Repository structure (monorepo)

```
SpecForge/
  backend/
    app/
      main.py                # FastAPI app factory, middleware wiring
      core/                  # config, security (JWT/bcrypt), rbac, audit, logging, errors
      api/                   # routers (versioned, e.g. /api/...)
      models/                # SQLAlchemy models
      schemas/               # Pydantic request/response models
      services/              # business logic (one module per domain)
      storage/               # StorageBackend interface + postgres/azure impls
      llm/                   # provider abstraction, RAG retrieval, prompt templates
      workers/               # Celery app + tasks (ingest, generate, stale, export)
    alembic/                 # migrations
    tests/                   # pytest (unit + integration)
    pyproject.toml / requirements.txt   # pinned versions
  frontend/                  # Next.js (App Router) + TypeScript
    app/                     # routes + layouts (App Router)
    components/              # shared UI + design-token primitives
    features/                # one folder per module/feature area
    lib/                     # api client, auth (token split), query hooks
    middleware.ts            # route protection / server-side session checks
    tests/                   # component + e2e (Playwright)
  infra/                     # docker-compose (postgres+redis), env templates, CI
  .claude/prd/               # requirements (source of truth)
  .claude/plans/             # these planning docs
```

---

## 3. Cross-cutting architecture standards

These are implemented once in **E0 (Foundation)** and reused by every later milestone. Each later deep plan must *consume*, not reinvent, them.

### 3.1 Authentication & authorization (BR-M0-008…012, spec-forge-security skill)
- JWT HS256, secret from `JWT_SECRET`; 1h access / 7d refresh; refresh rotation; refresh tokens stored **hashed** and revocable.
- Access token in memory (frontend), refresh token in **httpOnly Secure cookie**. Never localStorage.
- `require_role()` / permission dependency on **every** endpoint except `/api/auth/login`, `/api/auth/refresh`, `/api/health`.
- **Server-side is the only authority**; frontend role checks are UX-only. Combine role checks with **resource-level** (ownership/membership) checks.
- Status discipline: **401** missing/invalid token, **403** authn-but-unauthorized, **404** when existence would leak.
- JWT decode **pins the algorithm** (`algorithms=["HS256"]`) — never trust the token header (prevents `alg:none`/confusion).
- Refresh-token **kill-switch**: maintain a JTI blocklist (Redis) so tokens can be revoked before expiry (logout, password/role change).
- **CSRF defense** on cookie-authenticated, state-changing routes: SameSite cookies + double-submit token (or strict origin check).
- **Account lockout / backoff** after repeated failed logins; identical generic responses to prevent **account enumeration**.
- Cookies set `HttpOnly`, `Secure`, `SameSite=Lax` (or `Strict` where appropriate).
- Every protected endpoint uses `Depends(require_user)` / `require_role(...)` — no ad-hoc token parsing in handlers.

### 3.2 Audit logging (BR-M0-007)
- Append-only `audit_event` store; events emitted **server-side at the point of action**.
- Every material action records: actor, timestamp, project, document/app, action, source/target version, affected sections. AI events add: skill version, model, prompt-template version, source refs, output decision state.
- A reusable `audit.emit(...)` helper; services call it — no endpoint silently mutates without an audit event.

### 3.3 Versioning & snapshots (BR-M0-006)
- Generic, document-key-addressable version service usable by BRD/FS/NFR/RU/Trace and any future module.
- Snapshots are **immutable** (storage-enforced, non-restorable); non-snapshot versions support non-destructive restore (new current version) — BR-M5-006/007.

### 3.4 File storage abstraction (DB-first → Azure)
- `StorageBackend` interface: `put(stream, metadata) -> file_id`, `get(file_id) -> stream`, `delete(file_id)`, `url(file_id, ttl)`.
- `PostgresStorageBackend` (now): bytes in a `file_blob` table (chunked for large files); metadata in `file` table.
- `AzureBlobStorageBackend` (later): bytes in a container; same metadata rows. Switch via `STORAGE_BACKEND` env var.
- Uploads validate **content type by magic bytes**, reject path-traversal names, enforce size limits (spec-forge-security skill).

### 3.5 Background jobs (Celery)
- Task families: **ingestion** (parse/OCR/extract/embed), **generation** (BRD/FS/NFR/section-regen), **staleness recompute** (dependency graph), **export jobs**, **analytics/triage recompute**.
- Conventions: idempotent tasks keyed by a request ID; job status persisted (queued/running/completed/failed) and surfaced to UI; failures return actionable errors; results audited where material.
- Celery Beat for scheduled recompute (staleness, portfolio triage freshness).

### 3.6 Provenance, traceability & staleness (cross-module, mainly M2/M4)
- Every generated claim links to a **source span**, an **app-brain fact**, or a tracked **assumption** (no orphan claims).
- Trace graph: BR → FR → design → test → NFR, stored as edges; coverage and gaps are queries over it.
- Staleness = downstream invalidation computed at **section level** when an upstream section changes; drives review + regen gating.

### 3.7 Data classification & PII (BR-M4-011)
- PII detection at ingestion; classification tags on sources/facts; permission-filtered retrieval so restricted content never reaches a client surface, citation, export, or LLM prompt for an unauthorized user; security decisions audited.

### 3.8 API & error conventions
- REST under `/api`; consistent error envelope; pagination + filtering on list endpoints; idempotency keys on job-creating POSTs.
- CORS whitelist `FRONTEND_URL`; security headers (`X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, CSP on frontend); HTTPS-only with Secure cookies.

### 3.9 Design tokens (BR-M0-005)
- One token catalogue (color/typography/spacing/shadow/status/AI/app-brain/component-state). AI output, human edits, and app-brain grounding are **visually distinct**. Runtime theme overrides may not alter compliance-bearing semantic tokens.

### 3.10 Testing strategy
- Backend: **pytest** unit + integration against a real Postgres (test DB), factory fixtures, no mocked DB for integration paths.
- Frontend: component tests + **Playwright** e2e; UI stories verified in-browser (the PRD acceptance criterion).
- Each user story's acceptance criteria become test cases; security checklist (below) runs in CI.

### 3.11 Observability
- Structured logging (no secrets/PII — spec-forge-security skill), request IDs, Celery task logging, basic metrics; detailed errors logged server-side, generic messages to clients.

---

## 4. Configuration & secrets

Env vars (local `.env`, gitignored; platform secrets in prod):

```
JWT_SECRET=                 # ≥256-bit; rotatable (validate multiple during transition)
FRONTEND_URL=               # CORS whitelist
DATABASE_URL=               # Postgres
REDIS_URL=                  # cache + rate-limit
CELERY_BROKER_URL=          # Redis
CELERY_RESULT_BACKEND=      # Redis
STORAGE_BACKEND=postgres    # postgres | azure-blob
AZURE_STORAGE_CONNECTION_STRING=   # later
LLM_PROVIDER= / LLM_API_KEY=       # provider abstraction; never in client state
```

Secrets never in code or client-side state; dependencies pinned; `pip-audit`/`safety` before release (spec-forge-security skill §Dependency Security).

---

## 5. Environments & seed data
- **Local** (docker-compose: postgres + redis), **dev/staging/prod** (Railway/Vercel now).
- Alembic migrations gate every deploy.
- **Seed data:** seeded test/demo users across the 7 roles that go through the *same* auth + RBAC path (US-M0-009-4), visually flagged as non-production; a seeded app brain (PayHub) and a sample project to exercise vertical slices.

---

## 6. Definition of Done (per story / epic)
- All acceptance criteria for the covered user stories pass (mapped to tests).
- Security checklist passes (below). Audit events emitted for material actions. RBAC enforced server-side.
- Migrations written; seed/fixtures updated. Typecheck + lints green. UI verified in-browser for UI stories.
- Deep plan's demo script runs end-to-end.

### Security checklist (from spec-forge-security skill — apply to every backend slice)
- [ ] JWT HS256, `JWT_SECRET` from env; 1h/7d; refresh rotation; hashed refresh tokens.
- [ ] bcrypt cost ≥12; min length 8; no credential leakage; hashes excluded from responses.
- [ ] `require_role()` on every endpoint (except login/refresh/health); resource-level checks; 401/403/404 discipline.
- [ ] CORS whitelisted; rate limits (5/min login, 3/hr reset); request-size limits; security headers; HTTPS/Secure cookies.
- [ ] ORM/parameterized queries only; strict Pydantic validation; upload magic-byte + path-traversal checks.
- [ ] No secrets/PII in logs; generic prod errors; pinned deps + audit.
- [ ] JWT decode pins `algorithms=[...]`; refresh-token JTI blocklist supports revocation; account lockout + enumeration-safe responses.
- [ ] Cookie flags `HttpOnly/Secure/SameSite`; CSRF defense on cookie-auth state-changing routes.
- [ ] No `eval`/`exec`/`shell=True` on user input; no `verify=False` on outbound HTTP.
- [ ] Read the relevant `spec-forge-security/references/*.md` (jwt-auth, fastapi-patterns, nextjs-patterns, anti-patterns) before writing the code.

---

## 7. Open decisions to confirm (not blocking E0)
- LLM provider + embedding model defaults (provider abstraction lets us defer; pgvector dimension depends on embedding model).
- Document parsing/OCR toolchain for ingestion (e.g., unstructured/pypdf + OCR engine).
- Frontend UI-state lib (Context vs Zustand) and component primitives.
- Account lockout/backoff beyond rate limiting; SSO/MFA (currently Non-Goal, see Module 0 PRD).
- pgvector large-corpus performance ceiling before considering a dedicated vector store.
