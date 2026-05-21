# E1 — AI Infrastructure & App Brain Core — Deep Plan

**Goal:** Build the generation substrate for SpecForge. A user can register an enterprise application, upload corpus documents, trigger the ingestion pipeline (parse → chunk → embed → extract facts), and interactively ask "the app brain" a question and receive a streaming, cited RAG answer. LLM provider configuration is abstracted and credential-safe. PII detection governs what gets indexed and retrieved. Every material action is audited and RBAC-enforced.

**Tier-1 decisions:** [`00-foundations-and-decisions.md`](00-foundations-and-decisions.md) · **Roadmap:** [`01-master-roadmap.md`](01-master-roadmap.md)
**Binding skills:** `spec-forge-security` (auth/RBAC/API security), `postgres` (models/migrations/queries).

**Model guidance:** Implement on **Sonnet** for most tasks; escalate to **Opus** for the RAG retrieval service (T13–T15), the SSE streaming endpoint (T16), and the PII detection logic (T6). Switch with `/model`.

---

## Scope boundary for E1

| Built fully in E1 | Skeleton only — full data from later epic |
|---|---|
| App registry CRUD, app brain data model, corpus upload + ingestion pipeline, pgvector embedding store, fact extraction, permission-filtered RAG retrieval, `/ask` SSE streaming endpoint, `fact_extractor` and `app_brain_qa` skills, PII detection, LLM provider config additions | App-brain grounding injected into BRD/FS generation (E3), proposed-updates governance (E5), app onboarding queue UI beyond skeleton (E5) |

---

## 1. BRs covered & acceptance mapping

| BR | Title | Key acceptance criteria | Verified in E1 by |
|---|---|---|---|
| BR-M4-001 | Application Registry | List/search all apps; health signal badges; tier/owner visible | `GET /api/apps` returns filtered list; search by name; tier badge in UI |
| BR-M4-002 | App Onboarding Queue (Should) | Apps not yet onboarded appear in a queue; status transitions | `is_onboarded=false` apps appear in queue tab; status visible |
| BR-M4-003 | App Brain Detail | Facts, corpus docs, pipeline steps, constraints, integrations visible per app | `GET /api/apps/{id}` returns full detail; brain detail page renders all sections |
| BR-M4-004 | Pipeline Transparency | Ingest/extract/synthesize step counts and status per doc and per app | `index_status` per corpus doc; pipeline summary returned in app detail |
| BR-M4-005 | Corpus Management | Upload docs to app corpus; re-index triggers fresh embedding pass | `POST /api/apps/{id}/corpus` creates doc + dispatches Celery task; `POST /api/apps/{id}/reindex` works |
| BR-M4-006 | Ask the App Brain | Streaming RAG answer with citation chips; question logged; PII-filtered | `POST /api/apps/{id}/ask` returns SSE stream; citation IDs in final event; unauthorized user cannot see restricted chunks |
| BR-M4-010 | LLM Provider Config | Provider abstraction; keys from env/secrets; never in client state | `embedding_provider` setting; keys excluded from all API responses; `MockEmbeddingProvider` works in dev |
| BR-M4-011 | Data Security + PII | PII detected during ingestion; `pii_detected=true` blocks retrieval for unauthorized users; classification restricts facts | Ingestion sets `pii_detected`; `/ask` enforces classification filter; audit event on retrieval attempt |

---

## 2. Dependencies (what must already exist)

- **E0 complete:** FastAPI app factory, `get_current_user`/`require_role` deps, `audit.emit`, `StorageFile`/`StorageFileBlob` models (files/file_blobs tables), `VersionSnapshot`, Celery + Redis wired, `SkillEngine`, `GeminiProvider`/`MockProvider`, `LLMProvider` ABC, `TimestampMixin`/`uuid_pk` base patterns, `ok()`/`err()` envelope, Alembic through migration `0003`.
- **pgvector Postgres extension:** Already installed in Postgres (E0 docker-compose); Python package `pgvector` NOT yet installed — must be added to `requirements.txt`.
- **New Python packages to add:** `pgvector`, `tiktoken`, `presidio-analyzer`, `presidio-anonymizer`. Pin versions.
- **Vertex AI embedding access:** Same service account used for `GeminiProvider` must have `aiplatform.endpoints.predict` IAM permission on `text-embedding-004`.

---

## 3. Data model & migrations

### Migration `0004_app_brain.py` — single migration for all E1 tables

The migration must run `CREATE EXTENSION IF NOT EXISTS vector` before creating tables (safe if already enabled).

#### 3.1 `apps` table

```sql
CREATE TABLE apps (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    short_name   VARCHAR(50)  NOT NULL,
    description  TEXT,
    tier         INTEGER      NOT NULL CHECK (tier BETWEEN 1 AND 3),
    owner_id     UUID         REFERENCES users(id) ON DELETE SET NULL,
    is_onboarded BOOLEAN      NOT NULL DEFAULT false,
    version      VARCHAR(50),
    domain_area  VARCHAR(100),
    rebuild_status VARCHAR(20),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_apps_short_name ON apps (lower(short_name));
CREATE INDEX idx_apps_owner_id ON apps (owner_id);
CREATE INDEX idx_apps_tier ON apps (tier);
```

SQLAlchemy model: `App(TimestampMixin, Base)` in `app/models/app.py`. `tier` uses `CheckConstraint("tier BETWEEN 1 AND 3", name="ck_apps_tier")`. `rebuild_status` is plain `String(20)` nullable — values `"rebuilding"` or `None`. Relationships: `members` (list `AppMember`), `corpus_docs` (list `AppCorpusDoc`), `facts` (list `AppFact`).

#### 3.2 `app_members` table

```sql
CREATE TABLE app_members (
    app_id   UUID        NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    user_id  UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind     VARCHAR(20) NOT NULL DEFAULT 'delegate' CHECK (kind IN ('owner', 'delegate')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (app_id, user_id)
);
CREATE INDEX idx_app_members_user_id ON app_members (user_id);
```

SQLAlchemy model: `AppMember(Base)` with composite PK `(app_id, user_id)`. `kind` as `String(20)` with `CheckConstraint`.

#### 3.3 `app_corpus_docs` table

```sql
DO $$ BEGIN
    CREATE TYPE index_status_enum AS ENUM ('pending', 'running', 'done', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE app_corpus_docs (
    id             UUID               PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id         UUID               NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    file_id        UUID               NOT NULL REFERENCES files(id) ON DELETE RESTRICT,
    name           VARCHAR(500)       NOT NULL,
    page_count     INTEGER,
    is_primary     BOOLEAN            NOT NULL DEFAULT false,
    pii_detected   BOOLEAN            NOT NULL DEFAULT false,
    classification VARCHAR(50)        NOT NULL DEFAULT 'internal',
    indexed_at     TIMESTAMPTZ,
    index_status   index_status_enum  NOT NULL DEFAULT 'pending',
    index_error    VARCHAR(1000),
    created_at     TIMESTAMPTZ        NOT NULL DEFAULT now()
);
CREATE INDEX idx_app_corpus_docs_app_id ON app_corpus_docs (app_id);
CREATE INDEX idx_app_corpus_docs_file_id ON app_corpus_docs (file_id);
CREATE INDEX idx_app_corpus_docs_index_status ON app_corpus_docs (index_status);
```

SQLAlchemy model: `AppCorpusDoc(Base)` in `app/models/corpus.py`. `index_status` mapped as `Enum("pending","running","done","error", name="index_status_enum", create_type=False)`. Relationship: `chunks` list of `AppChunk` with `cascade="all, delete-orphan"`.

#### 3.4 `app_chunks` table

```sql
CREATE TABLE app_chunks (
    id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id     UUID    NOT NULL REFERENCES app_corpus_docs(id) ON DELETE CASCADE,
    chunk_no   INTEGER NOT NULL,
    text       TEXT    NOT NULL,
    embedding  vector(768),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_no)
);
CREATE INDEX idx_app_chunks_doc_id ON app_chunks (doc_id);
CREATE INDEX idx_app_chunks_embedding_ivfflat
    ON app_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

SQLAlchemy model: `AppChunk(Base)` in `app/models/corpus.py`. `embedding` column uses `pgvector.sqlalchemy.Vector(768)`. The `(doc_id, chunk_no)` unique constraint enforces idempotent re-ingestion (delete existing chunks first on re-index). No `TimestampMixin` — only `created_at`.

**IVFFlat notes:** `lists=100` suitable for corpora up to ~1M chunks. At query time use `SET ivfflat.probes = 10` for recall/speed balance. Run `ANALYZE app_chunks` after bulk insert (Celery task does this).

#### 3.5 `app_facts` table

```sql
DO $$ BEGIN
    CREATE TYPE fact_kind_enum AS ENUM ('capability','constraint','limitation','integration','gotcha');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    CREATE TYPE fact_confidence_enum AS ENUM ('high','medium','low');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
DO $$ BEGIN
    CREATE TYPE fact_status_enum AS ENUM ('active','proposed','dismissed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE app_facts (
    id          UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id      UUID                NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    kind        fact_kind_enum      NOT NULL,
    text        TEXT                NOT NULL,
    source_ref  VARCHAR(255),
    confidence  fact_confidence_enum NOT NULL DEFAULT 'medium',
    status      fact_status_enum    NOT NULL DEFAULT 'active',
    chunk_ids   JSONB               NOT NULL DEFAULT '[]',
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ         NOT NULL DEFAULT now()
);
CREATE INDEX idx_app_facts_app_id ON app_facts (app_id);
CREATE INDEX idx_app_facts_kind ON app_facts (kind);
CREATE INDEX idx_app_facts_status ON app_facts (status);
CREATE INDEX idx_app_facts_chunk_ids_gin ON app_facts USING gin (chunk_ids);
```

SQLAlchemy model: `AppFact(TimestampMixin, Base)` in `app/models/fact.py`. `kind`, `confidence`, `status` all mapped as `Enum(..., create_type=False)`. `chunk_ids` mapped as `JSONB`.

#### 3.6 Model file layout

- `backend/app/models/app.py` — `App`, `AppMember`
- `backend/app/models/corpus.py` — `AppCorpusDoc`, `AppChunk`
- `backend/app/models/fact.py` — `AppFact`
- Update `backend/app/models/__init__.py` to import all new models.

---

## 4. API contracts

All under `/api/apps`. Auth minimum `Depends(get_current_user)`. Errors via standard `err()` envelope. Status discipline: 401/403/404 as per E0.

### 4.1 `GET /api/apps`

**Auth:** All authenticated. Platform admins see all apps. Others see `is_onboarded=true` apps OR apps where they are `owner`/`delegate` in `app_members`.

**Query params:** `q` (ILIKE search on name/short_name), `tier` (1/2/3), `mine` (bool), `limit` (default 50, max 100), `offset` (default 0).

**Response `200`:**
```json
{
  "data": [{
    "id": "uuid", "name": "PayHub", "short_name": "payhub",
    "description": "...", "tier": 1, "domain_area": "payments",
    "is_onboarded": true, "version": "3.2.1", "owner_id": "uuid",
    "corpus_doc_count": 4, "indexed_doc_count": 3,
    "fact_count": 12, "has_pii": false,
    "created_at": "...", "updated_at": "..."
  }],
  "error": null,
  "meta": {"total": 1, "limit": 50, "offset": 0}
}
```

`corpus_doc_count`, `indexed_doc_count` (where `index_status='done'`), `fact_count` (where `status='active'`), `has_pii` (any corpus doc with `pii_detected=true`) — computed via correlated scalar subqueries.

### 4.2 `POST /api/apps`

**Auth:** `require_role("platform_admin")`.

**Request body:**
```json
{"name": "PayHub", "short_name": "payhub", "description": "...", "tier": 1, "domain_area": "payments", "version": "3.2.1"}
```

**Validation:** `name` non-empty; `short_name` matches `^[a-z0-9-]{1,50}$` — 422 on violation; unique (409 `short_name_conflict` on duplicate); `tier` 1-3. `owner_id` defaults to caller's `user.id`.

**Response `201`:** Full `AppDetail` object.

**Audit:** `audit.emit(event="app.created", actor_id=..., metadata={"app_id": ..., "short_name": ...})`.

### 4.3 `GET /api/apps/{app_id}`

**Auth:** platform_admin OR app owner/delegate OR `is_onboarded=true` for any authenticated user. Return 404 for both not-found and unauthorized non-onboarded apps (existence-leak prevention).

**Response `200`:** Full detail including `corpus_docs` (selectin), `facts` (selectin, PII-filtered for non-privileged), `pipeline_summary` (aggregated from DB).

Facts PII filter for non-privileged callers: exclude facts where any `chunk_id` in `chunk_ids` belongs to a doc with `pii_detected=true`. Practical: store `classification` denormalized on `AppFact` (populated during extraction from source doc), filter by `classification='internal'` for non-admin/non-owner callers.

### 4.4 `POST /api/apps/{app_id}/corpus`

**Auth:** `require_app_write_access` (platform_admin OR owner/delegate).

**Request:** `multipart/form-data`: `file` (UploadFile), `is_primary` (bool, default false).

**Processing:**
1. Validate magic-byte MIME via `storage.detect_mime` — only PDF/DOCX/TXT allowed.
2. SHA-256 dedup: if `files.sha256` already exists for this app's corpus → 409 `duplicate_document`.
3. Persist bytes to `StorageFile` + `StorageFileBlob` (reuse E0 storage abstraction).
4. Create `AppCorpusDoc` with `index_status='pending'`.
5. Dispatch `tasks.ingest_corpus_doc.delay(str(doc.id))`.
6. Audit: `audit.emit(event="corpus.doc.uploaded", ...)`.
7. Return `AppCorpusDocRead` with 202.

**Rate limit:** `@limiter.limit("10/minute")`.

### 4.5 `POST /api/apps/{app_id}/reindex`

**Auth:** `require_app_write_access`.

**Guard:** If `App.rebuild_status == 'rebuilding'` → 409 `rebuild_in_progress`.

**Processing:** Set `rebuild_status='rebuilding'`, commit. Dispatch `tasks.rebuild_app_brain.delay(str(app_id))`. Return 202 with `{"task_id": "..."}`.

**Audit:** `audit.emit(event="app.reindex.triggered", ...)`.

### 4.6 `GET /api/apps/{app_id}/facts`

**Auth:** Authenticated + `require_app_access`.

**Query params:** `kind` (enum), `status` (enum, default `active`), `confidence` (enum), `limit`/`offset`.

**PII filter:** same as app detail — exclude facts from PII docs for non-privileged callers.

**Response `200`:** Paginated list of `AppFactRead`.

### 4.7 `POST /api/apps/{app_id}/ask`

**Auth:** `require_app_access`. **Rate limit:** `@limiter.limit("20/minute")`.

**Request body:**
```json
{"question": "What payment protocols does PayHub support?", "top_k": 8}
```
`top_k` default 8, max 20. `question` max 1000 chars.

**Response:** `text/event-stream` SSE. Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

SSE event format:
```
data: {"type": "chunk", "text": "PayHub supports "}

data: {"type": "chunk", "text": "ISO 20022 settlement."}

data: {"type": "citations", "citations": [
  {"id": "uuid1", "doc_name": "PayHub Architecture v2.pdf", "chunk_no": 14, "text_excerpt": "PayHub implements ISO 20022..."}
]}

data: {"type": "done"}
```

On error: `data: {"type": "error", "message": "No indexed content found."}`

**Processing flow:**
1. Embed question via `EmbeddingProvider.embed(question)`.
2. `RAGRetrievalService.retrieve(app_id, question, top_k, caller_is_privileged, db)` — pgvector cosine similarity, PII/classification filter, similarity threshold ≥ 0.3.
3. If no chunks → yield error event, return.
4. Render `app_brain_qa` skill prompt via `SkillEngine._render_prompt(...)`.
5. Stream via `LLMProvider.astream(prompt, system)` — yield `chunk` events per token.
6. After stream complete → yield `citations` event, then `done`.
7. Audit: `audit.emit(event="app.brain.ask", metadata={"question_hash": sha256(question), "chunk_count": N})` — question hashed, NOT stored plaintext.

**FastAPI SSE pattern:**
```python
from fastapi.responses import StreamingResponse

@router.post("/{app_id}/ask")
async def ask_app_brain(app_id: UUID, body: AskRequest, ...):
    async def event_generator():
        async for event in rag_service.stream_answer(...):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

---

## 5. Background jobs

All in `backend/workers/tasks.py`. Celery tasks call `asyncio.run(_async_impl())` following E0 pattern.

### 5.1 `tasks.ingest_corpus_doc(doc_id: str)`

**Trigger:** `POST /api/apps/{id}/corpus`.

**Steps:**
1. Validate `UUID(doc_id)` — if invalid, log and return without processing.
2. Load `AppCorpusDoc`. Set `index_status='running'`. Commit.
3. Load bytes from `StorageFile` + `StorageFileBlob`.
4. Parse bytes using existing `app/services/documents/parser.py`. Count pages (`fitz.open()` for PDF, `1` for DOCX/TXT). Set `page_count`.
5. **PII detection:** `PiiDetector().detect(text)`. If `True` → `pii_detected=True`, `classification='restricted'`.
6. **Chunking:** `chunk_text(text, max_tokens=512, overlap_tokens=64)` → list of strings.
7. **Embedding:** `EmbeddingProvider.embed_batch(chunk_texts)` → list of 768-dim float lists. Batched in groups of 250 (Vertex AI limit).
8. **Store chunks:** Delete existing `AppChunk` for this `doc_id`. Bulk-insert new rows with embeddings. Execute `ANALYZE app_chunks` (via `db.execute(text("ANALYZE app_chunks"))`).
9. Set `index_status='done'`, `indexed_at=now()`. Commit.
10. Dispatch `tasks.extract_app_facts.delay(str(doc.app_id))`.
11. On exception: set `index_status='error'`, `index_error=str(exc)[:1000]`. Commit. Re-raise.

**Retry policy:** `max_retries=3`, `default_retry_delay=30`, exponential backoff. PII detection errors are non-fatal (log, continue). Embedding API errors trigger retry.

### 5.2 `tasks.extract_app_facts(app_id: str)`

**Trigger:** Called by `ingest_corpus_doc` on success; also directly callable.

**Steps:**
1. Load all `AppChunk` rows for `app_id` (via corpus docs), ordered by `doc_id, chunk_no`. Limit to `FACT_EXTRACT_MAX_CHUNKS` (default 100).
2. Build context: concatenate chunks with `--- [doc: {name}, chunk {chunk_no}] ---\n{text}`. Truncate to 50,000 chars.
3. Load `App.name` and `App.short_name`.
4. Run `SkillEngine.run("fact_extractor", {"app_name": ..., "chunk_text": ...}, provider)`.
5. For each extracted fact: check for existing `AppFact` with same normalized `kind`+`text` (strip/lower) and `status='active'`. If found → skip. Otherwise insert new `AppFact`.
6. Update `App.updated_at`. Commit.
7. Return `{"ok": True, "facts_created": N, "app_id": app_id}`.

### 5.3 `tasks.rebuild_app_brain(app_id: str)`

**Trigger:** `POST /api/apps/{id}/reindex`.

**Steps:**
1. Load all `AppCorpusDoc` for `app_id` where `index_status != 'running'`. Reset each to `index_status='pending'`. Commit.
2. For each doc: run `_ingest_corpus_doc(str(doc.id), task_self=None)` sequentially.
3. Run `_extract_app_facts(app_id)`.
4. Set `App.rebuild_status=None`, `App.updated_at=now()`. Commit.
5. Return `{"ok": True, "app_id": app_id, "docs_reindexed": N}`.

**Beat schedule addition:** `tasks.reset_stale_rebuild_status` — runs every 30 minutes, resets `rebuild_status='rebuilding'` rows with `updated_at` older than 60 minutes back to `None` (crash recovery).

---

## 6. New services

### 6.1 `backend/app/services/embeddings/` package

**`base.py`** — `EmbeddingProvider` ABC:
```python
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

**`vertex_embedding_provider.py`** — uses `langchain_google_vertexai.VertexAIEmbeddings` with `model_name="text-embedding-004"`. `embed_batch` batches in groups of 250. Asserts `len(embedding) == 768` on first call. Retries 3× on `google.api_core.exceptions.GoogleAPICallError`.

**`mock_embedding_provider.py`** — deterministic pseudo-random 768-dim float vectors seeded from `hash(text) % 2**32`. Normalized to unit length (required for cosine similarity correctness).

**`__init__.py`** — `get_embedding_provider()` factory:
```python
def get_embedding_provider() -> EmbeddingProvider:
    return MockEmbeddingProvider() if get_settings().llm_provider == "mock" else VertexEmbeddingProvider()
```

**Config additions to `Settings`:**
```python
embedding_model: str = "text-embedding-004"
embedding_dimensions: int = 768
corpus_max_upload_mb: int = 50
fact_extract_max_chunks: int = 100
```

### 6.2 `backend/app/services/pii/detector.py`

```python
class PiiDetector:
    def detect(self, text: str) -> bool:
        """Returns True if PII is detected (score >= 0.7)."""
```

Use `presidio_analyzer.AnalyzerEngine` with English. Detect: `PERSON`, `EMAIL_ADDRESS`, `PHONE_NUMBER`, `CREDIT_CARD`, `US_SSN`, `IBAN_CODE`, `IP_ADDRESS`. Minimum score 0.7.

**Regex fallback** if `presidio_analyzer` not importable: email pattern + US SSN pattern `\d{3}-\d{2}-\d{4}` + credit card pattern. Logs warning `"presidio_analyzer unavailable, using regex PII fallback"`.

### 6.3 `backend/app/services/corpus/chunker.py`

```python
def chunk_text(text: str, max_tokens: int = 512, overlap_tokens: int = 64) -> list[str]:
    """Splits text into overlapping chunks using tiktoken cl100k_base tokenizer."""
```

- Encode full text with `tiktoken.get_encoding("cl100k_base")`.
- Slide window: step = `max_tokens - overlap_tokens = 448` tokens.
- Decode each window back to string.
- Trailing chunks < 20 tokens merged into previous chunk.
- Empty input returns `[]`.

### 6.4 `backend/app/services/rag/retrieval_service.py`

```python
@dataclass
class RetrievedChunk:
    chunk_id: UUID; doc_id: UUID; doc_name: str
    chunk_no: int; text: str; similarity: float
    classification: str; pii_detected: bool

class RAGRetrievalService:
    async def retrieve(self, app_id, question, top_k, caller_is_privileged, db) -> list[RetrievedChunk]:
        ...
```

Implementation:
1. `embedding = await get_embedding_provider().embed(question)`.
2. Parameterized SQL with pgvector `<=>` operator:
```sql
SELECT ac.id, ac.doc_id, acd.name, ac.chunk_no, ac.text,
       1 - (ac.embedding <=> CAST(:vec AS vector(768))) AS similarity,
       acd.classification, acd.pii_detected
FROM app_chunks ac
JOIN app_corpus_docs acd ON acd.id = ac.doc_id
WHERE acd.app_id = :app_id
  AND acd.index_status = 'done'
  AND (NOT acd.pii_detected OR :privileged)
ORDER BY ac.embedding <=> CAST(:vec AS vector(768))
LIMIT :top_k
```
3. Filter `similarity < 0.3` after fetch.
4. Return `list[RetrievedChunk]`.

### 6.5 `backend/app/services/rag/rag_service.py`

`AppBrainRAGService.stream_answer(app_id, question, top_k, caller_is_privileged, db, app_name)` — async generator:
1. `chunks = await retrieval_service.retrieve(...)`.
2. If empty → yield `{"type": "error", "message": "No indexed content found for this app."}`, return.
3. Build `retrieved_text` with citation markers: `"[Citation {i+1} | {c.doc_name} chunk {c.chunk_no}]\n{c.text}"`.
4. Render prompt via extracted `SkillEngine._render_prompt("app_brain_qa", {"app_name": ..., "retrieved_text": ..., "question": ...})`.
5. Stream via `provider.astream(prompt=prompt, system=instruction, skill_name="app_brain_qa")`.
6. Yield `{"type": "chunk", "text": token}` per token.
7. Yield `{"type": "citations", "citations": [{chunk metadata}]}`.
8. Yield `{"type": "done"}`.

### 6.6 `LLMProvider` base extension

Add to `base.py`:
```python
@abstractmethod
async def astream(self, *, prompt: str, system: str, skill_name: str | None = None) -> AsyncIterator[str]:
    """Stream tokens from LLM. Yields raw text tokens."""
```

**`GeminiProvider.astream()`**: `async for chunk in self._llm.astream(messages): yield chunk.content`.

**`MockProvider.astream()`**: Split fixture answer into 10-char chunks, yield each with `await asyncio.sleep(0)`.

---

## 7. New skills

### 7.1 `fact_extractor` skill

**Location:** `backend/app/services/skills/fact_extractor/`

**`instruction.md`:** Expert enterprise systems analyst. Extract ONLY facts present in provided text. Classify as capability/constraint/limitation/integration/gotcha. Assign confidence: high (explicit), medium (implied), low (inferred). Provide source_ref quoting doc name + section. Deduplicate.

**`template.md`:**
```
Application: {{ app_name }}

## Documentation Chunks
{{ chunk_text }}

Extract all knowledge facts about {{ app_name }} from the above chunks.
```

**`schema.json`:**
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["facts"],
  "additionalProperties": false,
  "properties": {
    "facts": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["kind", "text", "confidence"],
        "additionalProperties": false,
        "properties": {
          "kind": {"type": "string", "enum": ["capability","constraint","limitation","integration","gotcha"]},
          "text": {"type": "string", "minLength": 5},
          "source_ref": {"type": ["string", "null"]},
          "confidence": {"type": "string", "enum": ["high","medium","low"]}
        }
      }
    }
  }
}
```

**Mock fixture** `backend/app/services/llm/fixtures/fact_extractor.json`:
```json
{
  "facts": [
    {"kind": "capability", "text": "PayHub supports real-time ISO 20022 payment settlement.", "source_ref": "PayHub Architecture v2.pdf §3.1", "confidence": "high"},
    {"kind": "integration", "text": "PayHub integrates with SWIFT MT103 for cross-border transfers.", "source_ref": "PayHub Architecture v2.pdf §4.2", "confidence": "high"},
    {"kind": "constraint", "text": "Transaction amounts are capped at $10M per single instruction.", "source_ref": null, "confidence": "medium"},
    {"kind": "gotcha", "text": "Idempotency keys expire after 24 hours; retrying after expiry creates a duplicate transaction.", "source_ref": "PayHub API Guide §7", "confidence": "high"}
  ]
}
```

### 7.2 `app_brain_qa` skill

**Location:** `backend/app/services/skills/app_brain_qa/`

**`instruction.md`:** Expert assistant for enterprise application architecture. Answer ONLY from provided context. If context is insufficient, say so — do not guess. Reference [Citation N] markers. Write professional prose for BA/SA audience.

**`template.md`:**
```
## Application: {{ app_name }}

## Retrieved Documentation Context
{{ retrieved_text }}

## Question
{{ question }}

Answer the question based solely on the above context. Reference [Citation N] markers where they support your answer.
```

**`schema.json`:**
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["answer"],
  "additionalProperties": false,
  "properties": {
    "answer": {"type": "string", "minLength": 1},
    "confidence": {"type": "string", "enum": ["high","medium","low"]},
    "unsupported": {"type": "boolean"}
  }
}
```

**Mock fixture** `backend/app/services/llm/fixtures/app_brain_qa.json`:
```json
{
  "answer": "PayHub supports real-time ISO 20022 payment settlement [Citation 1] and integrates with SWIFT MT103 for cross-border transfers [Citation 2]. Transaction amounts are capped at $10M per instruction.",
  "confidence": "high",
  "unsupported": false
}
```

---

## 8. Pydantic schemas (`backend/app/schemas/app.py`)

```python
class AppCreate(BaseModel):
    name: Annotated[str, AfterValidator(lambda v: v.strip())]  # non-empty
    short_name: Annotated[str, AfterValidator(lambda v: _validate_short_name(v))]  # ^[a-z0-9-]{1,50}$
    description: str | None = None
    tier: Annotated[int, Field(ge=1, le=3)]
    domain_area: str | None = None
    version: str | None = None

class AppCorpusDocRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; app_id: UUID; name: str; page_count: int | None
    is_primary: bool; pii_detected: bool; classification: str
    index_status: str; indexed_at: datetime | None; created_at: datetime

class AppFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; app_id: UUID; kind: str; text: str; source_ref: str | None
    confidence: str; status: str; chunk_ids: list; created_at: datetime; updated_at: datetime

class PipelineSummary(BaseModel):
    total_docs: int; indexed_docs: int; pending_docs: int
    total_chunks: int; total_facts: int; last_indexed_at: datetime | None

class AppListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; short_name: str; description: str | None
    tier: int; domain_area: str | None; is_onboarded: bool; version: str | None
    owner_id: UUID | None; corpus_doc_count: int = 0; indexed_doc_count: int = 0
    fact_count: int = 0; has_pii: bool = False; created_at: datetime; updated_at: datetime

class AppDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; name: str; short_name: str; description: str | None
    tier: int; domain_area: str | None; is_onboarded: bool; version: str | None
    owner_id: UUID | None; corpus_docs: list[AppCorpusDocRead]
    facts: list[AppFactRead]; pipeline_summary: PipelineSummary
    created_at: datetime; updated_at: datetime

class AskRequest(BaseModel):
    question: Annotated[str, Field(min_length=1, max_length=1000)]
    top_k: Annotated[int, Field(default=8, ge=1, le=20)] = 8
```

---

## 9. Frontend pages & components

### 9.1 `/apps` — App Registry (`frontend/app/apps/page.tsx`)

**Layout:** Inside `AppShell`. Top bar: "App Registry" heading + "New App" button (platform_admin only).

**Components:**

`AppRegistryPage`:
- SWR `useApps(filters)` → `GET /api/apps?q=...&tier=...&mine=...`
- Filter tabs: `All | Tier 1 | Tier 2 | Tier 3 | Not Onboarded | My Apps`
- Debounced search input (300ms), sets `q` param
- Grid of `AppCard` (3 columns @ 1440px)

`AppCard` (`frontend/app/components/AppCard.tsx`):
- App name, short_name chip, tier badge (Tier 1 = `--status-success`, Tier 2 = `--accent-blue`, Tier 3 = `--text-tertiary`), domain_area
- Health badges: `indexed_doc_count === corpus_doc_count` → "Brain Ready" (green); `< corpus_doc_count` → "Indexing" (amber); `is_onboarded=false` → "Not Onboarded" (grey)
- `has_pii` → shield icon with `--status-warning` color
- Click → `/apps/{id}`

`NewAppModal` (`frontend/app/components/NewAppModal.tsx`):
- Fields: name, short_name (auto-slugified from name on blur), description, tier (select), domain_area, version
- Submit → `POST /api/apps`, invalidate SWR, navigate to new app

**SWR hook** `frontend/lib/hooks/useApps.ts`:
```typescript
export function useApps(filters: AppsFilter) {
  const params = new URLSearchParams(/* filters */)
  return useSWR<AppListItem[]>(`/api/apps?${params}`, apiFetcher, { revalidateOnFocus: false })
}
```

**AppShell sidebar addition** in `AppShell.tsx` NAV_ITEMS:
```typescript
{ href: '/apps', icon: Brain, label: 'App Registry' }
```

### 9.2 `/apps/[id]` — App Brain Detail

**Route:** `frontend/app/apps/[id]/page.tsx` + `frontend/app/apps/[id]/layout.tsx`

**Layout:** Two-column — fixed left shelf nav (220px) + scrollable main area.

**Left shelf nav sections:** Overview · Facts · Corpus · Constraints · Integrations · Pipeline · Ask

**SWR hook** `useApp(id)` in `frontend/lib/hooks/useApp.ts` → `GET /api/apps/{id}`. `refreshInterval: 5000` while `pipeline_summary.pending_docs > 0` (auto-stops when all indexed).

**Sections:**

`OverviewSection`: name, short_name, tier badge, domain, version, owner, `is_onboarded` display, description, pipeline stats (X docs / Y facts / last indexed).

`FactList` (`frontend/app/components/FactList.tsx`):
- Filter bar: kind tabs + confidence chips
- Each row: `ConfidenceBadge` (reuse existing), kind icon chip (`Zap`/`Lock`/`AlertTriangle`/`Plug`/`AlertCircle`), fact text, source_ref, status chip

`CorpusManager` (`frontend/app/components/CorpusManager.tsx`):
- List of docs with `IndexStatusBadge` (spinner → done/error), `pii_detected` shield badge, page count, `is_primary` chip
- Upload zone (drag-and-drop + file picker) — owner/delegate/admin only: calls `POST /api/apps/{id}/corpus` (multipart). Optimistically adds pending row. SWR revalidates after 2s.
- "Re-index All" button: `POST /api/apps/{id}/reindex`. Disabled while `App.rebuild_status='rebuilding'`. Shows toast on 409.

`PipelineSection`: Step view per doc (Parse / Embed / Facts). Aggregate totals. `refreshInterval: 5000` while any doc is `pending`/`running`.

### 9.3 Ask Panel (`frontend/app/components/AskPanel.tsx`)

Text input + "Ask" button. Response area with streaming text + citation chips.

**SSE fetch implementation:**
```typescript
async function handleAsk() {
  setIsStreaming(true); setStreamedText(''); setCitations([])
  const res = await fetch(`/api/apps/${appId}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
                'Authorization': `Bearer ${tokenStore.get()}` },
    body: JSON.stringify({ question, top_k: 8 }),
  })
  if (!res.ok || !res.body) { setError('Request failed'); setIsStreaming(false); return }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n'); buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const event = JSON.parse(line.slice(6))
      if (event.type === 'chunk') setStreamedText(t => t + event.text)
      if (event.type === 'citations') setCitations(event.citations)
      if (event.type === 'error') setError(event.message)
      if (event.type === 'done') setIsStreaming(false)
    }
  }
}
```

`CitationChip` (`frontend/app/components/CitationChip.tsx`): pill with doc name + chunk number, tooltip showing `text_excerpt`. Use `--accent-blue` for citation color (consistent with future E3 citation style).

**`api.ts` additions:**
```typescript
apps: {
  list: (filters?: AppsFilter) => apiFetch<AppListItem[]>(`/api/apps?${qs}`),
  create: (data: AppCreate) => apiFetch<AppDetail>('/api/apps', { method: 'POST', body: JSON.stringify(data) }),
  get: (id: string) => apiFetch<AppDetail>(`/api/apps/${id}`),
  uploadCorpusDoc: async (appId: string, file: File, isPrimary: boolean): Promise<AppCorpusDoc> => { /* multipart */ },
  reindex: (appId: string) => apiFetch<{ task_id: string }>(`/api/apps/${appId}/reindex`, { method: 'POST' }),
  listFacts: (appId: string, params?: FactsFilter) => apiFetch<AppFact[]>(`/api/apps/${appId}/facts?${qs}`),
}
```

---

## 10. Ordered work breakdown

### Phase 1 — Data + Infrastructure

- **T1.** Add to `requirements.txt`: `pgvector==0.3.6`, `tiktoken==0.9.0`, `presidio-analyzer==2.2.355`, `presidio-anonymizer==2.2.355`. → blocks T3, T6, T7.
- **T2.** Alembic migration `0004_app_brain.py`: enable `vector` extension, create all enum types, create `apps`, `app_members`, `app_corpus_docs`, `app_chunks` (with IVFFlat index), `app_facts`. `downgrade()` in reverse dependency order. → blocks all.
- **T3.** SQLAlchemy models: `App`, `AppMember` in `app/models/app.py`; `AppCorpusDoc`, `AppChunk` (with `Vector(768)` column) in `app/models/corpus.py`; `AppFact` in `app/models/fact.py`. Update `models/__init__.py`. → blocks T8, T9.
- **T4.** Settings additions to `config.py`: `embedding_model`, `embedding_dimensions`, `corpus_max_upload_mb`, `fact_extract_max_chunks`. → blocks T5.
- **T5.** `EmbeddingProvider` ABC + `VertexEmbeddingProvider` + `MockEmbeddingProvider` + factory in `app/services/embeddings/`. → BR-M4-010. Blocks T9, T13.

### Phase 2 — Services

- **T6.** `PiiDetector` in `app/services/pii/detector.py`. presidio-analyzer + regex fallback. → BR-M4-011. Blocks T9.
- **T7.** `chunk_text()` in `app/services/corpus/chunker.py`. tiktoken `cl100k_base`, 512/64 tokens, sub-20-token merge. → Blocks T9.
- **T8.** Pydantic schemas in `app/schemas/app.py`. Validators for short_name, tier, question length, top_k max. → Blocks T17+.

### Phase 3 — Ingestion Pipeline

- **T9.** `tasks.ingest_corpus_doc` in `workers/tasks.py`. Full parse→PII→chunk→embed→store implementation. `ANALYZE app_chunks` after bulk insert. Dispatch `extract_app_facts` on success. → BR-M4-004, BR-M4-005, BR-M4-011.
- **T10.** `fact_extractor` skill files: `instruction.md`, `template.md`, `schema.json`, mock fixture. Update `MockProvider._SKILL_FIXTURE_MAP`. → BR-M4-003. Blocks T11.
- **T11.** `tasks.extract_app_facts` in `workers/tasks.py`. Chunk context → fact_extractor skill → upsert `AppFact` with deduplication. → BR-M4-003, BR-M4-004.
- **T12.** `tasks.rebuild_app_brain` + `tasks.reset_stale_rebuild_status` (Beat, 30min) in `workers/tasks.py`. Update Beat schedule in `celery_app.py`. → BR-M4-005.

### Phase 4 — Retrieval + Ask

- **T13.** `RAGRetrievalService` in `app/services/rag/retrieval_service.py`. pgvector cosine query, PII/classification SQL filter, similarity threshold 0.3, `RetrievedChunk` dataclass. → BR-M4-006, BR-M4-011.
- **T14.** `app_brain_qa` skill files + mock fixture. Update `MockProvider._SKILL_FIXTURE_MAP`. `SkillEngine._render_prompt()` extracted as a public helper method. → BR-M4-006.
- **T15.** `LLMProvider.astream()` abstract method + `GeminiProvider.astream()` + `MockProvider.astream()`. `AppBrainRAGService.stream_answer()` async generator in `app/services/rag/rag_service.py`. → BR-M4-006.
- **T16.** `POST /api/apps/{id}/ask` SSE endpoint. `StreamingResponse`, `event_generator()`, auth + rate limit, audit emit (question hashed). → BR-M4-006, BR-M4-011.

### Phase 5 — CRUD API

- **T17.** `GET /api/apps` with correlated subqueries (corpus_doc_count, indexed_doc_count, fact_count, has_pii). RBAC filter. → BR-M4-001.
- **T18.** `POST /api/apps`. short_name uniqueness check (409). require_role(platform_admin). → BR-M4-001.
- **T19.** `GET /api/apps/{id}`. Full detail: corpus_docs selectin, facts selectin with PII filter, pipeline_summary aggregated. `require_app_access` dep (404 for existence-leak). → BR-M4-003, BR-M4-004.
- **T20.** `POST /api/apps/{id}/corpus`. Magic-byte validate, SHA-256 dedup, StorageFile persist, AppCorpusDoc create, Celery dispatch. Rate limit 10/min. → BR-M4-005.
- **T21.** `POST /api/apps/{id}/reindex`. rebuild_status guard (409), dispatch, audit. Rate limit 2/min. → BR-M4-005.
- **T22.** `GET /api/apps/{id}/facts`. Filtered list, PII filter, pagination. → BR-M4-003.
- **T23.** `require_app_access` + `require_app_write_access` deps in `api/deps.py`. Wire `apps.router` into `main.py`. → All app BRs.
- **T24.** Seed data: create PayHub app (tier 1, is_onboarded=true) in `scripts/seed_users.py`. Upload sample text corpus doc. Trigger ingest via `CELERY_TASK_ALWAYS_EAGER=True`. Verify facts created. → Demo script.

### Phase 6 — Frontend

- **T25.** Type additions in `frontend/lib/types.ts`: `AppListItem`, `AppDetail`, `AppCorpusDoc`, `AppFact`, `PipelineSummary`, `IndexStatus`, `FactKind`, `FactConfidence`, `FactStatus`, `AppCreate`, `AppsFilter`, `FactsFilter`.
- **T26.** `api.ts` additions: `api.apps.*` methods. SSE `ask` handled separately via raw fetch.
- **T27.** SWR hooks: `useApps` (with filter params), `useApp` (with polling on pending docs).
- **T28.** `/apps` registry page: `AppRegistryPage`, `AppCard`, `NewAppModal`. Filter tabs, search, tier/health badges, PII shield. Add `Brain` nav item to `AppShell`. → BR-M4-001, BR-M4-002.
- **T29.** `/apps/[id]` layout with left shelf nav. `OverviewSection`. → BR-M4-003.
- **T30.** `FactList`, `CorpusManager`, `PipelineSection`, `IndexStatusBadge` components. → BR-M4-003, BR-M4-004, BR-M4-005.
- **T31.** `AskPanel` + `CitationChip` components. SSE streaming via `ReadableStream`. Token-by-token display. Citation chips after `done` event. → BR-M4-006.

---

## 11. Security checklist additions (extends E0 checklist)

- [ ] **Embedding keys never exposed:** `gemini_service_account_path` and all LLM/embedding credentials excluded from all API responses and logs. `GET /api/health` extended response MAY include provider name but NEVER key material.
- [ ] **PII classification enforcement (BR-M4-011):** `pii_detected=true` docs → chunks excluded from `/ask` retrieval for non-privileged callers at SQL level (parameterized filter, NOT client-side). Facts from PII docs excluded from `GET /api/apps/{id}/facts` for non-privileged callers. Audit event emitted when PII retrieval is blocked.
- [ ] **Existence-leak prevention:** `GET /api/apps/{id}` returns 404 (not 403) for non-onboarded apps the caller has no membership in.
- [ ] **Upload guards (corpus):** magic-byte MIME detection (reuse `storage.detect_mime`); sanitized filename (reuse `storage.sanitize_filename`); size limit `CORPUS_MAX_UPLOAD_MB` default 50MB; allowed MIME: PDF/DOCX/TXT only.
- [ ] **SSE auth:** `/ask` is a POST requiring Bearer token in Authorization header — cookies NOT relied upon (EventSource API only supports GET). Token validated via `get_current_user` before streaming begins. Mid-stream token expiry → yield `{"type":"error","message":"Session expired"}` then exit.
- [ ] **Question content not stored plaintext:** `audit.emit` for `/ask` stores `sha256(question)` only. Prevents business-sensitive info leaking into audit log.
- [ ] **Rate limits on AI endpoints:** `/ask` → 20/min per authenticated user. `/corpus` upload → 10/min. `/reindex` → 2/min.
- [ ] **pgvector SQL injection prevention:** embedding vector passed as a bound parameter via SQLAlchemy `text()` with `:vec` binding + explicit `CAST(:vec AS vector(768))` — never string-interpolated.
- [ ] **Celery task input validation:** `ingest_corpus_doc(doc_id: str)` validates `UUID(doc_id)` at task start — log and return on invalid input.
- [ ] **No LLM prompt logging at INFO:** Full rendered prompts (containing corpus text) NOT logged at INFO in production. Log only `skill_name`, `app_id`, `chunk_count`, `latency_ms`. Debug-only logging acceptable with `LOG_LEVEL=DEBUG`.
- [ ] **Classification hierarchy (enforcement):** `internal` accessible to all authenticated users (if `pii_detected=false`); `restricted` accessible only to owner/delegate/admin. Enforced at SQL level, not client-side.

---

## 12. Test plan

### Unit tests

**`test_chunker.py`:** Single-chunk for short text; 2-chunk result with correct overlap for 1000-token text; sub-20-token trailing merged; empty input returns `[]`.

**`test_pii_detector.py`:** SSN `"John Smith, SSN 123-45-6789"` → True; email in text → True; clean technical text → False; empty string → False.

**`test_mock_embedding_provider.py`:** Returns 768 floats; deterministic (same input = same output); unit-length normalized (L2 norm ≈ 1.0 ± 1e-5); batch returns correct count.

**`test_fact_extractor_skill.py`:** `SkillEngine.run("fact_extractor", context, MockProvider())` → dict with `facts` list; each fact has `kind`/`text`/`confidence`; `kind` in enum values; schema valid.

**`test_app_brain_qa_skill.py`:** Returns `{"answer": str, ...}`; schema valid.

**`test_app_schemas.py`:** `AppCreate` rejects `short_name="Has Spaces"` (422); rejects `tier=5` (422); `AskRequest` rejects empty question (422); rejects question > 1000 chars (422); rejects `top_k=25` (422).

### Integration tests (real Postgres + Redis)

**`test_app_crud.py`:** business_analyst POST /api/apps → 403; platform_admin POST → 201; duplicate short_name → 409; unauthenticated GET → 401; business_analyst sees only onboarded apps; platform_admin sees all; non-onboarded app as non-member → 404.

**`test_corpus_upload.py`:** Upload PDF → 202 pending; same file SHA-256 again → 409; file > size limit → 413; non-allowed MIME → 422; with `CELERY_TASK_ALWAYS_EAGER=True` upload → `index_status='done'`, chunks in DB.

**`test_ingest_pipeline.py`:** `ingest_corpus_doc` with MockEmbeddingProvider: status transitions `pending→running→done`; `AppChunk` rows with non-null embedding; `page_count` set; re-ingest idempotent (old chunks deleted, new inserted). `extract_app_facts`: AppFact rows created, no duplicates on second run.

**`test_pii_flow.py`:** Upload doc with SSN text → `pii_detected=True`; GET /api/apps/{id}/facts as non-privileged → facts from PII doc excluded; POST /api/apps/{id}/ask as non-privileged → PII chunks excluded from citations; audit event exists for blocked attempt.

**`test_ask_sse.py`:** POST /ask with indexed corpus → 200 text/event-stream; events: at least one `chunk`, one `citations`, one `done`; citations contain `doc_name`/`chunk_no`/`text_excerpt`; POST /ask for app with no indexed docs → `error` event; unauthenticated → 401 before stream opens.

**`test_reindex.py`:** POST /reindex → 202, `rebuild_status='rebuilding'`; second call → 409; after task: `rebuild_status=null`, all docs `index_status='done'`.

### e2e tests (Playwright)

**`test_app_registry.spec.ts`:** platform_admin sees app cards with tier badges; business_analyst sees only onboarded apps, no "New App" button; search filters cards; click → `/apps/{id}`; "New App" → modal → submit → appears in grid.

**`test_brain_detail.spec.ts`:** Left shelf nav renders all sections; facts tab shows cards with confidence badges; corpus tab shows docs with status; pipeline shows step counts; upload new doc → status "Pending" → polls to "Done".

**`test_ask_panel.spec.ts`:** Type question → stream appears token by token; citation chips render after done; SSE error → error message displayed; re-ask clears previous answer.

---

## 13. Done criteria + demo script

**Done:** All §1 acceptance rows pass; §11 security checklist green; CI (lint, typecheck, pytest unit+integration, Playwright, `pip-audit`) green; migration `0004` runs clean on fresh DB; seed creates PayHub with indexed docs and extracted facts.

**Demo script:**
1. `docker-compose up` (postgres+pgvector, redis). `alembic upgrade head`. `python seed.py`. Start API + Celery worker.
2. Log in as `admin@specforge.test`. Navigate `/apps` → PayHub card with "Brain Ready" badge, Tier 1.
3. Click PayHub → brain detail. Facts: 4+ with confidence badges. Corpus: 1 indexed PDF, status Done.
4. Upload second PDF → status "Pending" → auto-refreshes to "Done". Fact count increases.
5. Ask panel → "What payment protocols does PayHub support?" → streaming answer → citation chips appear.
6. Log in as `analyst@specforge.test`. `/apps` → PayHub visible. Upload button hidden (no write access). Ask panel works.
7. As admin: upload PII-containing doc → shield badge "PII Detected". Log in as analyst → ask about PII content → answer does NOT reveal PII (no PII chunk IDs in citations).
8. As admin: "Re-index All" → status "Rebuilding" → completes. Second click while rebuilding → toast "Rebuild already in progress".
9. Navigate `/apps/{non-onboarded-app-id}` as analyst → 404 page.
10. Show audit log: events for `app.created`, `corpus.doc.uploaded`, `app.reindex.triggered`, `app.brain.ask`.

---

## 14. Risks & open questions

- **IVFFlat recall on small corpora:** IVFFlat with `lists=100` performs poorly when chunk count < 1000 (most lists are empty). Consider `SET ivfflat.probes = min(100, lists)` at query time. For E1 corpora (< 100 chunks in dev), switch to HNSW: `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64)` — better accuracy at small scale, no pre-build requirement. Decision: use IVFFlat in migration but add a note to switch HNSW if `ANALYZE` shows poor recall.
- **presidio-analyzer spaCy model size:** Default `en_core_web_lg` is ~750MB. Use `en_core_web_sm` (50MB) for E1. Add `python -m spacy download en_core_web_sm` to Docker setup and developer onboarding docs. Alternative: `scrubadub` (~5MB) if spaCy is too heavy.
- **Streaming + async:** FastAPI `StreamingResponse` with async generators works cleanly with uvicorn asyncio mode. The `/ask` endpoint is purely async — no Celery involved. The streaming path does NOT go through Celery. Confirm uvicorn worker class (default asyncio, not gevent/eventlet) before deploying.
- **rebuild_status stuck:** If Celery worker crashes mid-rebuild, `rebuild_status` stays `'rebuilding'` forever. Mitigation: `tasks.reset_stale_rebuild_status` Beat task (30-min schedule) resets rows with `updated_at` older than 60 minutes. Must be added to `celery_app.beat_schedule` in T12.
- **Embedding cost (Vertex AI):** ~$0.01-0.02 per 100-page PDF. For dev: `MockEmbeddingProvider` (zero cost). For CI: use `MockEmbeddingProvider` (set `LLM_PROVIDER=mock`). Integration tests that hit real Vertex AI should be tagged `@pytest.mark.slow` and excluded from default CI run.
- **tiktoken vs text-embedding-004 tokenization:** `cl100k_base` is a pragmatic approximation — 512 `cl100k_base` tokens will not exceed Vertex AI's 2048-token input limit. Log character counts per chunk during ingestion for monitoring.
- **Fact deduplication brittle:** Normalized text equality misses paraphrases. Acceptable for E1; E5 adds semantic dedup via embedding cosine similarity. Document this limitation explicitly in E5 planning.
- **SSE + reverse proxy buffering:** `X-Accel-Buffering: no` disables nginx buffering. Verify Railway/production proxy passes this header. Add `Transfer-Encoding: chunked` as fallback in the `StreamingResponse` headers dict.
