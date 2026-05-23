# SpecForge — project guide

SpecForge is an AI-assisted SDLC portal: it turns messy requirements into structured, versioned specs, grounded in per-application "App Brains". (The product is **SpecForge** — never the old placeholder "DocForge".)

Monorepo with two apps orchestrated by the root `Makefile`:
- `backend/` — FastAPI + SQLAlchemy(async) + Celery. See `backend/CLAUDE.md`.
- `frontend/` — Next.js 14 (App Router) + shadcn/ui. See `frontend/CLAUDE.md`.

## Modules (built in order; each has a deep plan in `.claude/plans/`)
- **E0 Foundation** — auth/RBAC, projects, document upload, spec generation (functional/technical/user-stories/review), versioning, audit.
- **E1 App Brain** — onboard apps, ingest a corpus, extract facts, RAG `/ask`. Retrieval is **hybrid**: pgvector chunks **+** PageIndex reasoning tree.
- **E2 Project Intake** — portfolio (search/saved-views/table-board/triage), project wizard, **PageIndex** source corpus, adaptive **Requirement Understanding (RU)** interview, and the **generation gate** (specs are blocked until the RU is human-validated).

## Stack
Postgres + **pgvector**, Redis (Celery broker/result), **Vertex AI Gemini** (`gemini-2.5-flash`) via a GCP service account, **PageIndex** (vendored, reasoning tree over docs).

## Run it (all from repo root)
```
make install install-fe      # one-time deps (creates backend/.venv)
make migrate                 # alembic upgrade head
make seed                    # 7 test users, one per role
make dev-be                  # backend  → 127.0.0.1:8000
make dev-fe                  # frontend → localhost:3000
make worker                  # Celery worker (needs Redis on :6379)
make beat                    # Celery Beat (scheduled jobs: triage, purges)
make test-be / typecheck / lint
```
Requires Redis on `localhost:6379` (a container is fine, but it MUST publish the port: `docker run -d -p 6379:6379 redis:7-alpine`). Postgres on `:5432`.

**Login:** `admin@specforge.test` / `SpecForge#Test2026!` (platform_admin). Other roles: `analyst@ owner@ architect@ appowner@ qa@ reviewer@` (same password).

## Hard constraints (do not violate)
- **PII is out of scope, project-wide.** No PII detection/classification/restricted-retrieval anywhere — requirements legitimately contain PII-like data a detector can't distinguish. Never reintroduce it.
- **Secrets:** `video-key.json` (GCP service account) and `backend/.env` are secrets — never commit them.
- **Mock-first testing:** CI/tests run with `LLM_PROVIDER=mock`, which also routes embeddings + the corpus index to deterministic mocks (zero Vertex/PageIndex/network calls). Keep every new LLM/embedding/corpus feature behind its provider abstraction so the mock path stays green.

## Helper scripts (`backend/scripts/`)
- `seed_projects.py` — idempotent demo project `PRJ-0001` (PayHub) with a generated RU, mock providers.
- `purge_test_data.py` — remove test clutter (dry-run by default; `--apply` to delete; keeps clean-named apps + whitelisted projects).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
