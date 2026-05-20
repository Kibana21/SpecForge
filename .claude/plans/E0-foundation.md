# E0 — Foundation / Walking Skeleton — Deep Plan

**Goal:** Stand up the spine of SpecForge so a user can log in, land in the app shell, have every request RBAC-enforced and every material action audited, with the version-snapshot, design-token, storage, and background-job infrastructure in place. No feature modules yet — but the cross-cutting machinery every later epic consumes is real and tested.

**Tier-1 decisions:** [`00-foundations-and-decisions.md`](00-foundations-and-decisions.md) · **Roadmap:** [`01-master-roadmap.md`](01-master-roadmap.md) · **Requirements:** [`../prd/prd-module-0-global-architecture.md`](../prd/prd-module-0-global-architecture.md)
**Binding skills:** `spec-forge-security` (auth/RBAC/API security — read `references/jwt-auth.md`, `fastapi-patterns.md`, `nextjs-patterns.md`, `anti-patterns.md`), `postgres` (models/migrations/queries).

**Model guidance:** Implement on **Sonnet** (well-specified work — fast/cheap); escalate to **Opus** for the auth/security core (**T6–T12**), the open questions in §11, and any non-trivial debugging. Switch with `/model`.

---

## Scope boundary for E0
E0 builds **infrastructure + patterns**, exercised end-to-end with **seeded minimal data**. Some Module 0 capabilities can only be *fully* exercised once later epics produce real content; E0 delivers the reusable service + UI and verifies it against seed data, with full verification deferred to the noted epic.

| Built fully in E0 | Built as reusable service/skeleton, full data later |
|---|---|
| Auth (login/refresh/logout), JWT, credentials, API security, RBAC, audit | Version history (real docs in E3+), 10-stage progress (stages populate in E2–E4), design tokens for AI/stale/app-brain states (consumed in E3/E4) |

---

## 1. BRs covered & acceptance mapping

| BR | Title | Key user stories | Verified in E0 by |
|---|---|---|---|
| BR-M0-001 | Single-Page Workbench Shell | US-M0-001-1..4 | e2e nav, unknown→fallback, unauthorized→access-denied, project-context persistence |
| BR-M0-002 | Global Project/Document Context | US-M0-002-1..4 | context API + store tests; context scoping in RBAC integration tests |
| BR-M0-003 | Persistent Navigation Chrome | US-M0-003-1..4 | shell renders sidebar/topbar across routes (seeded stages); component + e2e |
| BR-M0-004 | Responsive Design Scaling (Should) | US-M0-004-1..3 | canvas scaling unit/e2e at sample widths; a11y doc stub |
| BR-M0-005 | Design Token Governance | US-M0-005-1..3 | token catalogue + lint rule: no non-token values on primary surfaces |
| BR-M0-006 | Global Version History Access | US-M0-006-1..4 | version service tests; panel opens from chip on a seeded doc; immutability test |
| BR-M0-007 | Global Auditability | US-M0-007-1..4 | `audit.emit` integration tests; immutability; query API; auth events audited |
| BR-M0-008 | Role-Based Access Control | US-M0-008-1..4 | RBAC dependency tests; filtered list; deny-by-default; 401/403/404 |
| BR-M0-009 | User Authentication & Login | US-M0-009-1..4 | login/logout flow tests; public-route allowlist; seeded test identities |
| BR-M0-010 | Session & Token Mgmt (JWT) | US-M0-010-1..3 | token validation (alg pinned), refresh rotation, JTI revocation, cookie split |
| BR-M0-011 | Password & Credential Security | US-M0-011-1..3 | bcrypt cost, min-length, no-leak, constant-time tests |
| BR-M0-012 | API Security & Backend Integrity | US-M0-012-1..4 | CORS, rate-limit, validation, headers, status-code, upload-guard tests |

---

## 2. Dependencies (what must already exist)
None — E0 is first. External: Postgres (+ `pgvector` extension installed for later), Redis, Python 3.11+, Node 20+. Provided via `infra/docker-compose.yml`.

---

## 3. Data model & migrations (Alembic; follow `postgres` skill)

Initial migration set (E0). Minimal `project`/`app` rows exist only to exercise context + RBAC; **E2/E1 extend them**.

- **user** — `id` (uuid pk), `email` (unique, citext), `display_name`, `role` (enum: business_analyst, product_owner, solution_architect, app_owner, qa_lead, compliance_reviewer, platform_admin), `password_hash`, `status` (active/locked/disabled), `is_test` (bool), `failed_login_count`, `locked_until`, `created_at`, `updated_at`.
- **refresh_token** — `jti` (uuid pk), `user_id` (fk), `token_hash`, `issued_at`, `expires_at`, `revoked_at`, `replaced_by_jti`, `user_agent`, `ip`. (Hashed + revocable; rotation chain.)
- **audit_event** — `id` (bigint pk), `actor_id`, `ts`, `project_id`, `document_key`, `app_key`, `action`, `source_version`, `target_version`, `affected_sections` (jsonb), `ai_meta` (jsonb: skill_version/model/prompt_template_version/source_refs/decision_state), `ip`, `user_agent`, `correlation_id`. **Append-only** (no UPDATE/DELETE grants for app role).
- **version_snapshot** — `id` (uuid pk), `document_key`, `version_no`, `actor_id`, `created_at`, `change_note`, `changed_sections` (jsonb), `change_count`, `generation_type` (ai/human/regeneration/restore/import), `is_immutable` (bool), `content_ref`. Unique `(document_key, version_no)`.
- **project** (minimal) — `id`, `name`, `business_unit`, `owner_id`, `created_at`. **project_member** — `(project_id, user_id, role)` for resource-level checks.
- **app** (minimal) — `app_key` (pk), `name`, `owner_id`, `onboarded` (bool). **app_owner/delegate** — `(app_key, user_id, kind)`.
- **file** + **file_blob** — storage abstraction backing tables: `file`(id, name, content_type, size, sha256, classification, created_by, created_at); `file_blob`(file_id, chunk_no, bytes). (Built now; uploads consume it in E1/E2.)

JTI **access-token blocklist** lives in Redis (set with TTL = token lifetime), not a table.

---

## 4. Backend — API contracts

All under `/api`. Auth via `Depends(require_user)` / `require_role(...)` except the public allowlist. Errors via central middleware (generic client message, detailed server log). Status discipline 401/403/404 per `spec-forge-security`.

**Public (no token):** `/api/auth/login`, `/api/auth/refresh`, `/api/health`.

| Method | Path | Purpose | Codes | Notes |
|---|---|---|---|---|
| POST | `/api/auth/login` | Verify creds → access token (body) + refresh (httpOnly cookie) | 200/401/429 | rate-limit 5/min/IP+user; enumeration-safe; lockout on repeated fail |
| POST | `/api/auth/refresh` | Rotate: new access+refresh, revoke old jti | 200/401 | reads refresh cookie; CSRF double-submit |
| POST | `/api/auth/logout` | Revoke refresh jti, blocklist access jti, clear cookie | 204 | audited |
| GET | `/api/auth/me` | Current principal (role, display_name) | 200/401 | response schema excludes hash |
| POST | `/api/auth/password-reset` | Initiate reset | 202 | rate-limit 3/hr; enumeration-safe; audited |
| GET | `/api/health` | Liveness | 200 | public |
| GET | `/api/context/resolve` | route+user → {allowed\|fallback\|access_denied} + context | 200 | shared authority for routing + RBAC (BR-M0-001/002) |
| GET | `/api/projects` | RBAC-filtered minimal project list | 200/401 | proves authorized-only visibility (US-M0-008-1) |
| GET | `/api/audit` | Query audit (filter actor/project/action/time) | 200/401/403 | compliance/admin roles only |
| GET | `/api/documents/{document_key}/versions` | Version timeline | 200/401/403/404 | BR-M0-006; RBAC-scoped |
| GET | `/api/documents/{document_key}/versions/{v}` | Read-only snapshot preview | 200/.. | immutable snapshots flagged |
| GET | `/api/documents/{document_key}/versions/compare?a=&b=` | Diff payload | 200/.. | additions/deletions marked |

**Cross-cutting middleware/deps:** settings (pydantic-settings, fail-loud on missing `JWT_SECRET`), CORS (`FRONTEND_URL` only), security headers, request-size limit (10MB default), `require_user`/`require_role`, `audit` dependency, rate limiter (slowapi + Redis), error handler, correlation-id.

---

## 5. Background jobs (Celery + Redis)
- Wire Celery app + worker + **Beat**; broker/result = Redis.
- `tasks.ping` — health task to prove the pipeline (used in CI smoke).
- `tasks.purge_expired_refresh_tokens` (Beat, daily) — revoke/delete expired refresh tokens.
- Job-status persistence pattern + conventions established here for later epics (ingestion/generation/export).

---

## 6. Frontend (Next.js App Router + TypeScript)
Follow `spec-forge-security/references/nextjs-patterns.md` for token storage, CSRF, cookies, server-side session checks.

- **Routes/layouts:** `/login`, `/` (dashboard shell placeholder), `/access-denied`, `not-found`; root layout = app shell.
- **App shell (BR-M0-003):** persistent **sidebar** (workspace links, current-project link, 10-stage progress [seeded], org-library links, user identity) + **topbar** (breadcrumbs from route, global search, notifications, settings, New project).
- **Global context store (BR-M0-002):** active project/SDLC stage/document key/review/app/version-panel; one authoritative source (Context + TanStack Query).
- **Design tokens (BR-M0-005):** CSS-variable catalogue (color/typography/spacing/shadow/status/AI/app-brain/component-state); status semantics; AI vs human vs app-brain visual distinction; lint/test guard against non-token values on primary surfaces.
- **Auth (BR-M0-009/010/012):** login form; access token in **memory**; refresh in **httpOnly cookie**; fetch wrapper attaches access token + auto-refresh on 401; `middleware.ts` route protection; CSRF double-submit; logout.
- **Routing safety (BR-M0-001):** unknown → fallback view; unauthorized → access-denied (no restricted data); preserve active project across navigation.
- **Version history panel (BR-M0-006):** opens from a consistent chip/button; timeline + preview/compare against seeded snapshot; immutable snapshots non-restorable.
- **Responsive scaling (BR-M0-004):** scale 1440px canvas to viewport; recompute on resize; min-viewport/zoom doc stub.

---

## 7. Ordered work breakdown (tasks → BR/US)

**Phase 1 — Scaffolding**
- T1. Monorepo + `infra/docker-compose.yml` (postgres+pgvector, redis), env templates, CI pipeline. → infra
- T2. FastAPI app factory, settings module (fail-loud secrets), error middleware, correlation-id, `/api/health`. → BR-M0-012
- T3. SQLAlchemy async + Alembic baseline; `postgres`-skill conventions. → schema
- T4. Security middleware: CORS allowlist, security headers, request-size limit. → BR-M0-012 (US-M0-012-1/3/4)
- T5. Celery + Beat wiring; `tasks.ping`. → §5

**Phase 2 — AuthN/Z core** (read `jwt-auth.md` + `fastapi-patterns.md` first)
- T6. `user` + credentials: bcrypt (cost ≥12), min-length, constant-time, hash never in responses. → BR-M0-011 (US-M0-011-1..3)
- T7. JWT issue/validate: HS256, **algorithm pinned**, payload `sub/role/exp/iat/jti`, 1h access. → BR-M0-010 (US-M0-010-1)
- T8. Refresh tokens: `refresh_token` table (hashed), rotation, 7d expiry, JTI revocation + Redis access blocklist. → BR-M0-010 (US-M0-010-2)
- T9. `/api/auth/login|refresh|logout|me`: enumeration-safe, lockout, audited; cookie flags `HttpOnly/Secure/SameSite`. → BR-M0-009 (US-M0-009-1..3), BR-M0-010 (US-M0-010-3)
- T10. Rate limiting (slowapi+Redis): login 5/min, reset 3/hr. → BR-M0-012 (US-M0-012-2)
- T11. `require_user`/`require_role` deps; role→permission policy; resource-level (project_member/app_owner) checks; deny-by-default; 401/403/404. → BR-M0-008 (US-M0-008-1..4), BR-M0-001 (US-M0-001-3)
- T12. `/api/context/resolve` (shared routing+RBAC authority) + minimal `project`/`app` + `/api/projects` filtered list. → BR-M0-001/002 (US-M0-002-1..4, US-M0-008-1)

**Phase 3 — Audit & Versioning**
- T13. `audit_event` (append-only) + `audit.emit` helper; wire into auth + RBAC-denial + (later) all mutations; `/api/audit` query (admin/compliance). → BR-M0-007 (US-M0-007-1..4)
- T14. `version_snapshot` model + version service (timeline/preview/compare, immutability); `/api/documents/{key}/versions*`; seed one doc. → BR-M0-006 (US-M0-006-1..4)
- T15. Storage abstraction: `StorageBackend` + `PostgresStorageBackend` (`file`/`file_blob`), magic-byte + path-traversal guards. → BR-M0-012 (US-M0-012-3), foundations §3.4

**Phase 4 — Frontend shell** (read `nextjs-patterns.md` first)
- T16. Next.js app, design-token system, root layout. → BR-M0-005 (US-M0-005-1..3)
- T17. Auth UI + token-split + fetch wrapper + `middleware.ts` + CSRF + logout. → BR-M0-009/010/012
- T18. Sidebar/topbar chrome + breadcrumbs + global entry points (seeded 10-stage). → BR-M0-003 (US-M0-003-1..4)
- T19. Global context provider; project-context persistence across nav. → BR-M0-002 (US-M0-002-*), BR-M0-001 (US-M0-001-4)
- T20. Routing: fallback + access-denied views; multi-entry navigation. → BR-M0-001 (US-M0-001-1..3)
- T21. Version-history panel UI (from chip; preview/compare; immutable). → BR-M0-006
- T22. Responsive canvas scaling + min-viewport/zoom doc stub. → BR-M0-004 (US-M0-004-1..3)

**Phase 5 — Seed & harden**
- T23. Seed 7-role test users (`is_test`, visually flagged per US-M0-009-4), seeded project/app/version snapshot.
- T24. Run full security checklist; CI green; demo script.

---

## 8. Security checklist (E0 is where most of this lands — from `spec-forge-security`)
- [ ] Secrets from env only; fail-loud on missing `JWT_SECRET`. No hardcoded secrets.
- [ ] JWT HS256 **algorithm pinned**; payload limited to `sub/role/exp/iat/jti`; 1h/7d; refresh rotation; refresh hashed; JTI blocklist revocation.
- [ ] bcrypt ≥12; min length 8; constant-time verify; hashes excluded from all response schemas; no credential logging.
- [ ] `require_user`/`require_role` on every protected endpoint (allowlist: login/refresh/health); resource-level checks; deny-by-default.
- [ ] 401 (missing/invalid), 403 (authn-no-perm), 404 (existence-leak) discipline; generic client errors; no stack traces to client.
- [ ] CORS = `FRONTEND_URL` only; rate limits (5/min login, 3/hr reset); request-size limit; security headers; HTTPS/Secure cookies; `SameSite`; CSRF double-submit.
- [ ] ORM/parameterized queries only; strict Pydantic validation; upload magic-byte + path-traversal guards.
- [ ] Account lockout + enumeration-safe responses; auth events audited (login success/fail, logout, refresh, denial) with `user_id/ip/ua/correlation_id`.
- [ ] No secrets/PII in logs; no `eval`/`exec`/`shell=True`; no `verify=False`; deps pinned + `pip-audit`.

---

## 9. Test plan (acceptance criteria → tests)
- **Unit:** bcrypt cost/verify + min-length (M0-011); JWT issue/validate incl. **rejects unpinned alg & tampered token** (M0-010); RBAC policy matrix (M0-008); `audit.emit` shape (M0-007); version immutability (M0-006); canvas scaling math (M0-004); token-non-leak in response schemas (M0-011).
- **Integration (real Postgres+Redis):** login→refresh(rotation)→logout(revocation) incl. reused-old-refresh rejected (M0-009/010); rate-limit 429 (M0-012); RBAC filtered list + 401/403/404 (M0-008); deny-by-default on unknown permission; audit row written for auth + denial, append-only enforced (M0-007); context-scoped reads can't cross projects (M0-002); version timeline/preview/compare RBAC-scoped (M0-006).
- **e2e (Playwright):** log in as each seeded role → shell renders chrome (M0-003); unknown route → fallback, unauthorized route → access-denied with no data leak (M0-001/008); project context persists across nav (M0-001/002); open version history from chip (M0-006); resize keeps app in viewport (M0-004); logout invalidates session (M0-009). UI stories verified in-browser.

---

## 10. Done criteria + demo script
**Done:** all acceptance rows in §1 pass; §8 checklist green; CI (lint, typecheck, pytest, Playwright, security checks) green; migrations + seed reproducible.
**Demo:** (1) `docker-compose up`; (2) log in as `analyst@…` test user → shell with sidebar/topbar + identity; (3) try a route reserved for `platform_admin` → access-denied (no data); (4) navigate dashboard↔(seeded) project → active project preserved; (5) open version history on the seeded doc → timeline + preview/compare, snapshot non-restorable; (6) hit login 6× fast → 429 + lockout; (7) show audit log entries for the logins/denials; (8) log out → protected API returns 401; (9) resize browser → layout stays within viewport.

---

## 11. Risks & open questions
- **JWT library:** `pyjwt` vs `python-jose` — pick one; ensure algorithm pinning either way (consult `anti-patterns.md`).
- **Access-token kill-switch scope:** rely on 1h expiry alone, or also Redis-blocklist access JTIs on logout/role-change? (Plan: blocklist on logout/role-change.)
- **Role taxonomy granularity:** are roles global, per-project, or per-business-unit? Affects `require_role` + membership model (also a Module 0 PRD open question).
- **How much of `project`/`app` to stub** without pre-empting E1/E2 schemas — keep columns minimal, additive migrations later.
- **Design-token guard:** lint rule vs visual test for "no non-token values on primary surfaces" — choose enforcement mechanism.
- **CSRF approach** with token-split auth — confirm SameSite=Lax + double-submit is sufficient for our cross-site needs (see `nextjs-patterns.md`).
