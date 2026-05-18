# SpecForge AI — Phased Implementation Plan

> **Note on plan location:** Plan mode requires writing here at `/Users/kartik/.claude/plans/`. After approval (ExitPlanMode), this file should be copied to the project at `/Users/kartik/Documents/Work/Projects/SpecForge/SpecForge/.claude/plans/specforge-implementation-plan.md` as you requested.

---

## 1. Context

SpecForge AI is a guided, enterprise-grade portal that ingests messy requirements documents (PDF/DOCX/TXT) from Business Analysts and Engineering Leads, and transforms them through a deterministic AI pipeline into versioned, structured, editable artifacts: Functional Spec, Technical Spec, Jira-ready User Stories, Open Questions, and Review Comments. It is explicitly **not a chatbot** — the value is the workflow scaffolding around the LLM, plus the reusable "Skill Engine" that encapsulates each AI capability (system instruction + Jinja2 template + JSON Schema + parser).

The project is currently **greenfield** — only `README.md` and `.claude/prd/prd-specforge-ai.md` exist. Everything (backend, frontend, DB, skills, infra) must be built from scratch.

The MVP goal: a working local-Docker deployment where a user can create a project, drag-drop documents, see extracted requirements with confidence + source-reference badges, see gap questions surfaced (never hallucinated), trigger sequential generation of all four spec types, edit them inline with auto-save, and export Markdown. The system must run end-to-end with **mock LLM responses** when `GEMINI_API_KEY` is absent, so every layer is testable independently of vendor availability.

**Confirmed constraints (user input):**
- Build strategy: **phased by layer** (A→E below)
- PRD open questions resolved with defaults: free-text gap answers fed into spec regen; 20 MB/file cap; latest-version-only UI (versions retained in DB); reviewer is manual final step of "Generate Specs"; no dashboard tagging/search for MVP
- Out of scope: DOCX export, Azure Blob, Claude/Azure OpenAI providers, auth, multi-user, real-time collab, Slack/Jira integration

---

## 1A. Engineering Practices — mandatory skill compliance

Two project-level skill files in `.claude/skills/` must be honored throughout implementation. Treat them as binding standards; the phase deliverables below reference them.

### `.claude/skills/postgres.md` — applied in Phase B + C + every DB touch

- **UUID v4 PKs** via `sqlalchemy.dialects.postgresql.UUID(as_uuid=True)` — never auto-increment ints. Apply to all 6 tables.
- **`created_at` / `updated_at`** on every table via `server_default=func.now()` + SQLAlchemy `onupdate` event. Built into `TimestampMixin` in `models/base.py`.
- **PG enums** (not free-text TEXT) for fixed value sets: `spec_type`, requirement `category`, `confidence`, gap `category`/`severity`, review `severity`/`category`, document `parse_status`. Declare as `sqlalchemy.Enum(..., name='spec_type', create_type=True)` so Alembic creates the type explicitly. (§3 column types are updated accordingly.)
- **JSONB** only for `spec_versions.content_json` (genuinely flexible). All other fields are typed columns.
- **NOT NULL** every column that should always have a value — explicit at the schema level, not just app-side.
- **Explicit FK ON DELETE** behavior:
  - `ON DELETE CASCADE`: `documents.project_id`, `extracted_requirements.project_id`, `gap_questions.project_id`, `spec_versions.project_id`, `review_comments.project_id`
  - `ON DELETE SET NULL`: `review_comments.spec_version_id`, `extracted_requirements.document_id`
- **Index every FK column** — PG does NOT auto-create FK indexes. Name them `idx_{table}_{column}`. Also add the composite indexes in §3.
- **Soft delete via `deleted_at`** on `projects`; every list query must filter `WHERE deleted_at IS NULL`.
- **Connection pool** in `db.py`: `pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=1800, pool_pre_ping=True`. Use `NullPool` for pytest.
- **Async sessions only** — `AsyncSession` via `async with`; SQLAlchemy 2.0 `select()` API (no legacy `session.query()`).
- **Eager-load** relationships you'll iterate (`selectinload(Project.documents)` etc.). Forbidden: lazy-load in a loop.
- **Pagination** — list endpoints `.limit()` / `.offset()` with default limit 50.
- **Counts** via `func.count()`, not `len(list(...))`.
- **Transactions** — wrap the spec-generation flow (allocating `version_number`) in `async with session.begin()` + `SELECT … FOR UPDATE` on the project row.
- **Alembic discipline** — one migration per logical change, descriptive names (`0001_initial.py`, `0002_add_resolution_text_to_gaps.py`); always write both `upgrade()` and `downgrade()`; `alembic check` before commit; never edit applied migrations; for adding `NOT NULL` to existing data: add nullable → backfill → alter to NOT NULL in a separate migration.
- **Check constraints** at the DB level where simple: `CHECK (size_bytes > 0)`, `CHECK (version_number > 0)`; defense in depth alongside Pydantic.
- **`statement_timeout`** set on the DB role (30s) so a runaway LLM-fed query can't hang the pool.

### `.claude/skills/security.md` — applied in Phase A + C; auth-specific parts deferred

The security skill assumes JWT/RBAC/password auth is in scope. The PRD removes auth from MVP non-goals, so **JWT, password hashing, refresh tokens, and RBAC are deferred** (documented in Risks §11). Apply everything else now:

- **Input validation** — every request body / query param goes through a Pydantic schema with strict types (`StrictStr`, `conint(ge=1)`, etc.). No raw user input into SQL, shell, or filesystem paths.
- **SQL injection** — only ORM / parameterized queries; never f-string SQL.
- **CORS whitelist** — exact origins via `CORS_ORIGINS` env (default `http://localhost:3000`). Never `["*"]`.
- **Request size limits** — `MAX_UPLOAD_MB=20` enforced in the upload endpoint (return **413** over limit). FastAPI body parsing also bounded.
- **File upload hardening** (US-003): validate by **magic bytes** (use `python-magic` or `filetype` lib), not just extension; sanitize filename for path traversal (`..`, absolute paths, NUL bytes); store under a **server-generated random filename** (`{uuid4}.{ext}`) at `uploads/{project_id}/`; keep original filename in `documents.filename` for display.
- **Security headers middleware** — add `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: no-referrer` via FastAPI middleware in `main.py`. Add a minimal `Content-Security-Policy` on the Next.js side (default-src self; connect-src self http://localhost:8000).
- **Error sanitization** — production errors return envelope `{code, message}` only; full stack trace + request ID logged server-side (Phase E hardening).
- **Secrets management** — `GEMINI_API_KEY`, `DATABASE_URL` in `.env` (gitignored). Per PRD FR-8, the frontend never sees the key; all LLM calls are server-side. `.env` template lives at `.env.example`.
- **Dependency pinning** — `requirements.txt` pins exact versions (`fastapi==0.115.x`, etc.). Run `pip-audit` in CI / before release. Keep security-critical libs current (`pydantic`, `sqlalchemy`, `pymupdf`, `python-docx`, `google-generativeai`, `cryptography`).
- **Rate limiting** — `slowapi` middleware on LLM-triggering endpoints (`POST /extract`, `/detect-gaps`, `/specs/*`, `/review`) to bound cost. Default 30 req/min/IP. Cheap insurance against runaway loops or key leakage.
- **No PII / token logging** — log skill name + latency + status code, never document content or LLM prompts/responses at INFO level (DEBUG only, with redaction).

### Cross-cutting

- The 6 skill `instruction.md` files should themselves include guard rails ("never invent credentials", "never echo prompt back as output", "JSON only").
- The deferred auth gap is real, not silent — when added in v2, every endpoint except `/healthz` requires `Depends(require_user())`, and `Project.owner_id` is backfilled (`0010_add_user_id_to_projects.py`: nullable column → backfill → NOT NULL).

---

## 2. Phase Breakdown

### Phase A — Scaffolding (foundations)

**Goal:** Empty-to-runnable. `docker compose up` brings up Postgres; backend and frontend boot with placeholder routes.

**Deliverables (paths to create):**

| Path | Purpose |
|------|---------|
| `/docker-compose.yml` | `postgres:16`, named volume `pgdata`, port 5432 |
| `/.env.example` | Template for all env vars |
| `/.gitignore` (update) | Add `uploads/`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`, `*.env` |
| `/README.md` (update) | Setup steps: prereqs, env, docker, migrations, dev servers |
| `/backend/pyproject.toml` or `requirements.txt` | **Pin exact versions** (`security.md`): fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, pydantic, pydantic-settings, python-multipart, jinja2, jsonschema, google-generativeai, pymupdf, python-docx, aiofiles, pytest, httpx, **slowapi** (rate limiting), **python-magic** or **filetype** (file magic-byte detection), **pip-audit** (dev) |
| `/backend/app/__init__.py` | empty |
| `/backend/app/main.py` | FastAPI app; **CORS whitelist** via `CORS_ORIGINS`; **security headers middleware** (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy); **slowapi rate limiter** registered; `/healthz` |
| `/backend/app/config.py` | `pydantic_settings.BaseSettings` reading `DATABASE_URL`, `LLM_PROVIDER`, `GEMINI_API_KEY`, `UPLOAD_DIR`, `MAX_UPLOAD_MB`, `GEMINI_MODEL`, `CORS_ORIGINS`, `LOG_LEVEL` |
| `/backend/app/db.py` | Async engine with **pool config** (`pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=1800, pool_pre_ping=True`), `AsyncSessionLocal`, `Base = declarative_base()`, `get_db()` dep; `NullPool` switch for pytest |
| `/backend/alembic.ini` + `/backend/alembic/env.py` | Async-aware Alembic |
| `/backend/uploads/.gitkeep` | placeholder |
| `/frontend/package.json` | Next 14, React 18, TS 5, Tailwind 3, @tiptap/react @tiptap/starter-kit, swr, clsx, lucide-react |
| `/frontend/tsconfig.json` | strict, paths `@/*` |
| `/frontend/tailwind.config.ts` | Content paths, dark mode `class` |
| `/frontend/postcss.config.js` | tailwindcss + autoprefixer |
| `/frontend/next.config.mjs` | rewrites `/api/:path*` → `http://localhost:8000/api/:path*` |
| `/frontend/app/layout.tsx` | Root layout, Inter font, global Tailwind import |
| `/frontend/app/globals.css` | Tailwind base/components/utilities + CSS vars (colors) |
| `/frontend/app/page.tsx` | Stub "Dashboard" placeholder |
| `/frontend/.env.example` | `NEXT_PUBLIC_API_BASE=http://localhost:8000` |

**User stories covered:** none directly; unblocks all others.

**Acceptance check:**
- `docker compose up -d postgres` → `psql` connects on 5432
- `uvicorn app.main:app --reload` from `/backend` → `GET /healthz` returns `{"ok": true}`
- `npm run dev` in `/frontend` → loads dashboard placeholder
- `npm run typecheck` passes

---

### Phase B — Data layer, LLM abstraction, Skill Engine core

**Goal:** Persistence and AI plumbing ready. No business endpoints yet.

**Skill compliance focus (`postgres.md`):** UUID v4 PKs, PG enums with `create_type=True`, NOT NULL everywhere applicable, explicit FK `ON DELETE` behavior, FK indexes (PG doesn't auto-create), `TimestampMixin` with `server_default=func.now()`, async sessions, SQLAlchemy 2.0 `select()` API, eager-load via `selectinload`. CHECK constraints on `size_bytes > 0`, `version_number > 0`. Alembic migration 0001 includes `CREATE EXTENSION IF NOT EXISTS pgcrypto` and both `upgrade()` + `downgrade()`.

**Deliverables:**

| Path | Purpose |
|------|---------|
| `/backend/app/models/__init__.py` | Re-export all models |
| `/backend/app/models/base.py` | `TimestampMixin` (`created_at`, `updated_at`), UUID PK helper |
| `/backend/app/models/project.py` | `Project` table |
| `/backend/app/models/document.py` | `Document` table |
| `/backend/app/models/requirement.py` | `ExtractedRequirement` table |
| `/backend/app/models/spec.py` | `SpecVersion` + `SpecType` enum |
| `/backend/app/models/gap.py` | `GapQuestion` table |
| `/backend/app/models/review.py` | `ReviewComment` table |
| `/backend/alembic/versions/0001_initial.py` | All tables + enums |
| `/backend/app/services/llm/base.py` | `LLMProvider` ABC |
| `/backend/app/services/llm/gemini_provider.py` | Gemini implementation |
| `/backend/app/services/llm/mock_provider.py` | Skill-keyed canned JSON |
| `/backend/app/services/llm/__init__.py` | `get_provider()` factory based on env |
| `/backend/app/services/skills/skill_engine.py` | `SkillEngine.run(skill_name, context, provider) -> dict` |
| `/backend/app/services/skills/__init__.py` | Skill registry helpers |
| `/backend/tests/test_skill_engine.py` | Tests against MockProvider |
| `/backend/tests/test_models.py` | Round-trip insert/read |

**User stories covered:** US-001, US-004, US-005.

**Acceptance check:**
- `alembic upgrade head` runs clean on empty DB; all 6 tables present
- `psql -c "\dt"` shows projects, documents, extracted_requirements, spec_versions, gap_questions, review_comments
- `pytest backend/tests/test_skill_engine.py` green — engine loads any skill dir, renders Jinja2, calls MockProvider, validates JSON, retries once on validation failure
- Unset `GEMINI_API_KEY` → engine still works (MockProvider chosen)
- Set `LLM_PROVIDER=gemini` with key → engine routes to GeminiProvider

---

### Phase C — Skill prompts, parsers, API surface, exporter

**Goal:** Full backend executable via curl. All skills present with `instruction.md`, `template.md`, `schema.json`. All endpoints live and persisting.

**Skill compliance focus (`security.md` + `postgres.md`):**
- All endpoints use **Pydantic strict-typed schemas**; envelope-wrapped error responses sanitize internals.
- **File upload (US-003):** magic-byte content-type check (not extension trust), filename sanitized for `..` / NUL / absolute paths, stored as `uploads/{project_id}/{uuid4}.{ext}`, original filename retained in DB.
- **Rate limit** LLM-triggering endpoints (`/extract`, `/detect-gaps`, `/specs/*`, `/review`) at 30 req/min/IP via `slowapi`.
- Project lists filter `deleted_at IS NULL`; all list endpoints paginate (`limit≤100`, default 50).
- `version_number` allocation wrapped in `async with session.begin()` + `SELECT … FOR UPDATE` on the parent project row.
- Eager-load `Project.documents` / `Project.spec_versions` in detail endpoint (no N+1).
- All ORM queries via `select()` — zero string SQL.
- No prompt/response content logged at INFO; only `{skill, provider, attempt, latency_ms, status}`.

**Deliverables — Skill content (6 dirs, 3 files each):**

```
/backend/app/services/skills/requirement_extractor/{instruction.md, template.md, schema.json}
/backend/app/services/skills/gap_detector/{instruction.md, template.md, schema.json}
/backend/app/services/skills/functional_spec/{instruction.md, template.md, schema.json}
/backend/app/services/skills/technical_spec/{instruction.md, template.md, schema.json}
/backend/app/services/skills/user_stories/{instruction.md, template.md, schema.json}
/backend/app/services/skills/reviewer/{instruction.md, template.md, schema.json}
```

**Deliverables — Code:**

| Path | Purpose |
|------|---------|
| `/backend/app/services/documents/parser.py` | `parse(file_path, mime) -> str` for PDF (PyMuPDF) / DOCX (python-docx) / TXT |
| `/backend/app/services/documents/storage.py` | `save(project_id, upload) -> Path`; abstraction for later Azure Blob |
| `/backend/app/services/export/markdown_exporter.py` | `render(spec_version) -> str`; `render_combined(versions) -> str` |
| `/backend/app/schemas/envelope.py` | `Envelope[T]` with `data`, `error`, `meta` |
| `/backend/app/schemas/project.py` | `ProjectCreate`, `ProjectRead`, `ProjectDetail` |
| `/backend/app/schemas/document.py` | `DocumentRead` |
| `/backend/app/schemas/spec.py` | `SpecVersionRead`, `SpecPatch` |
| `/backend/app/schemas/gap.py` | `GapQuestionRead`, `GapResolvePatch` |
| `/backend/app/schemas/review.py` | `ReviewCommentRead`, `ReviewDismissPatch` |
| `/backend/app/api/projects.py` | Project CRUD |
| `/backend/app/api/documents.py` | Upload, list, extract, detect-gaps |
| `/backend/app/api/specs.py` | Generate (4), patch edit, export, review |
| `/backend/app/api/gaps.py` | Gap resolution patch |
| `/backend/app/api/reviews.py` | Review dismiss patch |
| `/backend/app/main.py` (update) | Mount routers, exception handler producing envelope |
| `/backend/tests/test_projects_api.py` | CRUD coverage |
| `/backend/tests/test_documents_api.py` | upload + parse with sample PDF/DOCX/TXT fixtures |
| `/backend/tests/test_specs_api.py` | full sequential generation against MockProvider |
| `/backend/tests/fixtures/sample.{pdf,docx,txt}` | small test files |

**User stories covered:** US-002, US-003, US-006, US-007, US-008, US-009, US-010, US-011, US-019 (backend half).

**Acceptance check (curl smoke):**
```bash
ID=$(curl -s -X POST localhost:8000/api/projects \
   -H 'content-type: application/json' \
   -d '{"name":"X","description":""}' | jq -r .data.id)
curl -F file=@sample.pdf localhost:8000/api/projects/$ID/documents
curl -X POST localhost:8000/api/projects/$ID/extract
curl -X POST localhost:8000/api/projects/$ID/detect-gaps
curl -X POST localhost:8000/api/projects/$ID/specs/functional
curl -X POST localhost:8000/api/projects/$ID/specs/technical
curl -X POST localhost:8000/api/projects/$ID/specs/user-stories
curl -X POST localhost:8000/api/projects/$ID/review
curl 'localhost:8000/api/projects/'$ID'/export/markdown?spec_type=functional' -o out.md
```
All return 200; `/docs` shows full surface; pytest green.

---

### Phase D — Frontend dashboard + workspace

**Goal:** Full UI implementing all UX user stories. Every component built only after invoking `ui-ux-pro-max-skill`; every flow verified with `dev-browser`.

**Deliverables:**

| Path | Purpose |
|------|---------|
| `/frontend/lib/api.ts` | typed fetch wrappers (envelope-aware) |
| `/frontend/lib/types.ts` | mirror of backend Pydantic types |
| `/frontend/lib/hooks/useProjects.ts` | SWR hook |
| `/frontend/lib/hooks/useProject.ts` | SWR hook with detail |
| `/frontend/lib/hooks/useDebouncedSave.ts` | 500 ms debounce for autosave |
| `/frontend/app/page.tsx` | Dashboard (server component shell + client grid) |
| `/frontend/app/projects/[id]/page.tsx` | Workspace orchestrator (client) |
| `/frontend/app/projects/[id]/layout.tsx` | ThreePanel scaffold (server) |
| `/frontend/app/components/ProjectCard.tsx` | name, desc, doc count, latest spec badge, updated_at |
| `/frontend/app/components/NewProjectModal.tsx` | US-013 |
| `/frontend/app/components/EmptyState.tsx` | reusable |
| `/frontend/app/components/Skeleton.tsx` | reusable shimmer |
| `/frontend/app/components/UploadPanel.tsx` | drag-drop + picker + progress |
| `/frontend/app/components/DocumentList.tsx` | left-panel file list |
| `/frontend/app/components/WorkflowSteps.tsx` | stepper in left panel |
| `/frontend/app/components/OutputTabs.tsx` | pill tabs container |
| `/frontend/app/components/SpecEditor.tsx` | tiptap wrapper, autosave |
| `/frontend/app/components/GapQuestions.tsx` | right panel, severity grouping, resolve toggle |
| `/frontend/app/components/ReviewComments.tsx` | severity grouping, dismiss |
| `/frontend/app/components/ConfidenceBadge.tsx` | green/yellow/red chip |
| `/frontend/app/components/ExtractedRequirements.tsx` | collapsible list w/ source-ref tooltip |
| `/frontend/app/components/GenerateSpecsButton.tsx` | sequential trigger, per-tab loading |
| `/frontend/app/components/ExportMenu.tsx` | per-tab + combined |
| `/frontend/app/components/VersionBadge.tsx` | "v2" pill |
| `/frontend/app/components/SavingIndicator.tsx` | Saved / Saving… |
| `/frontend/app/components/ThreePanel.tsx` | layout primitive; mobile collapses |

**User stories covered:** US-012 through US-020 (frontend half).

**Acceptance check (per story):**
- `npm run typecheck` clean
- Dashboard renders projects, empty state, modal creates + navigates
- Workspace shows three panels at 20/55/25; mobile collapses to tabs
- Drag-drop upload populates left list; "Extract" shows extracted requirements with confidence chips; right panel populates gaps grouped by severity
- "Generate Specs" sequentially fills tabs with per-tab loading
- Edit in SpecEditor → see "Saving…" → 500 ms → "Saved"; refresh persists
- "Export Markdown" downloads file with correct name; "Export All" combines
- Review tab groups Critical/Warning/Suggestion; Dismiss removes from view; right panel mirrors blockers/criticals while on other tabs
- All flows visually verified via `dev-browser` skill

---

### Phase E — Integration, hardening, polish

**Goal:** End-to-end production-feel MVP.

**Deliverables:**

| Path | Purpose |
|------|---------|
| `/backend/tests/test_e2e_flow.py` | Full pipeline against MockProvider |
| `/README.md` (final) | Quickstart, ASCII architecture diagram, troubleshooting |
| `/docs/skill-authoring.md` | How to add a 7th skill |
| `/docs/architecture.md` | Sequence diagrams: upload → extract → generate |
| `/Makefile` | `make up`, `make migrate`, `make dev`, `make test` |

**Hardening tasks:**
- Backend: structured JSON logs, request ID middleware, global exception → envelope, 404/422/500 mappers
- Frontend: error boundaries, toast notifications, accessibility audit (focus rings, labels), keyboard nav (ESC closes modal, Tab through tabs)
- Performance: SWR cache invalidation on mutation; debounced save coalesces requests; lazy-load tiptap
- Empty-state polish on every list
- Final `ui-ux-pro-max-skill` pass on color tokens, spacing, typography

**Acceptance check:**
- Clean clone → `docker compose up` → `make migrate` → `make dev` → complete README "Sample project flow" with MockProvider in < 2 min
- `pytest`, `npm run typecheck`, `npm run lint` all green
- `dev-browser` walkthrough of all 9 UX user stories passes

---

## 3. Data Model

All tables follow `postgres.md` rules: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (UUID v4, never auto-int), `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` (auto-updated via SQLAlchemy `onupdate` event). Enable `pgcrypto` in migration 0001 (`CREATE EXTENSION IF NOT EXISTS pgcrypto`).

**Enum types** (created via `sqlalchemy.Enum(..., name=..., create_type=True)` so Alembic emits the `CREATE TYPE`):

| Enum name | Values |
|---|---|
| `spec_type` | `functional`, `technical`, `user_stories`, `review` |
| `requirement_category` | `functional`, `non_functional`, `constraint`, `assumption`, `stakeholder` |
| `confidence_level` | `high`, `medium`, `low` |
| `gap_category` | `scope`, `data`, `security`, `integration`, `ux` |
| `gap_severity` | `blocker`, `major`, `minor` |
| `review_severity` | `critical`, `warning`, `suggestion` |
| `review_category` | `completeness`, `ambiguity`, `security`, `data`, `implementation` |
| `parse_status` | `pending`, `done`, `error` |

All `_id` FK columns get explicit indexes (`idx_{table}_{column}`) — PG does not auto-create them. All FKs declare `ON DELETE` behavior (see §1A). The column tables below use the abstract type name (e.g., "enum: …"); the SQLAlchemy model uses the PG enum types above.

### `projects`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT NOT NULL | |
| description | TEXT NULL | |
| deleted_at | TIMESTAMPTZ NULL | soft delete |
| created_at / updated_at | TIMESTAMPTZ | |

Index: `(deleted_at)` for filtering.

### `documents`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects.id (ON DELETE CASCADE) | indexed |
| filename | TEXT NOT NULL | |
| mime_type | TEXT NOT NULL | |
| size_bytes | BIGINT NOT NULL | |
| storage_path | TEXT NOT NULL | local rel path; later swappable to blob URL |
| extracted_text | TEXT NULL | |
| parse_status | TEXT NOT NULL DEFAULT 'pending' | pending/done/error |
| parse_error | TEXT NULL | |

### `extracted_requirements`
One row per requirement (not one blob).

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | indexed |
| category | TEXT NOT NULL | enum: functional / non_functional / constraint / assumption / stakeholder |
| ext_id | TEXT NOT NULL | LLM-assigned id (e.g., "FR-1") |
| text | TEXT NOT NULL | |
| source_reference | TEXT NULL | quoted excerpt from doc |
| confidence | TEXT NOT NULL | enum: high / medium / low |
| document_id | UUID FK → documents.id NULL | provenance optional |

Index: `(project_id, category)`.

### `spec_versions`
Holds every spec generation, keyed by per-project version_number.

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | indexed |
| spec_type | TEXT NOT NULL | enum: functional / technical / user_stories / review |
| version_number | INT NOT NULL | per-project monotonic |
| content_json | JSONB NOT NULL | structured spec |
| content_markdown | TEXT NULL | derived for export/editor, optional cache |
| is_edited | BOOLEAN NOT NULL DEFAULT false | flips on first PATCH |

**Unique constraint:** `UNIQUE (project_id, version_number)` — global per project.

**Per-project version_number mechanism:** Inside the same transaction as the insert:
```sql
SELECT id FROM projects WHERE id = $project_id FOR UPDATE;
SELECT COALESCE(MAX(version_number),0)+1 FROM spec_versions WHERE project_id = $project_id;
```
This serializes concurrent generations per project (acceptable for MVP since it's single-user-per-project).

Index: `(project_id, spec_type, version_number DESC)` to fetch latest fast.

### `gap_questions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | indexed |
| ext_id | TEXT NOT NULL | LLM-assigned id |
| question | TEXT NOT NULL | |
| category | TEXT NOT NULL | enum: scope / data / security / integration / ux |
| severity | TEXT NOT NULL | enum: blocker / major / minor |
| resolved | BOOLEAN NOT NULL DEFAULT false | |
| resolution_text | TEXT NULL | free-text answer fed into spec regen |
| resolved_at | TIMESTAMPTZ NULL | |

Index: `(project_id, resolved)`.

### `review_comments`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | indexed |
| spec_version_id | UUID FK → spec_versions.id NULL | which spec it targets |
| section | TEXT NOT NULL | |
| comment | TEXT NOT NULL | |
| severity | TEXT NOT NULL | enum: critical / warning / suggestion |
| category | TEXT NOT NULL | enum: completeness / ambiguity / security / data / implementation |
| dismissed | BOOLEAN NOT NULL DEFAULT false | |
| dismissed_at | TIMESTAMPTZ NULL | |

Index: `(project_id, dismissed, severity)`.

---

## 4. API Surface

All responses use envelope `{ "data": <T>, "error": null|<obj>, "meta": <obj> }`. Errors carry `{ code, message, details? }`. Mounted under `/api`.

| Method | Path | Purpose | US |
|---|---|---|---|
| POST | `/api/projects` | Create project | US-002 |
| GET | `/api/projects` | List (incl. doc_count, latest_spec_type, latest_updated_at) | US-002, US-012 |
| GET | `/api/projects/{id}` | Detail incl. documents + latest spec per type | US-002, US-014 |
| DELETE | `/api/projects/{id}` | Soft delete (sets `deleted_at`) | US-002 |
| POST | `/api/projects/{id}/documents` | Multipart upload (≤20MB, PDF/DOCX/TXT) | US-003, US-015 |
| GET | `/api/projects/{id}/documents` | List documents | US-015 |
| DELETE | `/api/projects/{id}/documents/{doc_id}` | Remove document | US-015 |
| POST | `/api/projects/{id}/extract` | Run requirement_extractor | US-006, US-016 |
| GET | `/api/projects/{id}/requirements` | List extracted requirements | US-016 |
| POST | `/api/projects/{id}/detect-gaps` | Run gap_detector | US-007, US-016 |
| GET | `/api/projects/{id}/gaps` | List gap questions | US-016 |
| PATCH | `/api/projects/{id}/gaps/{gap_id}` | Resolve/un-resolve + answer text | US-016 |
| POST | `/api/projects/{id}/specs/functional` | Generate Functional Spec (new version) | US-008, US-017 |
| POST | `/api/projects/{id}/specs/technical` | Generate Technical Spec | US-009, US-017 |
| POST | `/api/projects/{id}/specs/user-stories` | Generate User Stories | US-010, US-017 |
| POST | `/api/projects/{id}/review` | Run reviewer skill | US-011, US-020 |
| GET | `/api/projects/{id}/specs` | List latest by type; `?all=true` returns all | US-017 |
| GET | `/api/projects/{id}/specs/{version_id}` | Get specific version | US-017 |
| PATCH | `/api/projects/{id}/specs/{version_id}` | Update content (autosave) | US-018 |
| GET | `/api/projects/{id}/export/markdown?spec_type=...` | Download .md (functional / technical / user_stories / review / all) | US-019 |
| GET | `/api/projects/{id}/reviews` | List review comments | US-020 |
| PATCH | `/api/projects/{id}/reviews/{comment_id}` | Dismiss / undismiss | US-020 |
| GET | `/healthz` | Liveness | infra |

CORS: allow `http://localhost:3000` only.

---

## 5. Skill Engine Architecture

### Directory layout (one skill, e.g., requirement_extractor)

```
backend/app/services/skills/requirement_extractor/
  instruction.md      # system message; persona + rules + "return JSON only"
  template.md         # Jinja2 user prompt; vars: {{ document_text }}, {{ project_name }}
  schema.json         # JSON Schema (draft-2020-12) for the expected output
```

### `SkillEngine.run(skill_name, context, provider) -> dict`

```python
async def run(skill_name: str, context: dict, provider: LLMProvider) -> dict:
    skill_dir = SKILLS_ROOT / skill_name
    instruction   = (skill_dir / "instruction.md").read_text()
    template_src  = (skill_dir / "template.md").read_text()
    schema        = json.loads((skill_dir / "schema.json").read_text())

    prompt = Environment(autoescape=False).from_string(template_src).render(**context)

    raw = await provider.complete(prompt=prompt, system=instruction, skill_name=skill_name)
    parsed = extract_json(raw)               # strips ```json fences, trims prose
    try:
        jsonschema.validate(parsed, schema)
        return parsed
    except ValidationError as e:
        retry_prompt = (
            f"{prompt}\n\nYour previous response failed schema validation: {e.message}\n"
            f"Return ONLY valid JSON matching the schema. No prose."
        )
        raw2 = await provider.complete(prompt=retry_prompt, system=instruction, skill_name=skill_name)
        parsed2 = extract_json(raw2)
        jsonschema.validate(parsed2, schema)  # raise on second failure
        return parsed2
```

Notes:
- `extract_json` handles ` ```json ... ``` ` fences and trims pre/post prose.
- `skill_name` is passed to the provider so MockProvider dispatches to the right canned response.
- Engine emits structured log lines per call: `skill`, `provider`, `attempt`, `latency_ms`.
- One retry only (per PRD). Second failure → raise `SkillValidationError` → API returns 502 envelope.

### Skill content responsibilities

| Skill | Inputs (context) | Output schema highlights |
|---|---|---|
| `requirement_extractor` | `document_text`, `project_name` | `{functional_requirements[], non_functional_requirements[], constraints[], assumptions[], stakeholders[]}`; each `{id, text, source_reference, confidence}` |
| `gap_detector` | `extracted_requirements` JSON | `{gaps: [{id, question, category, severity}]}` |
| `functional_spec` | `extracted_requirements`, `resolved_gap_answers[]` | `{overview, objectives[], scope, features:[{name, description, acceptance_criteria[]}]}` |
| `technical_spec` | `functional_spec`, `extracted_requirements` | `{architecture_overview, components[], data_models[], api_endpoints[], tech_stack, risks[]}` |
| `user_stories` | `functional_spec`, `extracted_requirements` | `{stories: [{id, title, description, acceptance_criteria[], story_points, labels[]}]}` |
| `reviewer` | `functional_spec`, `technical_spec`, `user_stories`, `extracted_requirements` | `{comments: [{id, section, comment, severity, category}]}` |

---

## 6. LLM Provider Design

### `base.py`
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, *, prompt: str, system: str, skill_name: str | None = None) -> str:
        """Return raw model text. Skill engine handles JSON parsing/validation."""
```

### `gemini_provider.py`
- Lazy-construct `genai.GenerativeModel(model_name=settings.GEMINI_MODEL)` (default `gemini-1.5-flash`)
- Pass `system_instruction=system`, `contents=[prompt]`
- `generation_config={"response_mime_type": "application/json", "temperature": 0.3}`
- Wrap SDK calls in `asyncio.to_thread` since the SDK is sync
- Network retries on 429/5xx with exponential backoff (max 3, orthogonal to skill engine's 1 validation retry)
- Errors mapped to `LLMProviderError`

### `mock_provider.py`
- Dict `{skill_name: canned_json_string}` of hand-crafted realistic responses
- `requirement_extractor` returns ≥5 items spread across categories with varied confidence
- `gap_detector` returns ≥3 questions across categories/severities
- `functional_spec` returns spec with ≥3 features
- `technical_spec` returns ≥3 components, ≥2 data_models, ≥3 endpoints
- `user_stories` returns ≥5 stories with ACs and points
- `reviewer` returns ≥4 comments across severities/categories
- Canned outputs stored as separate `.json` files in `mock_provider/fixtures/` for readability and tested against each skill's `schema.json` in CI

### Selection (`services/llm/__init__.py`)
```python
def get_provider() -> LLMProvider:
    name = settings.LLM_PROVIDER.lower()
    if name == "gemini":
        if not settings.GEMINI_API_KEY:
            log.warning("GEMINI_API_KEY missing — using MockProvider")
            return MockProvider()
        return GeminiProvider()
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {name}")
```
FastAPI dependency: `provider: LLMProvider = Depends(get_provider)`.

---

## 7. Frontend Architecture

### Routing (Next 14 App Router)
```
app/
  layout.tsx              # root shell, font, theme
  page.tsx                # dashboard (server fetches initial; client grid)
  projects/
    [id]/
      layout.tsx          # ThreePanel scaffold + project header (server)
      page.tsx            # client orchestrating tabs/state
```

### Server vs. Client
- **Server components:** `app/page.tsx` (initial project list SSR); `app/projects/[id]/layout.tsx` (project header + initial fetch).
- **Client components:** Everything interactive — UploadPanel, GapQuestions, OutputTabs, SpecEditor, NewProjectModal, ReviewComments. Marked `"use client"`.
- **Data fetching:** SWR for client-side after initial SSR hydrate. Mutations call `lib/api.ts` then `mutate()`.

### Key components

| Component | Responsibilities |
|---|---|
| `ProjectCard` | name, description (2-line truncate), doc count, latest spec badge, relative updated time |
| `NewProjectModal` | Headless modal (focus trap, ESC, backdrop close), inline name validation, optimistic create |
| `ThreePanel` | CSS grid `grid-cols-[20%_55%_25%]` on `md:`; mobile → single column + segmented tabs |
| `UploadPanel` | `react-dropzone` (or built-in DnD), per-file progress via XHR, client-side type/size reject |
| `DocumentList` | List items with mime icon, size formatter, upload date |
| `WorkflowSteps` | 4 dots: Upload → Extract → Generate → Review; highlights current |
| `ExtractedRequirements` | Collapsible by category; rows = ConfidenceBadge + text + tooltip (Radix) for source_reference |
| `ConfidenceBadge` | `high → emerald`, `medium → amber`, `low → rose` |
| `OutputTabs` | Pill tabs: Functional / Technical / User Stories / Review / Open Questions; VersionBadge if version>1 |
| `SpecEditor` | tiptap + StarterKit; serializes to Markdown for autosave; `useDebouncedSave(500)` calls PATCH; SavingIndicator |
| `GapQuestions` | Right panel; grouped Blocker → Major → Minor; resolve toggle + free-text input → PATCH `resolution_text` |
| `ReviewComments` | Critical → Warning → Suggestion; Dismiss; right panel shows blockers/criticals while on other tabs |
| `GenerateSpecsButton` | Sequential POSTs functional → technical → user-stories → review; per-tab loading |
| `ExportMenu` | Dropdown: Functional/Technical/User Stories/Review/All → `window.location.href = url` to trigger download |

### Tiptap integration
- `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-placeholder`
- Render `content_markdown` from backend; on edit, serialize editor state to Markdown
- Autosave: `useDebouncedSave` calls `PATCH /api/projects/{id}/specs/{version_id}` with `{ content_markdown }`
- For MVP: edits stored as Markdown in `content_markdown`; structured `content_json` remains AI-output-of-record

### State management
- SWR keyed by URL; `mutate(key)` to revalidate after mutations
- Per-tab loading kept in local `useState` in the workspace page; flips off as each POST resolves

---

## 8. Three-Panel Layout Spec

### Desktop (`md:` and up)

```
┌─────────────────────────────────────────────────────────────┐
│  Project Header (name, breadcrumb, GenerateSpecsButton)     │
├────────────┬──────────────────────────────┬─────────────────┤
│ Left 20%   │ Center 55%                   │ Right 25%       │
│            │                              │                 │
│ Workflow   │ OutputTabs (pill)            │ Active-tab      │
│ Steps      │                              │ context:        │
│            │ Active tab body:             │  Functional/    │
│ Doc list   │  - Functional/Tech/Stories   │   Tech/Stories  │
│            │    → SpecEditor (tiptap)     │   → blockers +  │
│ Upload     │  - Review                    │     criticals   │
│ Panel      │    → ReviewComments grouped  │  Review         │
│            │  - Open Questions            │   → unresolved  │
│            │    → GapQuestions list       │     gaps        │
│            │                              │  Open Q         │
│            │ ExportMenu (top-right)       │   → all gaps    │
│            │ VersionBadge                 │                 │
└────────────┴──────────────────────────────┴─────────────────┘
```

CSS: `grid grid-cols-[minmax(0,20%)_minmax(0,55%)_minmax(0,25%)] gap-0`. Each panel scrolls independently (`overflow-y-auto h-[calc(100vh-56px)]`). Fixed proportions (not resizable) for MVP.

### Mobile (`<md`)
Single column. Sticky top bar with a 3-tab segmented control: **Docs · Spec · Notes** that switches which panel is mounted. Inside **Spec**, OutputTabs renders horizontally scrollable. SpecEditor goes full-width.

---

## 9. Environment / Config

### `.env.example` (root or `/backend`)
```
# Backend
DATABASE_URL=postgresql+asyncpg://specforge:specforge@localhost:5432/specforge
UPLOAD_DIR=./uploads
MAX_UPLOAD_MB=20
LLM_PROVIDER=gemini          # gemini | mock
GEMINI_API_KEY=              # leave blank to force MockProvider
GEMINI_MODEL=gemini-1.5-flash
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

### `/frontend/.env.example`
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

### `docker-compose.yml` services
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: specforge
      POSTGRES_PASSWORD: specforge
      POSTGRES_DB: specforge
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U specforge"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

Backend and frontend run on host during dev (containerize later if desired).

### README setup steps (final form, abbreviated)
1. `cp .env.example .env` and fill (or leave `GEMINI_API_KEY` blank for mock mode)
2. `docker compose up -d postgres`
3. `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
4. `alembic upgrade head`
5. `uvicorn app.main:app --reload --port 8000`
6. `cd frontend && npm install && cp .env.example .env.local && npm run dev`
7. Visit `http://localhost:3000`

---

## 10. Verification Plan

### Per-phase

| Phase | Backend check | Frontend check | UX check |
|---|---|---|---|
| A | `curl localhost:8000/healthz` → 200; `psql` connects | `npm run typecheck`; `/` loads placeholder | n/a |
| B | `alembic upgrade head` clean; `pytest backend/tests/test_models.py test_skill_engine.py` | n/a | n/a |
| C | Full curl flow (Phase C acceptance); `pytest backend/tests/` green; `/docs` shows all routes; export `.md` opens in viewer | n/a | n/a |
| D | n/a | `npm run typecheck` + `npm run lint` | `dev-browser` walkthrough of US-012 → US-020; visual match vs. `ui-ux-pro-max-skill` |
| E | `pytest` incl. `test_e2e_flow.py` | `npm run build` clean | Re-run all `dev-browser` flows; sample-project happy path in <2 min |

### Verification commands quick-reference
```bash
# Backend
alembic upgrade head
pytest -q
ruff check .  # optional

# Frontend
npm run typecheck
npm run lint
npm run build

# Mandatory UX verification (Phase D onward, per PRD Design Considerations)
# 1. Invoke ui-ux-pro-max-skill BEFORE writing each component
# 2. Use dev-browser to load http://localhost:3000 and click through each user story
```

---

## 11. Risks & Open Decisions

| # | Risk / Decision | Default applied | Trigger to revisit |
|---|---|---|---|
| 1 | Gap answers free-text vs. structured | **Free text** fed into functional_spec context | If users want canned answer templates |
| 2 | Per-doc 20 MB cap; no project total cap | Locked | If project sizes balloon |
| 3 | Store all versions; UI shows latest only | Locked | If diff/restore requested |
| 4 | Reviewer = final manual step of Generate Specs | Locked | If auto-review desired |
| 5 | No dashboard tagging/search for MVP | Locked | Post-MVP |
| 6 | `version_number` allocation under contention | Single-writer-per-project; serialize via `SELECT FOR UPDATE` on `projects` row | Multi-user phase |
| 7 | Tiptap stores Markdown vs. JSON | **Markdown for autosave**; structured JSON = AI output of record | If structural editing required |
| 8 | Mock-mode source_reference quotes | Reference text from canned doc; if uploaded text shorter, MockProvider returns generic quotes | Edge case in demos |
| 9 | Gemini JSON-mode reliability | `response_mime_type: application/json`; rely on engine retry | If drift observed |
| 10 | LLM cost | `gemini-1.5-flash`; no token budget enforcement in MVP | Pre-production |
| 11 | Large doc text overflow | Truncate `document_text` to N chars per call; log truncation; no chunking in MVP | If users upload very large PDFs |
| 12 | Concurrency on autosave PATCH | Last-write-wins; no optimistic lock | Multi-user phase |
| 13 | Soft-deleted projects cleanup | Manual SQL | Add admin job post-MVP |
| 14 | Per-skill latency variability | Tabs populate progressively, masking it | Background job queue if >30s |
| 15 | Tiptap bundle size | Lazy-load editor on first edit | If perf budget exceeded |
| 16 | Auth deferred per PRD non-goals; `security.md` mandates JWT/RBAC | **Deferred** — every endpoint is open in MVP; rate limiting + CORS whitelist + security headers + dependency pinning + file-upload hardening DO apply now | Adding multi-user → introduce `users` table, `Project.owner_id`, `require_user()` dep, JWT (HS256, 1h access / 7d refresh, rotation), bcrypt cost ≥12, RBAC, login/refresh/logout endpoints |
| 17 | LLM cost runaway under abuse (no auth) | `slowapi` rate limit 30/min/IP on `/extract`, `/detect-gaps`, `/specs/*`, `/review`; `MAX_UPLOAD_MB=20` cap | If abuse seen / before public deploy |
| 18 | File upload exploits (path traversal, MIME spoofing) | Magic-byte validation + UUID-named storage + filename sanitization | If a new file type added |
| 19 | DB-level data integrity beyond Pydantic | NOT NULL everywhere, explicit FK `ON DELETE`, CHECK constraints (`size_bytes > 0`, `version_number > 0`), PG enums for fixed value sets | Schema evolution per `postgres.md` § Migrations |

---

## 12. Implementation Sequencing Cheat Sheet

```
A1  scaffold repo (compose, deps, configs)            ─┐
A2  /healthz + base layout                              │ Phase A
                                                        ┘
B1  models + migrations                                ─┐
B2  LLMProvider ABC + Mock + Gemini                     │ Phase B
B3  SkillEngine + tests                                 ┘

C1  skill content (6 dirs × 3 files)                   ─┐
C2  document parser + storage                           │
C3  projects + documents APIs                           │ Phase C
C4  extract + detect-gaps APIs                          │
C5  4 spec generation APIs + PATCH + export             │
C6  reviewer + dismiss API                              ┘

D1  api client + types + SWR hooks                     ─┐
D2  dashboard + NewProjectModal (US-012, US-013)        │
D3  ThreePanel layout (US-014)                          │
D4  UploadPanel + DocumentList (US-015)                 │ Phase D
D5  Extract flow + GapQuestions (US-016)                │
D6  OutputTabs + GenerateSpecsButton (US-017)           │
D7  SpecEditor + autosave (US-018)                      │
D8  Export menu (US-019 FE)                             │
D9  ReviewComments + right-panel mirror (US-020)        ┘

E1  e2e tests, logging, error handling, README, docs    Phase E
E2  accessibility + final ui-ux-pro-max polish
```

Each Phase D row must: (a) invoke `ui-ux-pro-max-skill` for design tokens/layout before coding, (b) ship with `npm run typecheck` green, (c) be verified via `dev-browser`.

---

## 13. User Story → Phase mapping

| US | Title | Phase |
|---|---|---|
| US-001 | DB schema | B |
| US-002 | Project CRUD API | C |
| US-003 | Document upload + parse API | C |
| US-004 | LLM abstraction + Gemini provider | B |
| US-005 | Skill Engine core | B |
| US-006 | requirement_extractor skill | C |
| US-007 | gap_detector skill | C |
| US-008 | functional_spec_generator skill | C |
| US-009 | technical_spec_generator skill | C |
| US-010 | user_story_generator skill | C |
| US-011 | reviewer skill | C |
| US-012 | Dashboard list | D |
| US-013 | Create project modal | D |
| US-014 | Three-panel workspace | D |
| US-015 | Document upload UI | D |
| US-016 | Requirements + gaps UI | D |
| US-017 | Spec generation UI | D |
| US-018 | Inline rich-text editing + autosave | D |
| US-019 | Markdown export (backend in C, frontend in D) | C + D |
| US-020 | Review Comments panel | D |
