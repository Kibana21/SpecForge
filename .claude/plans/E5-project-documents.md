# E5 — Project Documents Module

**Status:** Planned  
**Depends on:** E2 (project intake), E4a (concept brief / artifact pipeline)  
**Last updated:** 2026-05-26

---

## Goal

Make project documents first-class, AI-grounded artefacts. Every uploaded file —
regardless of type — should be readable, structured, and contribute to the AI
context used by Requirement Understanding, Concept Brief, and BRD generation.

---

## Zone Boundary (hard constraint)

| Zone | Tables | Must not touch |
|---|---|---|
| **App Brain** | `app_corpus_docs`, `app_doc_trees`, `document_markdown`, vector chunks/embeddings | ← project docs must never write here |
| **Project Docs** | `documents`, `document_trees` | ← project docs write only here |

The two zones share the `get_markdown_provider()` and `get_corpus_index()`
abstractions, but their data is completely isolated. Project docs call the
markdown provider **directly** (not via `MarkdownConverterService`, which writes
to `document_markdown` — an App Brain table). The converted markdown is stored in
`doc.extracted_text` which lives in the project docs zone.

---

## Supported Document Types

| Type | MIME | Extraction method | PageIndex tree |
|---|---|---|---|
| PDF | `application/pdf` | Azure Content Understanding (`prebuilt-layout`) | Rich tree from heading-structured markdown |
| Word | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Azure Content Understanding (`prebuilt-layout`) | Same |
| Images | `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/tiff`, `image/bmp` | Azure Content Understanding (`prebuilt-layout`) | From AI-generated markdown |
| Plain text | `text/plain` | Raw bytes decode (UTF-8) | Minimal (page chunks) |
| Markdown | `text/markdown` | Raw bytes decode (UTF-8) | Rich tree from `#` headings |

**Key insight:** Azure `prebuilt-layout` natively handles PDF, DOCX, and images
(JPEG, PNG, TIFF, BMP, GIF, WEBP) — producing clean, table-aware, figure-aware
markdown for all of them. One extraction path replaces PyMuPDF, python-docx, AND
any Gemini Vision approach. The `MockMarkdownProvider` already provides
deterministic CI/test coverage.

---

## Processing Pipeline

All document types follow the same two-phase pipeline:

```
Upload
  │
  ├─► Sync (in request handler)
  │     parser.parse() on TXT/MD only (cheap, no API call)
  │     For TXT/MD: extracted_text = raw decode, parse_status = 'done'
  │     For PDF/DOCX/images: parse_status = 'done' (skip sync parse — let async handle it)
  │     indexing_status = 'pending'
  │
  └─► dispatch(ingest_project_source) [async, Celery]
        indexing_status: pending → running
        │
        ├─► Detect MIME category
        │
        ├─► RICH_MIMES (PDF, DOCX, images)
        │     provider = get_markdown_provider()           ← same factory as App Brain
        │     markdown = await provider.convert(            ← called DIRECTLY (no MarkdownConverterService)
        │         file_bytes, mime_type                       stores nothing in document_markdown
        │     )
        │     doc.extracted_text = markdown
        │     doc.parse_status = 'done'
        │     await db.flush()
        │
        ├─► TEXT_MIMES (TXT, MD)
        │     extracted_text already set in sync phase
        │     (no-op here)
        │
        ├─► PageIndex.build_index(
        │       content = doc.extracted_text.encode('utf-8'),
        │       mime_type = 'text/markdown',               ← always markdown after conversion
        │       filename = doc.filename
        │   )
        │     → md_to_tree uses # headings
        │     → DocumentTree row written (or replaced if re-indexed)
        │         tree_json, page_texts, node_count, model
        │
        └─► indexing_status = 'done'
              └─► IF project has RU with updated_at < doc.created_at
                    → docs_stale_for_ru = true (computed at read time)
```

**Why call the provider directly instead of `MarkdownConverterService`?**

`MarkdownConverterService.convert()` writes to `document_markdown` — an App Brain
table. By calling `provider.convert()` directly, we get the same conversion
quality (Azure or mock) but store the result in `doc.extracted_text`, which
belongs to the project docs zone. No zone boundary is crossed.

---

## Backend Changes

### No new Alembic migration needed

All required fields already exist on the `Document` model:
- `extracted_text` — converted markdown (all types) or raw text (TXT/MD)
- `indexing_status` — `pending | running | done | error`
- `index_error` — error string if PageIndex fails
- `page_count` — set during ingest

These fields ARE in `DocumentRead` Pydantic schema but are **missing from the
TypeScript `DocumentRead` interface** — that's the only schema fix needed.

### Updated: `workers/tasks.py` — `_ingest_project_source()`

```python
from app.services.markdown_converter import get_markdown_provider

RICH_MIMES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png", "image/jpeg", "image/jpg",
    "image/gif", "image/webp", "image/tiff", "image/bmp",
})

async def _ingest_project_source(doc_id: str, db: AsyncSession) -> None:
    doc = await db.get(Document, uuid.UUID(doc_id))
    # ...existing status guards...
    doc.indexing_status = "running"
    await db.flush()

    try:
        file_bytes = await storage.read(doc.storage_path)

        if doc.mime_type in RICH_MIMES:
            # Call provider directly — do NOT use MarkdownConverterService
            # (that writes to document_markdown, which is App Brain zone)
            provider = get_markdown_provider()
            markdown = await provider.convert(file_bytes, doc.mime_type)
            doc.extracted_text = markdown
            doc.parse_status = "done"
            await db.flush()
            content_for_index = markdown.encode("utf-8")
        else:
            # TXT/MD already have extracted_text from sync parse phase
            content_for_index = (doc.extracted_text or "").encode("utf-8")

        # Build PageIndex tree — always treat as markdown after conversion
        corpus_index = get_corpus_index()
        result = await corpus_index.build_index(
            content_for_index, "text/markdown", doc.filename
        )

        # Write DocumentTree (project zone)
        await db.execute(delete(DocumentTree).where(DocumentTree.document_id == doc.id))
        db.add(DocumentTree(
            document_id=doc.id,
            tree_json=result.tree,
            page_texts=result.page_texts,
            node_count=result.node_count,
            model=result.model,
        ))
        doc.page_count = result.node_count
        doc.indexing_status = "done"
        await db.commit()

    except Exception as exc:
        doc.indexing_status = "error"
        doc.index_error = str(exc)
        await db.commit()
        raise
```

### New endpoints: `backend/app/api/documents.py`

```
GET  /projects/{project_id}/documents/{doc_id}/outline
     → { tree: [nodes…], node_count, model, indexing_status }
     → pure DB read, titles + summaries only (no bulk text)

GET  /projects/{project_id}/documents/{doc_id}/section/{node_id}
     → { title, pages, text }
     → lazy: reconstructs text from page_texts[start_index..end_index]
     → called only when user expands a section

GET  /projects/{project_id}/documents/{doc_id}/file
     → binary response with correct Content-Type header
     → used for image thumbnail in viewer + PDF download link
```

### Updated: `GET /projects/{project_id}` response

Add `docs_stale_for_ru: bool` to `ProjectDetail`:

```python
# Computed at read time — no new column needed
docs_stale_for_ru = (
    ru is not None
    and ru.status in ("in_interview", "validated")
    and any(
        d.created_at > ru.updated_at
        for d in project.documents
        if d.indexing_status == "done"
    )
)
```

---

## Frontend Changes

### `frontend/lib/types.ts` — extend `DocumentRead`

```typescript
export interface DocumentRead {
  id: string
  project_id: string
  filename: string
  mime_type: string
  size_bytes: number
  parse_status: ParseStatus
  parse_error: string | null
  indexing_status: 'pending' | 'running' | 'done' | 'error'  // ADD
  index_error: string | null                                   // ADD
  page_count: number | null                                    // ADD
  created_at: string
  updated_at: string
}
```

Add new API methods:

```typescript
documents: {
  // existing ...
  getOutline:  (projectId, docId) => GET /outline
  getSection:  (projectId, docId, nodeId) => GET /section/{nodeId}
  getFileUrl:  (projectId, docId) => string  // constructs URL for <img src> / download
}
```

### `DocumentList` — indexing status per file

Per-file status indicator (right side of each row):

| `indexing_status` | Icon | Behaviour |
|---|---|---|
| `pending` | pulsing `Loader2` (grey) | — |
| `running` | pulsing `Loader2` (blue) | — |
| `done` | `CheckCircle2` (green) | Structure tab available |
| `error` | `AlertCircle` (red) | tooltip with `index_error` |

**SWR polling:** when any document in the project has `indexing_status !== 'done'`,
`useProject` should poll every 3 seconds (same pattern as `useArtifact` for
`status === 'generating'`).

**Type-aware icons** (replace generic `FileText` for all):

| MIME contains | Icon | Colour tint |
|---|---|---|
| `pdf` | `FileText` | red-400 |
| `word` / `docx` | `FileText` | blue-400 |
| `markdown` | `Hash` | purple-400 |
| `plain` / `txt` | `AlignLeft` | grey-400 |
| `image/` | `Image` | amber-400 |
| other | `File` | grey-400 |

### `DocumentViewer` — type-aware tabs

Viewer decides which tabs to show based on `doc.mime_type`:

```
mime_type starts with "image/"
  Header: thumbnail (<img src={fileUrl}>) + filename + "AI Understanding" label
  Tab 1: "AI Understanding" → rendered markdown (react-markdown)
  Tab 2: "Structure" → PageIndex tree (same as markdown)

mime_type === "text/markdown"
  Tab 1: "Rendered" → react-markdown renderer
  Tab 2: "Structure" → PageIndex tree

mime_type === "text/plain"
  Tab 1: "Text" → plain pre block (no Structure — page-chunk nodes aren't useful)

mime_type === "application/pdf" or "...docx"
  Tab 1: "Rendered" → react-markdown (Azure-converted markdown)
  Tab 2: "Structure" → PageIndex tree
```

**Structure tab — tree component:**

```
▼ § Overview (pp. 1–2)
    "Describes the settlement modernization goals..."
    [Expand to read]
  ▼ § Functional Requirements (pp. 3–8)
      "Lists all FR items with acceptance criteria..."
      [Expand to read]
    ▶ § FR-001: ACH Transfers (pp. 3–4)
    ▶ § FR-002: Real-time Balance (pp. 5–6)
  ▶ § Non-Functional Requirements (pp. 9–11)
  ▶ § Integration Points (pp. 12–14)
```

Clicking "Expand to read" triggers `GET /section/{node_id}` lazily.

### Project Overview — stale banner

When `ProjectDetail.docs_stale_for_ru === true`, show a dismissible banner
between the project info card and the progress checklist:

```
⚠ A document was added after your Requirement Understanding was generated.
  Regenerate the RU to incorporate the latest sources.   [Open Interview →]
```

Dismiss stores in `sessionStorage` (clears on next load so it reappears if still stale).

---

## Implementation Order

1. **Backend: `workers/tasks.py`** — add `RICH_MIMES`, direct `provider.convert()` call, updated tree-writing logic
2. **Backend: `/outline`, `/section/{node_id}`, `/file` endpoints**
3. **Backend: `docs_stale_for_ru` in `ProjectDetail`**
4. **Frontend: `DocumentRead` type** — add `indexing_status`, `page_count`, `index_error`
5. **Frontend: `useProject` polling** — refresh when any doc indexing not done
6. **Frontend: `DocumentList` icons + status indicators**
7. **Frontend: `DocumentViewer` tabs** — type-aware rendering, Structure tree, image thumbnail
8. **Frontend: API methods** — `getOutline`, `getSection`, `getFileUrl`
9. **Frontend: stale banner** in project overview

---

## What Does NOT Change

- No new Alembic migration
- No new database tables
- App Brain tables untouched (including `document_markdown` — project docs never write there)
- `ingest_project_source` task signature unchanged (still takes `doc_id`)
- `document_trees` table unchanged
- RU retrieval (`_retrieve_project_sections`) unchanged — reads `extracted_text` and `document_trees`
- Artifact retrieval unchanged — same benefit automatically
- `MarkdownConverterService` unchanged — still used only by App Brain corpus ingestion

---

## Mock Strategy (CI/tests)

- `MockMarkdownProvider.convert()` returns content of
  `app/services/markdown_converter/fixtures/mock_markdown.md` (existing fixture)
- `ingest_project_source` with a PDF/image in tests → calls mock → produces tree →
  asserts `indexing_status == 'done'` and `node_count > 0`
- No Vertex AI or Azure calls in CI

---

## Open Questions

1. **Upload UI** — should we explicitly allow `image/*` in the UploadPanel accept
   attribute? Currently shows "PDF, DOCX, TXT". Update to "PDF, DOCX, TXT, MD,
   PNG, JPG" once image pipeline is live.

2. **Conversion cost** — Azure Content Understanding calls are billed. Consider
   adding a `max_file_size_bytes` config gate (e.g. reject files > 20 MB before
   calling the provider API).

3. **Re-indexing** — no current mechanism to re-run conversion on existing docs
   if the provider is changed or the file needs re-processing. A future
   `POST /documents/{doc_id}/reindex` endpoint could handle this.

4. **Structure tab for TXT** — hidden because page-chunk nodes are not meaningful.
   Revisit if TXT files in practice have large structured content.
