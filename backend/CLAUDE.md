# SpecForge backend

FastAPI + SQLAlchemy 2.0 (async/asyncpg) + Alembic + Celery/Redis + pgvector. Python 3.13 venv at `.venv`. Run commands from the repo root via `make` (see root CLAUDE.md).

## Layout
- `app/api/` — routers, mounted in `app/main.py`. Most under `/api` (auth/versions/context/apps mount their own paths).
- `app/models/` — SQLAlchemy models; **register every new model in `app/models/__init__.py`** or Alembic autogen/mapper config misses it.
- `app/schemas/` — Pydantic; `app/services/` — business logic; `app/core/` — auth/rbac/audit/credentials.
- `workers/` — Celery (`celery_app.py`, `tasks.py`, `dispatch.py`).
- `alembic/versions/` — migrations `0001`→`0007`. `scripts/` — seeds + purge.

## Conventions
- **Response envelope:** return `ok(data, meta?)` / raise `err(code, message, status)` from `app.schemas.envelope`. Never return bare dicts.
- **Migrations:** hand-written, raw SQL via `op.execute`, `IF NOT EXISTS`, and `DO $$ … EXCEPTION WHEN duplicate_object` guards for enums. Reuse existing enums with `create_type=False`. Apply with `make migrate`.
- **Auth/RBAC:** `Depends(get_current_user)`, `require_role(...)`, `get_project_or_404`. Admin roles (`platform_admin`, `compliance_reviewer`) see all; others are owner-or-member scoped.
- **Generation gate:** `require_ru_validated` (in `app/api/deps.py`) gates the spec-generate endpoints in `specs.py` → 409 until the RU is validated.

## Provider abstractions (swappable + mockable — the core pattern)
All return a deterministic Mock when `settings.llm_provider == "mock"`:
- `app/services/llm/` → `get_provider()` (Gemini via `langchain-google-genai`).
- `app/services/embeddings/` → `get_embedding_provider()` (pgvector vectors).
- `app/services/corpus_index/` → `get_corpus_index_provider()` (PageIndex reasoning tree).

**Vertex auth:** `app/core/google_credentials.py::get_google_credentials()` loads the service account AND calls `configure_google_genai_env()` (sets `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_GENAI_USE_VERTEXAI=true` + project/location). langchain-google-genai 4.x ignores the `credentials=` kwarg for embeddings, so those env vars are required — keep them set.

## Skills (LLM with JSON schemas)
`app/services/skills/<name>/{instruction.md,template.md,schema.json}`. `SkillEngine.run(name, ctx, provider)` renders the template, calls the LLM, validates against the schema, retries once on failure, and **coerces a bare LLM array into `{single_array_prop: [...]}`** (Gemini sometimes returns `[...]` instead of `{key:[...]}`). Mocks: a fixture in `app/services/llm/fixtures/<name>.json` registered in `MockProvider._SKILL_FIXTURE_MAP`.

## PageIndex (vendored)
`vendor/pageindex/` (MIT; the GitHub repo isn't pip-installable). Builds a reasoning tree via **LiteLLM → Vertex** (`page_index_main` for PDF, `md_to_tree` for markdown). PageIndex needs document **structure** (PDF sections or `#` headings) — heading-less text yields 0 nodes, so `PageIndexProvider` synthesizes a page-node fallback. Trees stored in `document_trees` (E2 project sources) and `app_doc_trees` (E1 App Brain hybrid). Retrieval = an LLM (`source_tree_search` skill) navigates the tree.

## Celery (important gotchas)
- **Every async task must run through `_run_async()`** in `tasks.py` — it `engine.dispose()`s after each task. Without it, async-SQLAlchemy + prefork reuses a pooled connection bound to a dead event loop → "got Future attached to a different loop".
- **Dispatch with `workers/dispatch.py::dispatch(task, *args)`**, not `task.delay()` directly — it does a fast TCP pre-flight so the API never hangs when the broker is down (uploads stay durable; ingestion is re-triggerable).
- Beat schedule lives in `celery_app.py` (`recompute_triage` every 15m, token/staging purges).

## Testing
`pytest` against a **real Postgres + Redis** but **mock LLM/embeddings/corpus** (`conftest` sets `LLM_PROVIDER=mock`; the conftest user is `platform_admin`). The DB is shared across tests and not always cleaned — **use unique identifiers** (`f"app{uuid4().hex[:8]}"`) to avoid `uq_*` collisions. Live Vertex test `test_pageindex_vertex.py` is skipped unless `RUN_PAGEINDEX_LIVE=1`.

## Don't
- Reintroduce PII handling (project-wide non-goal).
- Call Vertex/PageIndex from the request path synchronously for heavy work — dispatch to Celery (PageIndex builds are ~20–50 LLM calls/doc).
