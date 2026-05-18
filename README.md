# SpecForge AI

A guided, enterprise-grade portal that transforms messy requirements documents into structured, versioned specs — Functional Spec, Technical Spec, Jira-ready User Stories, Open Questions, and Review Comments — via an AI Skill Engine.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│  Next.js 14 (App Router)  localhost:3000                 │
│  Three-panel workspace: Left (docs) · Center (specs) ·   │
│  Right (gaps / review)                                   │
└────────────────────┬─────────────────────────────────────┘
                     │ /api/*  (rewrite → localhost:8000)
┌────────────────────▼─────────────────────────────────────┐
│  FastAPI  localhost:8000                                  │
│  ├── LLMProvider abstraction (Gemini / Mock)             │
│  └── Skill Engine (Jinja2 + JSON Schema + 1 retry)       │
│       ├── requirement_extractor                          │
│       ├── gap_detector                                   │
│       ├── functional_spec_generator                      │
│       ├── technical_spec_generator                       │
│       ├── user_story_generator                           │
│       └── reviewer                                       │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│  PostgreSQL 16  localhost:5432  (Docker)                  │
│  projects · documents · extracted_requirements           │
│  spec_versions · gap_questions · review_comments         │
└──────────────────────────────────────────────────────────┘
```

---

## Quick start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 20+

### 1 — Clone and configure

```bash
git clone <repo-url>
cd SpecForge
cp .env.example .env
# Edit .env — leave GEMINI_API_KEY blank to run in mock mode
```

### 2 — Start Postgres

```bash
docker compose up -d postgres
```

### 3 — Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

API docs available at http://localhost:8000/docs

### 4 — Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Postgres async URL |
| `UPLOAD_DIR` | `./uploads` | Local file storage path |
| `MAX_UPLOAD_MB` | `20` | Max upload size per file |
| `LLM_PROVIDER` | `gemini` | `gemini` or `mock` |
| `GEMINI_API_KEY` | _(empty)_ | Omit to force mock mode |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Model name |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed frontend origin |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Mock mode

Leave `GEMINI_API_KEY` empty (or set `LLM_PROVIDER=mock`) — the system uses pre-written realistic JSON fixtures for all six skills. The full workflow completes without any API calls.

---

## Project structure

```
backend/
  app/
    main.py            FastAPI app, CORS, security headers, rate limiter
    config.py          pydantic-settings config
    db.py              Async SQLAlchemy engine + session factory
    api/               Route handlers (projects, documents, specs, gaps, reviews)
    models/            SQLAlchemy ORM models
    schemas/           Pydantic request/response schemas
    services/
      llm/             LLMProvider abstraction (base, gemini, mock)
      skills/          Skill Engine + 6 skill directories
      documents/       File parser + storage abstraction
      export/          Markdown exporter
  alembic/             Database migrations
  uploads/             Local file storage (gitignored)

frontend/
  app/
    page.tsx           Dashboard
    projects/[id]/     Project workspace (three-panel)
    components/        All UI components
    lib/               API client, types, SWR hooks
```

---

## Running tests

```bash
cd backend
pytest -q
```

---

## Adding a new skill

See `.claude/plans/specforge-implementation-plan.md` §5 for the Skill Engine contract. Each skill is a directory under `backend/app/services/skills/` containing:

- `instruction.md` — system message for the LLM
- `template.md` — Jinja2 user prompt template
- `schema.json` — JSON Schema for output validation
