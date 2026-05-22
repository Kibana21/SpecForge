# Audit Log Module — Deep Plan

## Context

**Why now.** Every consequential action in SpecForge already writes an immutable `AuditEvent` (auth, project/app lifecycle, source intake, the RU human-validation gate, AI generation). But **nothing surfaces it** — there's no `/api/audit` endpoint and no `/audit` page. Admins and compliance reviewers (the only roles with access) currently have a black box. This module builds the **read/query/UI layer** over data that's already being captured.

**What admins/compliance actually need (and what this solves):**
- **Accountability** — "who did what, when, to which artifact?" (the core trail).
- **Security investigation** — failed logins, account lockouts, **refresh-token-reuse alerts**, malware blocks. These already emit; admins need to *see* them.
- **Compliance proof** — that a human **validated the Requirement Understanding** before AI generation (`understanding.validated`), and **AI-vs-human attribution** (which actions were AI-driven, what model/skill ran — from `ai_meta`).
- **Forensic tracing** — follow one request chain via `correlation_id`.
- **Incident review / external audit** — filter to a window/actor/event and **export CSV** as evidence.

**Outcome.** A clear, crisp, **searchable + filterable + paginated** Audit Log at `/audit` with security KPI tiles up top, human-readable event labels with severity colors, a row-detail drawer (IP/user-agent/metadata/correlation), and filtered CSV export — gated to `platform_admin` + `compliance_reviewer`.

**No migration required** — the `AuditEvent` table and its indexes (`event`, `actor_id`, `project_id`, `ts`) already exist. This is read-only over existing data.

---

## What already exists vs. what's missing

**Exists (reuse, do not rebuild):**
- `app/models/audit.py::AuditEvent` — columns: `id`, `event`, `actor_id` (UUID-as-string), `email_hash`, `project_id` (UUID-as-string), `document_key`, `app_key`, `action`, `source_version`, `target_version`, `affected_sections` (JSONB), `ai_meta` (JSONB metadata blob), `ip`, `user_agent`, `correlation_id`, `ts`. Indexed on event/actor_id/project_id/ts. **Append-only.**
- `app/core/audit.py::emit(...)` — async; `metadata` kwarg → `ai_meta`; caller commits.
- ~20 emitted events across `auth.py`, `projects.py`, `apps.py`, `documents.py`, `understanding/orchestrator.py`.
- RBAC: `require_role(*roles)` accepts multiple roles; `app/api/context.py::_ROLE_ROUTE_PREFIXES` + `AppShell.tsx` already gate `/audit` to compliance_reviewer + platform_admin.
- Pagination/envelope: `ok(items, meta={total, limit, offset})`, `limit = min(limit, 100)`, order `ts DESC` (see `app/api/apps.py::list_apps`).
- Frontend reuse: `apiFetchEnvelope` + `useProjects` SWR pattern, `PortfolioTable.tsx` styling, `StatTile.tsx`, `Badge` variants, `Dialog`, `Input`, `Select`, `ToggleGroup`, debounced-search in `app/page.tsx`.

**Missing (build):** `GET /api/audit` (+ summary + CSV), an event catalog, the `/audit` page + table + filters + detail drawer + a reusable Pagination control, types/hooks/api client.

---

## Design

### 1. Event catalog (`app/services/audit/catalog.py`)
Authoritative `event → {label, category, severity}` map. API attaches label/category/severity per row; the category filter is derived here. Unknown events fall back to `{humanized, other, neutral}`.

Categories: auth · security · data · destructive · ai · compliance. Filter tabs: **All · Security (incl. destructive) · Auth · Data · AI · Compliance**. Severity → Badge variant: info/warning/danger/success/ai/neutral.

### 2. Backend (`app/api/audit.py`, mounted `prefix="/api"`)
Gate every route with `Depends(require_role("platform_admin", "compliance_reviewer"))` → 403 otherwise.
- **`GET /api/audit`** — list newest-first. Params: `q` (ILIKE across event/action/document_key/`ai_meta::text` + matched actor name/email), `category`, `event`, `actor_id`, `project_id`, `app_key`, `start`/`end` (ts range), `limit`≤100, `offset`. Returns `ok(items, meta={total,limit,offset})`; each item = `AuditEventRead` (+ resolved actor_name/email/role). Actor resolution: batch `select(User).where(User.id.in_(page actor uuids))` → map in Python; null actor → "Unknown".
- **`GET /api/audit/summary`** — KPI counts: events today, failed logins 24h, lockouts 24h, token-reuse 7d, deletions 7d, AI actions today.
- **`GET /api/audit/export.csv`** — same filters, capped ~10k rows, `StreamingResponse` text/csv; emits `audit.exported`; rate-limited (`@limiter.limit`, needs `request: Request`).

### 3. Frontend
- `app/audit/page.tsx` — AppShell + hero + KPI tiles (`StatTile`, danger tone for failed-logins/lockouts/reuse) + toolbar (debounced search + category `ToggleGroup` + event `Select` + date-range inputs + Export CSV) + `AuditTable` + `Pagination` + `AuditDetailDialog`.
- `app/components/audit/AuditTable.tsx` — Time · Actor · Event (severity Badge) · Target · IP; row click → detail.
- `app/components/audit/AuditDetailDialog.tsx` — full event incl. pretty-printed metadata/affected_sections + correlation_id "show related".
- `app/components/ui/Pagination.tsx` *(new reusable)* — `{total, limit, offset, onChange}`, "Showing X–Y of Z" + Prev/Next.
- `lib/audit.ts` (severity/category maps), `lib/types.ts` (`AuditEventRead`/`AuditFilters`/`AuditSummary`), `lib/api.ts` (`api.audit.*` + `_auditQuery`; **CSV via `authedFetch`→blob→download**, not `<a href>`), `lib/hooks/useAudit.ts`.

---

## Files
**Create (backend):** `app/api/audit.py`, `app/services/audit/{__init__,catalog}.py`, `app/schemas/audit.py`, `tests/test_audit_api.py`. **Modify:** `app/main.py` (register router).
**Create (frontend):** `app/audit/page.tsx`, `app/components/audit/{AuditTable,AuditDetailDialog}.tsx`, `app/components/ui/Pagination.tsx`, `lib/audit.ts`, `lib/hooks/useAudit.ts`. **Modify:** `lib/types.ts`, `lib/api.ts`.

## Security checklist
- RBAC 403 unless platform_admin/compliance_reviewer · read-only (append-only integrity) · export capped + rate-limited + self-audited (`audit.exported`) · no secret leakage · null-actor safe · clamp limit / validate dates.

## Test plan
- Backend `tests/test_audit_api.py`: RBAC (allowed 200 / denied 403), pagination meta + ts-desc, computed category/severity/label, actor resolution (+Unknown), filters (event/category/actor/project/date/q), summary counts, CSV (text/csv + header + `audit.exported` written).
- Frontend: `tsc` clean; dev-browser QA (KPI tiles, filters, pagination, detail drawer, CSV download).

## Verification (end-to-end)
1. Ensure events exist (log in/out, create+delete an app, validate an RU, or run `scripts/seed_projects.py`).
2. `cd backend && ./.venv/bin/python -m pytest tests/test_audit_api.py -q`.
3. Log in as `admin@specforge.test` → Audit Log → KPI tiles, filter Security, search actor, page, open detail, Export CSV. Confirm non-admin → 403 + no nav entry.

## Out of scope / future
- Per-artifact Activity tabs (endpoint already accepts `project_id`/`app_key`). · Trigram/GIN index on `ai_meta::text` if search slows. · Retention/rotation; SIEM streaming; `audit.viewed`.
