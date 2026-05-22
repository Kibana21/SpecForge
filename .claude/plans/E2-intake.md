# E2 — Project Intake & Requirement Understanding — Deep Plan (PageIndex corpus engine)

## Context

E2 turns a vague initiative into a **validated, structured Requirement Understanding (RU)** that gates downstream generation. A user lands in a real portfolio (search / saved views / table-board / triage), creates a project via a guided wizard (similar-project reuse → apps-in-scope → source intake), the sources are **ingested into a PageIndex reasoning tree**, an adaptive interview synthesizes a structured RU grounded in **reasoning-retrieved source sections + app-brain facts**, and the user validates the RU — the human-in-the-loop checkpoint that unblocks Module 2.

**What changed from the earlier E2 plan:** corpus ingestion + retrieval for project sources moves from **pgvector chunk-RAG → PageIndex** (VectifyAI), a *vectorless, reasoning-based* tree index. Confirmed decisions:
- **Self-host PageIndex OSS**, all LLM calls through **our Vertex/Gemini** (via LiteLLM `vertex_ai/...`). Docs never leave our infra.
- **E2 project sources only** — E1's app-brain corpus (`app_chunks`, pgvector) is untouched.
- **Pure reasoning tree-search** — no source embeddings. Embeddings (`project_embeddings`, pgvector) are kept **only** for project/app similarity.

**Tier-1:** [`00-foundations-and-decisions.md`] · **Roadmap:** [`01-master-roadmap.md`] · **Reqs:** [`../prd/prd-module-1-dashboard-project-hub.md`]
**Binding skills:** `spec-forge-security`, `postgres`, `langchain-gemini`.
**Model guidance:** Sonnet for most; Opus for the corpus engine (T6–T8), RU orchestrator/interview (T18–T20), triage (T15).

**PII is out of scope** (project-wide decision; E1 columns removed in `0005_remove_pii`). BR-M1-009 PII acceptance criteria are dropped.

---

## What PageIndex is (and why it fits)

PageIndex builds a **hierarchical tree** of a document (a TOC of nodes: `{node_id, title, summary, start_index, end_index, nodes[]}`) using an LLM to detect structure + summarize sections. Retrieval is **LLM tree-navigation**: given a query, the LLM reasons over node titles+summaries to pick the relevant nodes (like a human using a table of contents), then we fetch only those nodes' text. No embeddings, no chunking, traceable to section + page range. Ideal for the long, structured docs SpecForge ingests (business cases, specs, manuals).

**Facts that drive the design (from research):**
- OSS is **PDF + Markdown only**. Other formats must be converted first.
- It uses **LiteLLM** → supports **Vertex AI Gemini** (`vertex_ai/gemini-2.5-flash`) with GCP creds; `litellm.drop_params=True` smooths unsupported-param differences. No official Gemini example exists → we validate this early (T6 spike).
- Index building is **LLM-heavy** (~20–50 calls / 50-page doc) → Celery, long timeout, retries, cost note.
- We implement **retrieval ourselves** with our existing Gemini provider (the OSS gives the tree + tools).

---

## Architecture: a swappable corpus-index provider (mirrors `embeddings`/`llm`)

New abstraction `app/services/corpus_index/` so PageIndex is isolated behind an interface (swappable, mockable in CI — exactly like `EmbeddingProvider`/`LLMProvider`):

```
app/services/corpus_index/
├── base.py              # CorpusIndexProvider ABC + dataclasses (DocTree, RetrievedSection)
├── pageindex_provider.py# real: build via PageIndex+LiteLLM/Vertex; tree_search via our Gemini
├── mock_provider.py     # fixture tree + deterministic node selection (no LLM/network)
└── __init__.py          # get_corpus_index_provider()  → Mock when settings.llm_provider == "mock"
```

```python
# base.py
@dataclass
class DocTree:           # result of build_index
    tree: dict          # PageIndex tree JSON (nodes: node_id,title,summary,start_index,end_index,nodes[])
    page_texts: dict     # {page_no(str): text}  — for fetching node text by page range
    node_count: int
    model: str

@dataclass
class RetrievedSection:
    document_id: uuid.UUID; doc_name: str; node_id: str
    title: str; page_start: int; page_end: int; text: str; reason: str

class CorpusIndexProvider(ABC):
    @abstractmethod
    async def build_index(self, *, data: bytes, content_type: str, filename: str) -> DocTree: ...
    @abstractmethod
    async def tree_search(self, *, query: str, docs: list[IndexedDoc], top_k: int) -> list[RetrievedSection]: ...
```

- **build_index** (pageindex impl): if PDF → PageIndex PDF path; if MD → MD path; else extract text via existing `parser.parse` → wrap as Markdown → MD path. Runs PageIndex with LiteLLM configured for Vertex (reusing our service account). Returns tree + per-page text.
- **tree_search** (pageindex impl): flatten in-scope docs' trees into a compact outline (`[doc] node_id · title — summary`), call the **`source_tree_search` skill** (our Gemini via `SkillEngine`) → returns selected `{document_id, node_id, reason}`; we slice `page_texts[start..end]` → `RetrievedSection`. This is the reasoning retrieval.
- **mock impl**: returns a small fixture tree on build; on search returns the first N fixture sections — keeps CI free of LLM/PageIndex.

**LiteLLM↔Vertex bridge** (`pageindex_provider`): set `litellm` params from existing settings — `vertex_project=gemini_project_id`, `vertex_location=gemini_location`, `vertex_credentials=google_service_account_path`, `model=settings.pageindex_model` (default `vertex_ai/gemini-2.5-flash`), `litellm.drop_params=True`. One service account, reused.

**Python/dep note:** add `litellm` + PageIndex OSS. Prefer `pip install git+https://github.com/VectifyAI/PageIndex` (MIT) or vendor its `page_index()` module — avoids `pageindex-open`'s Python 3.12 requirement (our backend targets 3.11+). **T6 is a spike to confirm PageIndex+Vertex works on our runtime before building on it.**

---

## 1. BRs covered & acceptance mapping
(unchanged from prior plan — BR-M1-001…012). Corpus-relevant rows:
| BR | Title | Verified in E2 by |
|---|---|---|
| BR-M1-009 | Source Document Intake | extended `documents` + `ingest_project_source` → **PageIndex tree** in `document_trees`; states polled; delete pre-gen (PII ACs dropped) |
| BR-M1-012 | Adaptive Requirement Understanding | RU grounded via **reasoning tree-search** over in-scope trees + app facts; `requirement_understanding` skill; `interview_messages`; `ru_validated` gate; audited |
(Portfolio/wizard/triage/workspace rows BR-M1-001…008,010,011 unchanged.)

## 2. Dependencies
- **E0 + E1 complete.** Reuse `get_current_user`/`require_role`/`require_project_access`, `audit.emit`, `SkillEngine`, `get_provider` (Gemini/Vertex), `get_embedding_provider`, `version_service`, `ok()/err()`, `limiter`, Celery+Beat, `StorageFile/StorageFileBlob`, `apps`/`app_facts`.
- **Existing scaffolding to extend:** `projects`/`project_members`, `documents`(+`parser`), `gap_questions`, `Project` CRUD, `/projects/[id]` workspace.
- **New deps:** `litellm`, PageIndex OSS (git/vendored). Optional converters for non-PDF→MD reuse existing `parser`. Alembic through `0005`; new migration `0006`.

---

## 3. Data model & migration `0006_project_intake.py`

**ALTER `projects`** (portfolio + intake): `human_id` (uniq, "PRJ-0001"), `business_unit`, `app_scope`, `status` (draft|active|in_review|finalized|archived), `priority`, `completion_pct`, `go_live_date`, `stage_progress` JSONB, `ru_validated` BOOL. Indexes on status/business_unit; unique human_id.

**ALTER `documents`** (source intake state): `indexing_status` (pending|running|done|error), `index_error`, `page_count`, `sha256`. Index `(project_id, sha256)`.

**NEW `document_trees`** — PageIndex tree store (replaces `project_source_chunks`):
```sql
CREATE TABLE document_trees (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  tree_json   JSONB NOT NULL,            -- hierarchical nodes (node_id,title,summary,start_index,end_index,nodes[])
  page_texts  JSONB NOT NULL,            -- {"1":"...", "2":"..."} for node-text fetch by page range
  node_count  INTEGER NOT NULL DEFAULT 0,
  model       VARCHAR(100),              -- LLM that built it
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_document_trees_project ON document_trees (project_id);
```

**NEW** (unchanged from prior plan): `project_apps`, `requirement_understanding`, `interview_messages`, `assumptions`, `reuse_selections`, `project_embeddings` (pgvector, similarity only), `triage_items`. **ALTER `gap_questions`** add section/due_date/assignee_id/source. (Full DDL identical to prior E2 plan §3.3–3.11, minus `project_source_chunks`.)

**Models:** extend `Project`/`Document`/`GapQuestion`; add `ProjectApp`, `RequirementUnderstanding`, `InterviewMessage`, `Assumption`, `ReuseSelection`, `ProjectEmbedding`, `TriageItem`, `DocumentTree`. Split per-domain (`app/models/understanding.py`, `app/models/project_source.py` for `DocumentTree`). Update `models/__init__.py`.

---

## 4. API contracts (unchanged from prior plan except retrieval internals)
- `GET /api/projects` (search/view/group_by, RBAC), `GET /api/projects/views`, `POST /api/projects` (wizard, atomic, dispatch ingest + RU), `GET /api/projects/{id}` (workspace detail), `GET /api/projects/{id}/similar`, `GET /api/apps/suggest`, source intake (`POST/GET/DELETE …/documents` + staging upload `POST /api/projects/staging/documents`), interview (`GET …/understanding`, `POST …/understanding/answer`, `POST …/understanding/validate`), `GET /api/triage`, assumptions. **Generation gate:** `require_ru_validated` dep wired into `specs.py` generate endpoints (409 until validated). See prior plan §4 for full request/response shapes — unchanged.

---

## 5. Background jobs (`workers/tasks.py`)

### 5.1 `ingest_project_source(document_id)` — **PageIndex build**
Validate UUID; load `Document`; `indexing_status='running'`; load bytes from `StorageFile`; **`tree = await get_corpus_index_provider().build_index(data, content_type, filename)`** (PDF→PDF path; DOCX/XLSX/PPTX/TXT→`parser.parse`→Markdown→MD path); upsert `document_trees` (tree_json, page_texts, node_count, model); set `page_count`, `indexing_status='done'`. On error → `error` + `index_error`. **`max_retries=3`, `time_limit` generous** (indexing is slow). Dispatch nothing else (RU is triggered separately). Cost/latency noted in §14.

### 5.2 `generate_requirement_understanding(project_id)`
1. If any source `pending`/`running` → re-queue (countdown 10s, bounded) so RU sees finished trees but the wizard isn't blocked.
2. **Reasoning retrieval:** load in-scope `document_trees` for the project → `sections = await corpus_index.tree_search(query=<objective probe>, docs, top_k)`; load included `app_facts` (via `project_apps`).
3. Run `requirement_understanding` skill (sections + app facts) → structured RU + per-field confidence + open_questions + assumptions + citations (citations now reference **doc + section title + page range**).
4. Persist RU (`in_interview`), `interview_messages`, `assumptions`, `gap_questions(source='interview')`; `audit.emit("understanding.generated", model, refs)`.

### 5.3 `recompute_triage()` (Beat, 15m) and 5.4 `purge_orphan_staging_files()` (Beat, daily) — unchanged from prior plan. Beat entries added in `celery_app.py`.

---

## 6. New services
- `app/services/corpus_index/*` — the provider abstraction (§Architecture).
- `app/services/storage/malware_scanner.py` — no-op `MalwareScanner` stub (wired into upload; real engine deferred).
- `app/services/portfolio/query_service.py` (search+view+group_by) and `triage_service.py`.
- `app/services/understanding/orchestrator.py` — `generate()` + `incorporate_answer()` wrap tree-search + `SkillEngine` + persistence (stateless re-synthesis each turn).
- `app/services/quality/quality_service.py` — heuristic subscores.
- `app/services/projects/embedding_service.py` — `upsert_project_embedding` (name+desc+RU.objective → `project_embeddings`) for similar/app-suggest.

## 7. Skills
- **`requirement_understanding`** (new) — synthesize structured RU from retrieved sections + app facts + prior Q&A; per-field confidence; `[S#]`/`[F#]` citations; ask only un-inferable questions. Schema as prior plan §7. Mock fixture + `_SKILL_FIXTURE_MAP`.
- **`source_tree_search`** (new) — input: query + flattened forest of in-scope trees (`[doc] node_id · title — summary`); output JSON `{selections:[{document_id, node_id, reason}]}` (schema-validated by SkillEngine). Powers `tree_search`. Mock fixture returns deterministic node ids.

## 8. Pydantic schemas
`project.py` (extend: ProjectCreate +business_unit/app_scope/app_ids/reuse/document_ids; ProjectListItem full projection; ProjectDetail panels), `understanding.py`, `app_scope.py` (AppSuggestion/SimilarProject/ProjectAppRead), `triage.py`, `assumption.py`, `document.py` (+indexing_status/index_error/page_count/sha256). Citations carry `{doc_name, section_title, page_start, page_end}`.

## 9. Frontend (unchanged from prior plan)
Portfolio (toolbar/table/board/group/triage), 5-step wizard (`/projects/new`), workspace (`StageMap` + operational panels; generation actions disabled until `ru_validated`), adaptive interview (`/projects/[id]/interview`: thread, understanding panel, answer composer, validate bar). `lib/api.ts` + hooks additions. Source rows show extract/index state; **citations show section title + page range** (richer than chunk_no). See prior plan §9.

---

## 10. Ordered work breakdown

### Phase 1 — Data + migration
- **T1.** Migration `0006` (ALTER projects/documents/gap_questions; CREATE document_trees + project_apps/requirement_understanding/interview_messages/assumptions/reuse_selections/project_embeddings/triage_items). `downgrade()`.
- **T2.** Models + `models/__init__.py`. **T3.** Pydantic schemas.

### Phase 2 — Corpus engine (PageIndex) ★ the new core
- **T4.** Add `litellm` + PageIndex OSS to `requirements.txt`; config: `corpus_index_provider`, `pageindex_model` (`vertex_ai/gemini-2.5-flash`).
- **T5.** Extend `parser.parse` for XLSX/PPTX/MD → text (for the non-PDF→Markdown bridge).
- **T6. (spike, Opus)** `CorpusIndexProvider` ABC + `PageIndexProvider.build_index` wired to **Vertex via LiteLLM**; prove a real PDF builds a tree on our runtime (Python compat, creds, drop_params). De-risks the whole epic.
- **T7.** `PageIndexProvider.tree_search` + `source_tree_search` skill; `MockCorpusIndexProvider` (fixture tree + selection); `get_corpus_index_provider()` factory.
- **T8.** `ingest_project_source` task (build → `document_trees`); `MalwareScanner` stub + upload wiring; extend `POST/GET/DELETE …/documents` (MIME incl. PDF/DOCX/XLSX/MD/PPTX/TXT, SHA-256 dedup, states, dispatch, audit); staging upload + `purge_orphan_staging_files` Beat.

### Phase 3 — Apps-in-scope + similar discovery
- **T9.** `embedding_service` + `project_embeddings`. **T10.** `GET /api/apps/suggest`. **T11.** `GET …/similar` + `reuse_selections`. **T12.** `project_apps` persistence + app-brain context loader for RU.

### Phase 4 — Portfolio + triage
- **T13.** `portfolio/query_service`. **T14.** Extend `GET /api/projects` + `GET /api/projects/views`. **T15.** `triage_service` + `triage_items` + `GET /api/triage` + `recompute_triage` Beat. *(Opus)*

### Phase 5 — Wizard create + RU
- **T16.** Extend `POST /api/projects` (atomic, human_id, dispatch ingest + RU). **T17.** `requirement_understanding` skill (+mock). **T18.** `understanding/orchestrator` + `generate_requirement_understanding` (uses `tree_search`). *(Opus)* **T19.** `GET …/understanding`, `POST …/answer`. *(Opus)* **T20.** `POST …/validate` gate + snapshot + `require_ru_validated` wired into `specs.py`. *(Opus)*

### Phase 6 — Workspace aggregation + quality
- **T21.** `quality_service` + stage_progress. **T22.** Extend `GET /api/projects/{id}` detail + assumptions endpoints. **T23.** Seed `PRJ-0001` (PayHub in scope, sample PDF → tree, RU generated) via `seed_projects.py` with `LLM_PROVIDER=mock` (mock corpus provider → fixture tree, no real PageIndex calls).

### Phase 7 — Frontend
- **T24.** types + `api.ts` + hooks. **T25.** Portfolio. **T26.** Wizard. **T27.** Workspace + gate. **T28.** Interview (citations show section/page).

---

## 11. Security checklist additions (extends E0/E1)
- [ ] **RBAC** on portfolio/views/triage/similar — counts/rows never reveal inaccessible projects; `require_project_access` (404 leak-safe) on sub-resources.
- [ ] **Upload guards:** magic-byte MIME (PDF/DOCX/XLSX/MD/PPTX/TXT), path-safe filename, size limit, SHA-256 dedup, malware scan before persist.
- [ ] **PageIndex/Vertex secrets:** LiteLLM uses our existing service-account path; **never log document text or full prompts at INFO** (only doc_id/node_count/latency); credentials never in responses.
- [ ] **Self-host = no third-party egress:** source bytes/trees stay in our DB (PageIndex Cloud explicitly NOT used).
- [ ] **RU provenance:** every inferred claim cites a tree section (doc + node + page) or app fact — no orphan claims.
- [ ] **Generation gate:** spec generation 409s unless `project.ru_validated`; validation audited + version-snapshotted.
- [ ] **No-orphan intake:** wizard cancel persists nothing; staged blobs purged by Beat.
- [ ] **Celery input validation** (UUID), **rate limits** (upload 10/min, answer 20/min, create 10/min), **audit coverage** (project.created, source.uploaded/removed, source.indexed, understanding.generated/validated, reuse.selected).

## 12. Test plan
**Unit:** `test_parser_formats` (XLSX/PPTX/MD); `test_mock_corpus_index` (build returns tree; tree_search returns sections deterministically); `test_requirement_understanding_skill` + `test_source_tree_search_skill` (schema-valid via MockProvider); `test_portfolio_query`; `test_quality_heuristics`.
**Integration (real PG+Redis, mock LLM + mock corpus provider):** `test_project_wizard` (422/201/cancel/purge); `test_portfolio_api` (RBAC/views/group); `test_source_ingest` (upload → `indexing_status` pending→done, `document_trees` row present, node_count>0; SHA-256 dup→409); `test_apps_suggest_similar`; `test_understanding_flow` (generate RU from tree-search → in_interview + messages + assumptions; answer updates; validate → `ru_validated`+snapshot+audit; pre-validate spec gen→409, post→allowed); `test_triage`.
**Live (opt-in, `@pytest.mark.slow`):** `test_pageindex_vertex` — real PDF → real Gemini tree build (excluded from default CI; validates the Vertex bridge).
**e2e (Playwright):** `portfolio.spec` / `wizard.spec` / `interview.spec` (citations show section+page).

## 13. Done criteria + demo
**Done:** §1 acceptance pass (PII ACs out of scope); §11 green; CI (lint/type/pytest unit+integration/Playwright/pip-audit) green with the **mock corpus provider** (no real PageIndex in CI); `0006` clean on fresh DB; seed builds PRJ-0001.
**Demo:** login → portfolio (views/search/board/group + triage) → wizard (identity → similar/reuse → apps-in-scope PayHub suggested → upload a **real PDF**) → ingestion shows pending→done (**PageIndex tree built via Vertex**) → routed to interview → RU populated with **section/page citations** from reasoning tree-search + PayHub facts → answer a question → **Validate** → workspace stage map shows RU validated, generation unblocked → pre-validate generation 409 → non-member sees nothing (404).

## 14. Risks & open questions
- **PageIndex + Vertex is "pioneering"** (no official Gemini example). **T6 spike de-risks it first.** Fallbacks if blocked: (a) LiteLLM OpenAI-compatible Gemini endpoint; (b) re-implement minimal tree-build with our Gemini provider; (c) last resort PageIndex Cloud (rejected for data residency).
- **Python compat:** `pageindex-open` needs 3.12; prefer the MIT GitHub `page_index()` via git-install/vendor on our 3.11 runtime. Confirm in T6.
- **Indexing cost/latency:** ~20–50 Gemini calls per 50-page doc → slow + token cost. Mitigate: Celery with long `time_limit`, retries, per-doc status UI; cap doc size; cache by `sha256` (reuse tree if same file already indexed). CI uses mock provider (zero calls).
- **Non-PDF structure loss:** DOCX/XLSX/PPTX/TXT go through a text→Markdown bridge, so the tree is weaker than for native PDFs. PDF is the first-class path; note in source UI.
- **Tree-search recall:** reasoning retrieval can miss content if summaries are thin. Mitigate: include node titles+summaries+page hints; allow top_k expansion; the interview's open-questions cover residual gaps.
- **PII out of scope; malware no-op stub; quality heuristic; saved views fixed; 10-stage map only RU/BRD/FS/NFR real** — as prior plan.
- **Embeddings retained only for project/app similarity** (`project_embeddings`); app-brain corpus (E1) stays on pgvector (separate decision if we later unify on PageIndex).
