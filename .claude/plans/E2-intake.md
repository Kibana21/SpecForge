# E2 — Project Intake & Requirement Understanding — Deep Plan

**Goal:** Turn a vague business initiative into a validated, structured Requirement Understanding (RU) that gates all downstream generation. A user lands in a real portfolio (search, saved views, table/board, grouping, triage), creates a project through a guided wizard (similar-project reuse, apps-in-scope, source intake), the sources are ingested (parse → chunk → embed), an adaptive interview synthesizes a structured RU grounded in source spans + app-brain facts and asks only what it can't infer, and the user validates the RU — the human-in-the-loop checkpoint that unblocks Module 2 generation.

**Tier-1 decisions:** [`00-foundations-and-decisions.md`](00-foundations-and-decisions.md) · **Roadmap:** [`01-master-roadmap.md`](01-master-roadmap.md) · **Requirements:** [`../prd/prd-module-1-dashboard-project-hub.md`](../prd/prd-module-1-dashboard-project-hub.md)
**Binding skills:** `spec-forge-security` (auth/RBAC/upload/API security), `postgres` (models/migrations/queries), `langchain-gemini` (LLM/embeddings/RAG patterns).

**Model guidance:** Sonnet for most tasks; escalate to Opus for the RU orchestrator + interview state machine (T18–T20) and the triage analytics recompute (T15).

---

## Scope boundary for E2

| Built fully in E2 | Skeleton / deferred (full data from later epic or external service) |
|---|---|
| Portfolio search + 6 saved views + table/board + grouping + triage; project wizard (identity → reuse → apps-in-scope → sources); project source ingestion (parse→chunk→embed) with state; similar-project discovery (embeddings); apps-in-scope + app-brain context loading; adaptive RU interview + structured RU + per-field confidence + provenance; **validation gate**; workspace stage map + operational panels; assumption ledger + open questions; quality subscores (heuristic); project activity from audit | Malware scanning (`MalwareScanner` stub interface, no-op default — real engine external, overview §9 non-goal); OCR for image-only PDFs (parser yields empty text + flag); quality subscores beyond heuristics (full quality engine = E4); stage map progress for ADR/TBP/SDD/TS/TC/Trace stages (those docs ship E3/E4 — shown "not started"); BRD/FS/NFR **authoring** (E3) — E2 only unblocks it |

**PII is out of scope for SpecForge (project-wide decision).** Requirements legitimately contain PII-like data that an automatic detector cannot reliably distinguish from real PII, so no PII detection, classification, or restricted-retrieval gating is built anywhere. The BR-M1-009 acceptance criteria referencing PII flags are intentionally **dropped** from E2 scope. (E1's PII columns/filters were removed in migration `0005_remove_pii`.)

---

## 1. BRs covered & acceptance mapping

| BR | Title | Key acceptance | Verified in E2 by |
|---|---|---|---|
| BR-M1-001 | Portfolio Project Search | name/ID/BU/owner, case-insensitive, within saved view, clearable | `GET /api/projects?q=&view=` ILIKE across 4 fields; intersects view; empty q → full view |
| BR-M1-002 | Portfolio Saved Views | 6 views w/ RBAC counts; persists across mode toggle | `GET /api/projects/views` returns counts; `view=` filters; counts RBAC-scoped |
| BR-M1-003 | Table & Board Modes (Should) | table columns; board by stage; mode preserves filters | list returns all projection fields in one query; board groups by `stage` |
| BR-M1-004 | Grouped Table (Should) | group by BU/stage/owner/status; collapsible; rollups; reset | `group_by=` returns server-side group counts + stale/review/finalized rollups |
| BR-M1-005 | Insights Triage | prioritized, personalized, linked, freshness | `GET /api/triage` from materialized `triage_items`; Beat recompute writes `computed_at`/`next_at` |
| BR-M1-006 | Project Creation Intake | wizard identity/reuse/apps/sources; back/fwd; cancel=no-op; generate→interview | wizard `POST /api/projects` (extended) atomic; draft staging; cancel discards; routes to `/interview` |
| BR-M1-007 | Similar Project Discovery | match %, BU, finalized date, asset tags; toggle; provenance | `GET /api/projects/{id}/similar` cosine over `project_embeddings`; `reuse_selections` persists provenance |
| BR-M1-008 | Apps in Scope | onboarded apps w/ tier/facts/corpus/version/owner; AI-suggested preselected; count; warn-if-none | `GET /api/apps/suggest?project=` flags; `project_apps` persists; app-brain loaded for RU |
| BR-M1-009 | Source Document Intake | DOCX/PDF/XLSX/MD/PPTX/TXT; name/size/extract/index state; remove pre-gen | extended `documents` + `ingest_project_source`; states polled; delete pre-gen (PII ACs dropped — out of scope) |
| BR-M1-010 | Workspace Stage Map | 10 stages, progress %, status, stale/review distinct, click→route | `stage_progress` JSONB computed; stage map renders 10; click routes |
| BR-M1-011 | Workspace Operational Panels | sources/quality/open-Q/assumptions/activity/skill-versions/quick-links | `GET /api/projects/{id}` (extended detail) aggregates all panels |
| BR-M1-012 | Adaptive Requirement Understanding | structured RU from sources+app facts; ask-only-gaps; citations; per-field confidence; **gate** | `requirement_understanding` skill; `interview_messages`; `ru_validated` gate; audited validation |

---

## 2. Dependencies (what must already exist)

- **E0 + E1 complete.** Reuses: `get_current_user`/`require_role`/`require_project_access`, `audit.emit`, `SkillEngine`, `get_provider`/`get_embedding_provider`, `RAGRetrievalService` pattern, `chunk_text`, `pgvector` + `Vector(768)`, `StorageFile`/`StorageFileBlob`, `version_service`, `ok()`/`err()` envelope, `limiter`, Celery + Beat, `apps`/`app_facts`/`app_chunks`.
- **Existing E2 scaffolding to extend (do not duplicate):** `projects`/`project_members`, `documents` (+ parser), `extracted_requirements`, `gap_questions`, `requirement_extractor` + `gap_detector` skills, `Project` CRUD API, `NewProjectModal`, `/projects/[id]` workspace.
- **Alembic** through `0004`; new migration `0005`.
- **No new Python packages required** for the core path. Optional parsers: `openpyxl` (XLSX), `python-pptx` (PPTX) — pin if added; MD/TXT need none.

---

## 3. Data model & migrations

### Migration `0006_project_intake.py`

(`0005_remove_pii` already shipped — drops the E1 PII/classification columns.)

`upgrade()` order: ALTER existing → CREATE new (FK-dependency order) → indexes. `downgrade()` reverse. Use the same `DO $$ … EXCEPTION WHEN duplicate_object` enum guard as `0004`.

#### 3.1 ALTER `projects` — portfolio + intake fields

```sql
ALTER TABLE projects ADD COLUMN IF NOT EXISTS human_id      VARCHAR(20);   -- "PRJ-0001", searchable
ALTER TABLE projects ADD COLUMN IF NOT EXISTS business_unit VARCHAR(255);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS app_scope     VARCHAR(255);  -- free-text application/app-scope from wizard
ALTER TABLE projects ADD COLUMN IF NOT EXISTS status        VARCHAR(30)  NOT NULL DEFAULT 'draft';   -- draft|active|in_review|finalized|archived
ALTER TABLE projects ADD COLUMN IF NOT EXISTS priority      VARCHAR(20)  NOT NULL DEFAULT 'medium';  -- low|medium|high|critical
ALTER TABLE projects ADD COLUMN IF NOT EXISTS completion_pct INTEGER     NOT NULL DEFAULT 0;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS go_live_date  DATE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS stage_progress JSONB       NOT NULL DEFAULT '{}'::jsonb;  -- {stage_key: {progress:int, status:str}}
ALTER TABLE projects ADD COLUMN IF NOT EXISTS ru_validated  BOOLEAN      NOT NULL DEFAULT false;        -- the generation gate (fast check)
CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_human_id ON projects (human_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_business_unit ON projects (business_unit);
```

`human_id` allocated on create via `SELECT 'PRJ-' || LPAD((COALESCE(MAX(...),0)+1)::text,4,'0')` in a transaction (mirror spec version_number allocation in `specs.py:_allocate_and_create_spec`). Model: add columns to `app/models/project.py:Project`. `stage_progress` mapped `JSONB`.

#### 3.2 ALTER `documents` — source intake states (BR-M1-009)

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexing_status VARCHAR(20) NOT NULL DEFAULT 'pending';  -- pending|running|done|error
ALTER TABLE documents ADD COLUMN IF NOT EXISTS index_error     VARCHAR(1000);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS page_count      INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS sha256          VARCHAR(64);
CREATE INDEX IF NOT EXISTS idx_documents_sha256 ON documents (project_id, sha256);
```

(`parse_status` already serves "extraction state"; `indexing_status` is the new chunk/embed state. No PII/classification columns — out of scope.)

#### 3.3 `project_apps` — apps in scope (BR-M1-008)

```sql
CREATE TABLE IF NOT EXISTS project_apps (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    app_id            UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    suggested         BOOLEAN NOT NULL DEFAULT false,
    included          BOOLEAN NOT NULL DEFAULT true,
    app_brain_version VARCHAR(50),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, app_id)
);
CREATE INDEX IF NOT EXISTS idx_project_apps_project_id ON project_apps (project_id);
```

#### 3.4 `requirement_understanding` (BR-M1-012)

```sql
CREATE TABLE IF NOT EXISTS requirement_understanding (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    objective       TEXT,
    content_json    JSONB NOT NULL DEFAULT '{}'::jsonb,  -- stakeholders, pain_points, target_process, functional_areas, systems, integrations, roles, assumptions, open_questions, risks
    field_confidence JSONB NOT NULL DEFAULT '{}'::jsonb, -- {field: {confidence:str, completeness:int}}
    status          VARCHAR(20) NOT NULL DEFAULT 'draft', -- draft|in_interview|validated
    version_number  INTEGER NOT NULL DEFAULT 1,
    validated_at    TIMESTAMPTZ,
    validated_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

One current RU per project (UNIQUE project_id); history via `version_service` snapshots keyed `requirement_understanding:{project_id}`.

#### 3.5 `interview_messages` (BR-M1-012)

```sql
CREATE TABLE IF NOT EXISTS interview_messages (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    understanding_id UUID NOT NULL REFERENCES requirement_understanding(id) ON DELETE CASCADE,
    role             VARCHAR(20) NOT NULL,  -- ai|user|question|understanding
    content          TEXT NOT NULL,
    citations        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{kind:'source'|'fact', ref, excerpt}]
    seq              INTEGER NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_interview_messages_project_seq ON interview_messages (project_id, seq);
```

#### 3.6 `assumptions` — assumption ledger (BR-M1-011) — shared with M2

```sql
CREATE TABLE IF NOT EXISTS assumptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    ext_id      VARCHAR(50) NOT NULL,                          -- "A-001"
    text        TEXT NOT NULL,
    confidence  confidence_level NOT NULL DEFAULT 'medium',    -- reuse existing enum from 0001
    source_ref  TEXT,
    status      VARCHAR(20) NOT NULL DEFAULT 'open',           -- open|confirmed|rejected
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_assumptions_project_id ON assumptions (project_id);
```

#### 3.7 ALTER `gap_questions` → also serve workspace "open questions" (BR-M1-011)

```sql
ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS section     VARCHAR(255);
ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS due_date    DATE;
ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS assignee_id UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE gap_questions ADD COLUMN IF NOT EXISTS source      VARCHAR(20) NOT NULL DEFAULT 'gap_detector';  -- gap_detector|interview
```

One questions store; RU interview writes `source='interview'`.

#### 3.8 `project_source_chunks` — RAG over project sources (BR-M1-009-4, BR-M1-012-1)

```sql
CREATE TABLE IF NOT EXISTS project_source_chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chunk_no    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    embedding   vector(768),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_no)
);
CREATE INDEX IF NOT EXISTS idx_project_source_chunks_project ON project_source_chunks (project_id);
CREATE INDEX IF NOT EXISTS idx_project_source_chunks_ivfflat
    ON project_source_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

(Mirror `app_chunks`. Small-corpus IVFFlat caveat from E1 §14 applies — fine for E2 scale.)

#### 3.9 `reuse_selections` — similar-project reuse provenance (BR-M1-007)

```sql
CREATE TABLE IF NOT EXISTS reuse_selections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    asset_category    VARCHAR(50) NOT NULL,   -- template|requirements|nfr|glossary
    asset_ref         VARCHAR(255),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reuse_selections_project ON reuse_selections (project_id);
```

#### 3.10 `project_embeddings` — similar-project + app-suggestion vectors (BR-M1-007, -008)

```sql
CREATE TABLE IF NOT EXISTS project_embeddings (
    project_id UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    embedding  vector(768) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_project_embeddings_ivfflat
    ON project_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

Embedding = `embed(name + "\n" + description + "\n" + RU.objective)`; recomputed on create and on RU validate.

#### 3.11 `triage_items` — materialized triage (BR-M1-005)

```sql
CREATE TABLE IF NOT EXISTS triage_items (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id  UUID REFERENCES projects(id) ON DELETE CASCADE,
    kind        VARCHAR(30) NOT NULL,   -- stale_impact|review|approval|low_confidence|open_assumption
    priority    INTEGER NOT NULL,       -- lower = more urgent
    title       TEXT NOT NULL,
    link        VARCHAR(500) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_triage_items_user_priority ON triage_items (user_id, priority);
```

Recomputed wholesale per user by Beat task (delete-then-insert). `computed_at`/`next_at` drive the freshness label.

#### 3.12 Model file layout

- `app/models/project.py` — extend `Project`; add `ProjectApp`, `RequirementUnderstanding`, `InterviewMessage`, `Assumption`, `ReuseSelection`, `ProjectEmbedding`, `TriageItem`. (Or split RU/interview into `app/models/understanding.py` and chunks into `app/models/project_source.py` for clarity — mirror E1's per-domain split.)
- Extend `Document` (`app/models/document.py`), `GapQuestion` (`app/models/gap.py`).
- `app/models/project_source.py` — `ProjectSourceChunk`.
- Update `app/models/__init__.py`.

---

## 4. API contracts

All under `/api`. Min auth `Depends(get_current_user)`; resource routes use `require_project_access` (404 existence-leak). Standard `err()`/`ok()` envelope, pagination on lists.

### 4.1 Portfolio — `GET /api/projects` (extend existing)

**Query:** `q` (ILIKE name/human_id/business_unit/owner-display), `view` (all|mine|needs_review|stale|high_priority|finalized, default all), `group_by` (business_unit|stage|owner|status|none), `limit`/`offset`.

**RBAC:** non-admin sees owned OR member projects only (counts + rows). Search **intersects** the view, never broadens.

**Response 200:** `data` = list of `ProjectListItem` (full projection: id, human_id, name, business_unit, stage, status, priority, completion_pct, owner display, open_review_count, is_stale, updated_at, go_live_date, doc_count). `meta` = `{total, limit, offset, groups?}` where `groups` (when `group_by≠none`) = `[{key, count, stale, review, finalized}]`.

### 4.2 `GET /api/projects/views` — saved-view counts (BR-M1-002)

Returns `[{view, label, count}]` for the 6 views, RBAC-filtered server-side. View predicates:
- `mine` = owner_id == user OR member; `needs_review` = open `review_comments` (undismissed) > 0; `stale` = any `stage_progress[*].status=='stale'`; `high_priority` = priority in (high,critical); `finalized` = status=='finalized'.

### 4.3 `POST /api/projects` — wizard create (extend; BR-M1-006)

**Auth:** `get_current_user` (any role may create; owner = caller).
**Body `ProjectCreate` (extended):**
```json
{"name":"...","description":"...","business_unit":"Payments","app_scope":"PayHub",
 "app_ids":["uuid"], "reuse":[{"source_project_id":"uuid","asset_category":"requirements"}],
 "document_ids":["uuid"]}
```
**Validation:** name, business_unit, app_scope, description required (422 if missing/blank). `app_ids` must be onboarded + accessible. `document_ids` must be staging docs owned by caller (see 4.10).
**Processing (atomic):** allocate `human_id`; insert `Project(status='draft')`; insert `project_apps` (included=true); insert `reuse_selections`; re-parent staged `documents` to project; create `requirement_understanding(status='draft')`; dispatch `ingest_project_source.delay()` per doc + `generate_requirement_understanding.delay(project_id)`; `audit.emit("project.created", …)`.
**Response 201:** `{id, human_id}` → frontend routes to `/projects/{id}/interview`.

### 4.4 `GET /api/projects/{id}` — workspace detail (extend; BR-M1-010, -011)

`require_project_access`. Returns `ProjectDetail`: identity + `stage_progress` (10 stages) + panels: `sources` (documents w/ states + page_count), `quality` (subscores), `open_questions`, `assumptions`, `recent_activity` (last N audit events tagged ai/human), `apps_in_scope`, `skill_versions`, `ru_status`, `ru_validated`. Aggregated via selectin + scalar subqueries (mirror existing `get_project`).

### 4.5 `GET /api/projects/{id}/similar` — discovery (BR-M1-007)

`require_project_access`. Cosine over `project_embeddings` (exclude self, RBAC-filtered, finalized-preferred). Returns `[{source_project_id, name, business_unit, match_pct, finalized_at, asset_tags:[…]}]`, threshold ≥ 0.5, top 5.

### 4.6 `GET /api/apps/suggest?project_id=` — app suggestions (BR-M1-008)

Embedding similarity between project text and each onboarded app (app description/fact centroid). Returns all onboarded apps as `AppListItem` + `suggested:bool` + `match_pct`. Used by wizard to preselect.

### 4.7 Source intake (BR-M1-009)

- `POST /api/projects/{id}/documents` — extend existing upload: add XLSX/PPTX/MD to allowed MIME (magic-byte), SHA-256 dedup (409 `duplicate_document`), set `indexing_status='pending'`, dispatch `ingest_project_source.delay(doc_id)`, `audit.emit("source.uploaded")`. Rate limit `10/minute`.
- `GET /api/projects/{id}/documents` — extend read with new state fields.
- `DELETE /api/projects/{id}/documents/{doc_id}` — existing; ensure pre-generation removal excludes from RU (audit `source.removed`).

### 4.8 Adaptive interview (BR-M1-012)

- `GET /api/projects/{id}/understanding` — current RU + `field_confidence` + `interview_messages` (ordered). `require_project_access`.
- `POST /api/projects/{id}/understanding/answer` — body `{question_id|seq, answer}`; appends `user` message; re-runs `requirement_understanding` skill with accumulated Q&A; persists updated RU + new `question`/`understanding` messages; returns updated RU. Rate limit `20/minute`.
- `POST /api/projects/{id}/understanding/validate` — gate. Sets `ru.status='validated'`, `ru.validated_at/by`, `projects.ru_validated=true`; snapshot via `version_service`; recompute `project_embeddings`; `audit.emit("understanding.validated")`. **403 `understanding_incomplete`** if any required field confidence missing (configurable). Response: validated RU.
- **Generation gate enforcement:** E3 spec endpoints must check `project.ru_validated` and 409 `understanding_not_validated` if false. E2 adds the guard helper `require_ru_validated` in `deps.py` and wires it into existing `specs.py` generate endpoints.

### 4.9 Triage — `GET /api/triage` (BR-M1-005)

Returns `data` = `triage_items` for caller ordered by priority, `meta` = `{computed_at, next_at}`. Empty if never computed (UI shows "computing…").

### 4.10 Wizard staging — `POST /api/projects/staging/documents`

Upload **before** project exists (BR-M1-006-3 cancel = no orphan). Stores `Document` with `project_id=NULL` (allow nullable temporarily? No — keep FK NOT NULL). **Decision:** staging docs live under a per-user hidden "staging" pseudo-project, OR store staged blobs in `StorageFile` only and create `Document` rows at project-create time. **Chosen:** upload returns a `StorageFile` id (no `Document` row); `POST /api/projects` creates `Document` rows from `document_ids` (= StorageFile ids). Cancel → orphaned `StorageFile`s purged by a Beat sweep (`purge_orphan_staging_files`, daily). This keeps `documents.project_id` NOT NULL and guarantees no orphan project/document.

### 4.11 Assumptions & open questions (BR-M1-011)

- `GET/PATCH /api/projects/{id}/assumptions[/{aid}]` — list; patch `status`. 
- Open questions reuse existing `GET /api/projects/{id}/gaps` + `PATCH …/gaps/{gid}` (now includes section/due_date/assignee/source).

---

## 5. Background jobs (`workers/tasks.py`)

### 5.1 `ingest_project_source(document_id: str)`
Mirror `_ingest_corpus_doc`. Validate UUID; load `Document`; set `indexing_status='running'`; ensure `extracted_text` (parse from `StorageFile` if absent via extended `parser.parse`); `page_count` (fitz for PDF else 1); `chunk_text`; `embed_batch`; replace `project_source_chunks`; `ANALYZE project_source_chunks`; `indexing_status='done'`. On error → `indexing_status='error'`, `index_error`. `max_retries=3`. (No PII detection — out of scope.)

### 5.2 `generate_requirement_understanding(project_id: str)`
1. Wait-free: if any source still `pending`/`running`, re-queue with countdown 10s (bounded retries) — RU improves as sources finish but must not block the route (BE-M1-006-4).
2. Retrieve top source spans (project-scoped pgvector over `project_source_chunks`) + included app facts (`app_facts` for `project_apps`).
3. Run `requirement_understanding` skill → structured RU + per-field confidence + open_questions + assumptions + citations.
4. Persist RU (`status='in_interview'`), `interview_messages` (`understanding` + first `question` rows), `assumptions`, `gap_questions(source='interview')`.
5. `audit.emit("understanding.generated", skill_version, model, source_refs)`.

### 5.3 `recompute_triage()` (Beat, every 15 min) — BR-M1-005
Per active user: delete their `triage_items`; recompute from open `review_comments`, stale `stage_progress`, pending validations (RU not validated but sources indexed), low-confidence assumptions (`confidence='low'` & `status='open'`); insert with priority + deep link; set `computed_at=now`, `next_at=now+15m`. RBAC-correct by construction (only the user's accessible projects).

### 5.4 `purge_orphan_staging_files()` (Beat, daily)
Delete `StorageFile`s not referenced by any `Document` older than 24h (wizard cancels/abandonments).

**Beat additions** in `celery_app.py`: `recompute-triage` (`crontab(minute="*/15")`), `purge-orphan-staging` (`crontab(hour=4, minute=0)`).

---

## 6. New services

### 6.1 `app/services/storage/malware_scanner.py` (stub interface)
```python
class MalwareScanner(ABC):
    @abstractmethod
    async def scan(self, data: bytes, filename: str) -> ScanResult: ...   # ScanResult(clean: bool, detail: str|None)
class NoopMalwareScanner(MalwareScanner):  # default; logs + returns clean
def get_malware_scanner() -> MalwareScanner: ...  # env MALWARE_SCANNER=noop
```
Wired into upload before persistence; failed scan → 422 `malware_detected` + audit. Real engine deferred (overview §9).

### 6.2 `app/services/corpus/project_retrieval.py`
`retrieve_project_spans(project_id, query, top_k, db) -> list[RetrievedSpan]` — pgvector cosine over `project_source_chunks` (parameterized `CAST(:vec AS vector(768))`), threshold 0.3, joins `documents` for citation metadata. Mirror `RAGRetrievalService`. (No classification filter — PII out of scope.)

### 6.3 `app/services/portfolio/query_service.py`
Builds the RBAC-filtered portfolio query (search + view predicate + group_by aggregation) in one statement; returns rows + group rollups. Saved-view count helper.

### 6.4 `app/services/portfolio/triage_service.py`
`compute_for_user(user_id, db) -> list[TriageItem]` (used by Beat + an on-demand fallback when `triage_items` empty).

### 6.5 `app/services/understanding/orchestrator.py`
`generate(project_id, db, provider)` and `incorporate_answer(project_id, qa, db, provider)` — wrap retrieval + `SkillEngine.run("requirement_understanding", …)` + persistence. Keep stateless: each turn re-synthesizes from sources + app facts + full accumulated Q&A (robust, idempotent).

### 6.6 `app/services/quality/quality_service.py` (heuristic)
`subscores(project_id, db) -> QualityScore`: completeness = RU field coverage %; clarity = inverse of open-question density; traceability = % requirements with source_ref; risk_coverage = risks present?; consistency = placeholder 100 (full engine E4); nfr_coverage = non_functional requirement count signal. Documented as heuristic.

### 6.7 `app/services/projects/embedding_service.py`
`upsert_project_embedding(project_id, db)` — embed name+description+RU.objective; upsert `project_embeddings`. Called on create + RU validate.

---

## 7. New skill — `requirement_understanding`

**Location:** `app/services/skills/requirement_understanding/`

**`instruction.md`:** Expert business analyst. Synthesize a structured Requirement Understanding **only** from provided source spans + app-brain facts + prior Q&A. Mark each field's confidence (high=explicit in sources, medium=implied, low=inferred). Attach `[S#]`/`[F#]` citation markers to inferred claims. Generate open questions **only** for fields you cannot infer (don't ask what's already grounded). Never invent facts.

**`template.md`:**
```
## Project
Name: {{ project_name }}
Business Unit: {{ business_unit }}
Description: {{ description }}

## Retrieved Source Spans
{{ source_spans }}

## App-Brain Facts (in scope)
{{ app_facts }}

## Prior Q&A
{{ qa_pairs }}

Produce the structured Requirement Understanding. Ask only unresolved questions.
```

**`schema.json`** (object, additionalProperties:false):
- `objective` (string), `stakeholders` (array str), `pain_points` (array str), `target_process` (string), `functional_areas` (array str), `systems` (array str), `integrations` (array str), `roles` (array str), `risks` (array str)
- `assumptions`: array of `{text, confidence:enum, source_ref}`
- `open_questions`: array of `{question, field, why}`
- `field_confidence`: object `{field: {confidence:enum(high|medium|low), completeness:int 0-100}}`
- `citations`: array of `{marker, kind:enum(source|fact), ref, excerpt}`

**Mock fixture** `app/services/llm/fixtures/requirement_understanding.json` (PayHub-flavored, ~3 stakeholders, 2 pain points, 2 open questions, field_confidence for all fields). Register in `MockProvider._SKILL_FIXTURE_MAP`.

(No new skill for app-suggestion / similar-project — both use embedding cosine, not an LLM call.)

---

## 8. Pydantic schemas (`app/schemas/`)

- `project.py` (extend): `ProjectCreate` (+business_unit, app_scope, app_ids, reuse, document_ids; required validators), `ProjectListItem` (full projection), `ProjectDetail` (panels), `SavedViewCount`, `ReuseSelectionIn`.
- `understanding.py` (new): `RequirementUnderstandingRead`, `InterviewMessageRead`, `AnswerIn`, `ValidateResult`.
- `app_scope.py` (new): `AppSuggestion`, `SimilarProject`, `ProjectAppRead`.
- `triage.py` (new): `TriageItemRead`.
- `assumption.py` (new): `AssumptionRead`, `AssumptionPatch`.
- `document.py` (extend): add indexing_status/index_error/page_count/sha256.

Validators: business_unit/app_scope/description non-blank; `app_ids`/`document_ids` UUID lists; reuse `asset_category` enum.

---

## 9. Frontend pages & components

State: TanStack Query / SWR per existing pattern; access token via `tokenStore`; `api.*` additions in `lib/api.ts`; types in `lib/types.ts`.

### 9.1 `/` Dashboard → Portfolio (rebuild on existing `app/page.tsx`)
- `PortfolioToolbar`: search input (debounce 300ms, clear button), saved-view tabs w/ counts (`useViews`), table/board toggle (persist in URL), group-by select.
- `PortfolioTable` (BR-M1-003/-004): columns ID/project/BU/stage/completion/reviews/priority/owner/status/updated/go-live; collapsible group headers w/ rollups; row click → workspace.
- `PortfolioBoard`: lanes by stage; cards click → workspace.
- `TriagePanel` (BR-M1-005): prioritized items, kind icons, deep links, freshness label ("updated 3m ago · next in 12m").

### 9.2 Project Creation Wizard (`/projects/new`, replaces `NewProjectModal`)
Multi-step `WizardShell` w/ step indicator + back/next/cancel:
1. **Identity** — name, business_unit, app_scope, description (required gating).
2. **Reuse** — `SimilarProjectList` (match %, BU, finalized, asset-tag toggles) ← `GET …/similar` seeded by identity. (Discovery runs after step 1 via a transient embed of typed text.)
3. **Apps in scope** — `AppScopePicker`: all onboarded apps w/ tier/facts/corpus/version/owner; AI-suggested preselected+badged (`/api/apps/suggest`); include/exclude; selected count; warn-if-none banner.
4. **Sources** — `SourceUploader`: drag-drop DOCX/PDF/XLSX/MD/PPTX/TXT → staging upload; rows show name/size/extract/index state; remove. 
5. **Review & Generate** — summary; "Generate Understanding" → `POST /api/projects` → route `/projects/{id}/interview`. Cancel → discard (no project).

### 9.3 Project Workspace (`/projects/[id]`, reframe existing)
- `StageMap` (BR-M1-010): 10 stages w/ progress ring + status chip (stale/review visually distinct); click routes (RU→interview, BRD→editor when E3, etc.).
- Operational panels (BR-M1-011): `SourcesPanel`, `QualityPanel` (6 subscores), `OpenQuestionsPanel`, `AssumptionLedger`, `ActivityFeed` (AI vs human badge), `SkillVersions`, `QuickLinks` (BRD/review/stale/trace/interview/app-brain).
- Existing upload→extract→generate panels remain but generation actions are **disabled until `ru_validated`** with a tooltip linking to the interview.

### 9.4 Adaptive Interview (`/projects/[id]/interview`, new) — BR-M1-012
- `InterviewThread`: distinct bubbles for ai / user / question / understanding; citation chips (reuse `CitationChip`) on inferred claims.
- `UnderstandingPanel`: structured RU fields w/ per-field confidence/completeness bars.
- `AnswerComposer`: answer current question → `POST …/answer` → optimistic append + RU refresh.
- `ValidateBar`: "Validate Understanding" → `POST …/validate`; on success route back to workspace with generation unblocked; disabled w/ reason if incomplete.

### 9.5 `lib/api.ts` additions
`api.projects.list(filters)`, `.views()`, `.create(wizardPayload)`, `.similar(id)`, `.understanding(id)`, `.answer(id,…)`, `.validate(id)`, `.assumptions(id)`; `api.apps.suggest(projectId)`; `api.triage.list()`; `api.staging.uploadDocument(file)`.

---

## 10. Ordered work breakdown

### Phase 1 — Data + migration
- **T1.** Migration `0006`: ALTER projects/documents/gap_questions; CREATE project_apps, requirement_understanding, interview_messages, assumptions, project_source_chunks, reuse_selections, project_embeddings, triage_items. Indexes. `downgrade()`.
- **T2.** Models: extend `Project`/`Document`/`GapQuestion`; add new models; update `models/__init__.py`.
- **T3.** Pydantic schemas (§8).

### Phase 2 — Source intake + RAG substrate
- **T4.** Extend `parser.parse` for XLSX (openpyxl)/PPTX (python-pptx)/MD; pin deps.
- **T5.** `MalwareScanner` stub + wire into upload.
- **T6.** `ingest_project_source` task + `project_source_chunks` write + `project_retrieval` service.
- **T7.** Extend `POST/GET/DELETE …/documents` (MIME, SHA-256 dedup, states, dispatch, audit) + staging upload endpoint + `purge_orphan_staging_files` Beat.

### Phase 3 — Apps-in-scope + similar discovery
- **T8.** `embedding_service` (project embedding upsert) + `project_embeddings`.
- **T9.** `GET /api/apps/suggest` (embedding similarity to onboarded apps).
- **T10.** `GET /api/projects/{id}/similar` + `reuse_selections` persistence.
- **T11.** `project_apps` persistence + app-brain context loader for RU.

### Phase 4 — Portfolio + triage
- **T12.** `portfolio/query_service` (search + view + group_by).
- **T13.** Extend `GET /api/projects` (projection, view, group_by) + `GET /api/projects/views`.
- **T14.** `triage_service` + `triage_items` + `GET /api/triage`.
- **T15.** `recompute_triage` Beat task + freshness timestamps. *(Opus)*

### Phase 5 — Wizard create + Requirement Understanding
- **T16.** Extend `POST /api/projects` (wizard, atomic, human_id, dispatch). 
- **T17.** `requirement_understanding` skill (instruction/template/schema + mock fixture + `_SKILL_FIXTURE_MAP`).
- **T18.** `understanding/orchestrator` + `generate_requirement_understanding` task. *(Opus)*
- **T19.** `GET …/understanding`, `POST …/answer` (interview turn). *(Opus)*
- **T20.** `POST …/validate` gate + snapshot + `require_ru_validated` dep; wire gate into `specs.py` generate endpoints. *(Opus)*

### Phase 6 — Workspace aggregation + quality
- **T21.** `quality_service` heuristics + stage_progress computation.
- **T22.** Extend `GET /api/projects/{id}` detail (panels) + assumptions endpoints.
- **T23.** Seed: PRJ-0001 wired to PayHub app brain w/ a sample source + generated RU (extend `seed_users.py` or new `seed_projects.py`) using `LLM_PROVIDER=mock`.

### Phase 7 — Frontend
- **T24.** `lib/types.ts` + `lib/api.ts` additions; hooks (`useProjects`, `useViews`, `useTriage`, `useUnderstanding`, `useSimilar`).
- **T25.** Portfolio: toolbar, table, board, grouping, triage panel.
- **T26.** Wizard (5 steps) replacing `NewProjectModal`.
- **T27.** Workspace: stage map + operational panels; gate generation actions.
- **T28.** Adaptive interview page (thread, understanding panel, answer composer, validate bar).

---

## 11. Security checklist additions (extends E0/E1)

- [ ] **RBAC portfolio:** search, saved-view counts, triage, similar-project candidates all RBAC-filtered server-side — counts/rows never reveal inaccessible projects (BR-M1-001…005, BE-M1-002-2).
- [ ] **Existence-leak:** `GET/POST` project sub-resources via `require_project_access` → 404 (not 403) for unauthorized.
- [ ] **Upload guards (sources):** magic-byte MIME (DOCX/PDF/XLSX/MD/PPTX/TXT only), path-traversal-safe filename, size limit (`corpus_max_upload_mb` reuse / new `source_max_upload_mb`), SHA-256 dedup, malware scan before persist.
- [ ] **RU provenance:** every inferred claim carries a citation marker (source span or app-brain fact) — no orphan claims (BE-M1-012-5).
- [ ] **Generation gate:** downstream spec generation 409s unless `project.ru_validated` (BR-M1-012-3); validation action immutably audited with actor/timestamp + version snapshot.
- [ ] **No-orphan intake:** wizard cancel persists no project/document; staged blobs purged by Beat (BR-M1-006-3, BE-M1-006-2).
- [ ] **pgvector injection-safe:** project vector bound as `:vec` + `CAST(... AS vector(768))`, never interpolated.
- [ ] **Celery input validation:** `ingest_project_source` / `generate_requirement_understanding` validate UUID, log+return on bad input.
- [ ] **No prompt logging at INFO:** RU prompts (source text) not logged at INFO; only skill_name/project_id/span_count/latency.
- [ ] **Audit coverage:** project.created, source.uploaded/removed, malware_detected, understanding.generated/validated, reuse.selected — all emitted server-side.
- [ ] **Rate limits:** source upload 10/min, interview answer 20/min, project create 10/min.

---

## 12. Test plan

### Unit
- `test_parser_formats.py`: XLSX/PPTX/MD extract non-empty text; unsupported → error.
- `test_requirement_understanding_skill.py`: `SkillEngine.run("requirement_understanding", …, MockProvider())` → schema-valid; field_confidence covers all fields; open_questions present.
- `test_portfolio_query.py`: view predicates (mine/needs_review/stale/high_priority/finalized) select correct sets; search ILIKE 4 fields; group rollups sum.
- `test_quality_heuristics.py`: completeness scales with RU field coverage.

### Integration (real Postgres + Redis, mock LLM/embeddings)
- `test_project_wizard.py`: missing required field → 422; valid → 201 w/ human_id + RU(draft) + project_apps + reuse_selections + re-parented docs; cancel path leaves no project; staged file purge.
- `test_portfolio_api.py`: RBAC — non-member project absent from list/counts/search; `view=mine` vs `all`; `group_by=business_unit` groups; search intersects view.
- `test_source_ingest.py`: upload → `indexing_status` pending→done; `project_source_chunks` rows w/ embeddings; SHA-256 dup → 409.
- `test_apps_suggest_similar.py`: suggest flags relevant app; similar returns ≥1 candidate w/ match_pct + asset_tags; RBAC excludes inaccessible.
- `test_understanding_flow.py`: generate RU → in_interview + interview_messages + assumptions + interview gap_questions; answer → RU updates, new messages; validate → `ru_validated=true`, snapshot exists, audit row; pre-validate spec generate → 409; post-validate → allowed.
- `test_triage.py`: `recompute_triage` populates per-user items; RBAC-correct; `GET /api/triage` returns meta freshness; low-confidence assumption surfaces.

### e2e (Playwright)
- `portfolio.spec.ts`: search + clear; switch views (counts); table↔board preserves filters; group/collapse/reset; triage item click routes.
- `wizard.spec.ts`: 5-step nav back/fwd preserves inputs; required-field gating; apps suggested preselected; warn-if-none; upload shows states; cancel → not in portfolio; generate → interview.
- `interview.spec.ts`: AI/question/understanding bubbles; citations on claims; answer updates understanding; per-field confidence shown; validate unblocks generation; pre-validate generation disabled.

---

## 13. Done criteria + demo script

**Done:** all §1 acceptance rows pass (PII ACs of BR-M1-009 explicitly out of scope); §11 checklist green; CI (lint, typecheck, pytest unit+integration, Playwright, `pip-audit`) green; `0006` runs clean on fresh DB; seed creates PRJ-0001 (PayHub in scope, sample source ingested, RU generated).

**Demo:**
1. `alembic upgrade head` → `python seed_projects.py` → start API + worker + beat + frontend.
2. Log in as `analyst@specforge.test`. Dashboard: portfolio with PRJ-0001; switch saved views (counts change); search "PRJ-0001"; clear; toggle table↔board (filters preserved); group by business unit. Triage panel shows "Validate Understanding" item with freshness.
3. "New Project" → wizard: enter identity → see similar projects (toggle reuse) → apps-in-scope (PayHub AI-suggested, preselected; selected count) → upload a PDF (states pending→done) → Generate Understanding → routed to interview.
4. Interview: structured RU populated from source + PayHub facts; citation chips on inferred claims; per-field confidence bars; answer one open question → RU updates; click "Validate Understanding".
5. Back in workspace: stage map shows Requirement Understanding 100%/validated; generation actions now enabled; quality + sources + assumptions + activity panels populated.
6. Try generating a BRD/spec on an **unvalidated** project → blocked (409) with message; validate → allowed.
7. Log in as a non-member → PRJ-0001 absent from portfolio, search, triage; direct `/projects/{id}` → 404.
8. Show audit: project.created, source.uploaded, understanding.generated, understanding.validated.

---

## 14. Risks & open questions

- **PII out of scope (decided):** no PII detection, classification, or restricted-retrieval anywhere in SpecForge. Reason: requirements legitimately contain PII-like data an automatic detector cannot reliably distinguish, causing false restriction/blocking. BR-M1-009's PII acceptance criteria are dropped. E1's PII columns/filters removed in `0005_remove_pii`.
- **Malware scanning:** no real engine (overview §9 non-goal). Ships as a no-op `MalwareScanner` stub so the wire/audit exists; real scanner is an external integration later. Acceptance for BE-M1-009-2 is "wired + blocks on fail," demonstrated via stub returning not-clean in a test.
- **OCR:** image-only PDFs yield empty text; flagged `indexing_status='done'` w/ 0 chunks. Full OCR deferred. Note in source UI when extraction yields no text.
- **Staging-upload model:** chosen approach uploads to `StorageFile` (no `Document` until create) to guarantee no orphans; requires the daily purge sweep. Alternative (nullable `documents.project_id`) rejected to keep FK integrity.
- **Similar-project cold start:** with few finalized projects, discovery returns little. Threshold 0.5; show empty-state "no similar projects yet." Embeddings backfilled on create + validate.
- **IVFFlat on small corpora:** same caveat as E1 — consider HNSW if recall poor at dev scale.
- **Triage cadence:** 15-min Beat + on-demand fallback when empty. Confirm SLA; could switch to event-driven later (open question from PRD §10).
- **Quality subscores are heuristic** in E2; the real consistency/traceability engine lands in E4. UI should label them as preliminary.
- **Saved views are fixed** (6 named); custom user-defined views are a future iteration (PRD §10).
- **10-stage map:** only Requirement Understanding (E2) + BRD/FS/NFR (E3/E4) have real progress; ADR/TBP/SDD/TS/TC/Trace render "not started" until their modules ship.
```
