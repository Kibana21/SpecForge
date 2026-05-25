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

The two zones share the PageIndex provider abstraction and the LLM provider
abstraction, but their data is completely isolated.

---

## Supported Document Types

| Type | MIME | Text extraction | PageIndex tree | AI Vision |
|---|---|---|---|---|
| PDF | `application/pdf` | PyMuPDF, per-page | Rich tree from PDF structure | No |
| Word | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | python-docx, flat text | Fair tree (page fallback) | No |
| Plain text | `text/plain` | Raw text | Minimal (page chunks) | No |
| Markdown | `text/markdown` | Raw text | Rich tree from `#` headings | No |
| Images | `image/png`, `image/jpeg`, `image/gif`, `image/webp`, `image/tiff`, `image/bmp` | ❌ (parser skips) | From AI-generated markdown | **Yes — Gemini Vision** |

---

## Processing Pipeline

### Non-image documents (PDF, DOCX, TXT, MD)

```
Upload
  │
  ├─► parser.parse() [sync, in request]
  │     extracted_text saved on Document row
  │     parse_status = 'done'
  │     indexing_status = 'pending'
  │
  └─► dispatch(ingest_project_source) [async, Celery]
        indexing_status: pending → running
        │
        ├─► PageIndex.build_index(file_bytes, mime_type, filename)
        │     PDF → page-by-page tree
        │     MD  → md_to_tree (headings-aware)
        │     TXT/DOCX → paginator fallback (~1500 chars/node)
        │
        ├─► DocumentTree row written (or replaced if re-indexed)
        │     tree_json, page_texts, node_count, model
        │
        └─► indexing_status = 'done'
              └─► IF project has RU with updated_at < doc.created_at
                    → docs_stale_for_ru = true (computed at read time)
```

### Image documents (`image/*`)

```
Upload
  │
  ├─► parser.parse() [sync] → extracted_text = None (parser skips images)
  │   parse_status = 'done', indexing_status = 'pending'
  │
  └─► dispatch(ingest_project_source) [async, Celery]
        │
        ├─► Detect image/* MIME
        │
        ├─► load image bytes from storage
        │
        ├─► GeminiProvider.vision_complete(image_bytes, mime_type, IMAGE_PROMPT)
        │     → structured markdown string
        │
        ├─► doc.extracted_text = markdown  [retroactively populated]
        │   doc.parse_status = 'done'
        │
        ├─► PageIndex.build_index(markdown.encode(), "text/markdown", filename)
        │     → md_to_tree uses # headings Gemini produced
        │     → DocumentTree row written
        │
        └─► indexing_status = 'done'
              └─► stale check same as above
```

**Key benefit:** images become fully AI-grounded. Their Gemini-generated markdown
feeds into RU retrieval and artifact generation exactly like any other document.

---

## Gemini Vision Prompt

Stored in `backend/app/services/documents/image_understanding.py`.

The prompt is designed to handle every image type an analyst might upload —
architecture diagrams, ER diagrams, wireframes, whiteboard photos, screenshots,
charts, tables, handwritten notes — and produce markdown that an AI can reason over.

```
You are a meticulous technical analyst converting an image into rich, structured
Markdown for use in a software requirements platform. This output will be used
by an AI to generate specifications — completeness and precision are critical.

─── STEP 1: Identify the image type ───────────────────────────────────────────

Begin your output with a YAML front-matter block:

---
image_type: <diagram | table | document | wireframe | chart | photograph | mixed>
summary: <one sentence — what this image shows and its purpose in a project context>
---

─── STEP 2: Apply the rule for the detected type ──────────────────────────────

DIAGRAM (architecture, flowchart, ER, sequence, class, network, state machine):
  ## Overview
  2–3 sentences on the diagram's purpose and scope.

  ## Components
  Every node, entity, service, actor, or system:
  **<Name>** (<type>): <role or description>

  ## Relationships
  Every edge, arrow, or connection — one per line:
  **<Source>** → [<label / protocol / cardinality>] → **<Target>**: <meaning>
  Use → directed, ↔ bidirectional, -- association, ◇ aggregation, ◆ composition

  ## Details
  Annotations, swim lanes, colours, legends, guards, conditions, notes on nodes.

TABLE / SPREADSHEET:
  Reproduce exactly as a Markdown pipe table. Preserve every header, row label,
  value, unit, and formula. Note merged cells as HTML comments.
  Add a ## Notes section for footnotes, totals logic, or data type hints.

DOCUMENT SCREENSHOT / HANDWRITTEN NOTES:
  Transcribe ALL text verbatim, in reading order (columns before wrap).
  Preserve heading levels, numbering, bullet style, indentation.
  Unclear text: [illegible] or [unclear: best-guess].
  Do NOT paraphrase — every word visible must appear.

UI WIREFRAME / MOCKUP:
  ## Screen: <name> for each distinct screen or panel.
  List every UI element:
    - **<type>** "<label>": <state | placeholder | value | constraints>
  ## Navigation: describe any flows, arrows, or transitions between screens.
  ## Annotations: any designer notes, redlines, or spec callouts.

CHART / GRAPH:
  Chart type, title, X-axis (label + units), Y-axis (label + units).
  Every data series: name + values or trend description.
  Thresholds, reference lines, anomalies, legend entries.
  If exact values are readable state them; if approximate, say so.

PHOTOGRAPH (whiteboard, physical document, equipment photo):
  Transcribe all visible text first.
  Then describe diagrams/sketches using spatial language (top-left, centre-right).
  Note colours, circled items, arrows, underlines — they carry intent.

MIXED: split into labelled ## sections, apply the matching rule to each part.

─── STEP 3: Universal rules (apply regardless of type) ────────────────────────

1. NOTHING OMITTED. Every label, number, colour code, legend entry, footnote,
   and annotation must appear in the output.

2. PRESERVE EXACT NAMES. Do not normalise, abbreviate, or paraphrase
   identifiers, field names, system names, or technical labels.

3. CODE BLOCKS for code, SQL, JSON, YAML, regex, formulas — with language hint.

4. BLOCKQUOTES (>) for callouts, warning boxes, highlighted requirements,
   or any visually emphasised note.

5. SPATIAL RELATIONSHIPS MATTER. In diagrams, left/right/above/below positioning
   conveys architectural intent — capture it explicitly.

6. If the image is too low resolution or partially obscured, note it:
   > ⚠ Partial visibility: the lower-right section is unclear.

Output ONLY the Markdown. No preamble. No "Here is the result:". Just the content.
```

---

## Backend Changes

### No new Alembic migration needed

All required fields already exist on the `Document` model:
- `extracted_text` — used for AI-generated markdown (images) or parsed text (others)
- `indexing_status` — `pending | running | done | error`
- `index_error` — error string if PageIndex fails
- `page_count` — set during ingest

These fields ARE in `DocumentRead` Pydantic schema but are **missing from the
TypeScript `DocumentRead` interface** — that's the only schema fix needed.

### New: `BaseLLMProvider.vision_complete()`

```python
# app/services/llm/base.py
@abstractmethod
async def vision_complete(
    self,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
) -> str: ...
```

Implementations:
- **`GeminiProvider`**: call `gemini-2.5-flash` with inline image part + text prompt
- **`MockLLMProvider`**: return static markdown fixture
  (`app/services/llm/fixtures/image_understanding.md`)

### New: `app/services/documents/image_understanding.py`

```python
IMAGE_MIMES = frozenset({
    "image/png", "image/jpeg", "image/jpg",
    "image/gif", "image/webp", "image/tiff", "image/bmp",
})

IMAGE_TO_MARKDOWN_PROMPT = """...(prompt above)..."""

async def understand_image(
    image_bytes: bytes,
    mime_type: str,
    provider,        # BaseLLMProvider
) -> str:
    return await provider.vision_complete(image_bytes, mime_type, IMAGE_TO_MARKDOWN_PROMPT)
```

### Updated: `workers/tasks.py` — `_ingest_project_source()`

Add MIME branch before the existing PageIndex call:

```python
from app.services.documents.image_understanding import IMAGE_MIMES, understand_image

if doc.mime_type in IMAGE_MIMES:
    image_bytes = await storage.read(doc.storage_path)
    provider = get_provider()
    markdown = await understand_image(image_bytes, doc.mime_type, provider)
    doc.extracted_text = markdown
    doc.parse_status = "done"
    await db.flush()
    # Feed AI-generated markdown into PageIndex (md_to_tree path)
    content_for_index = markdown.encode("utf-8")
    mime_for_index = "text/markdown"
else:
    content_for_index = file_bytes
    mime_for_index = doc.mime_type

result = await corpus_index.build_index(content_for_index, mime_for_index, doc.filename)
# ... rest of tree-writing logic unchanged
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
        if d.parse_status == "done"
          and d.mime_type not in IMAGE_MIMES  # images that haven't been indexed yet don't count
          or (d.mime_type in IMAGE_MIMES and d.indexing_status == "done")
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
  Tab 1: "Text" → plain pre block
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

1. **Backend: `vision_complete` on provider** — abstract method + Gemini impl + mock fixture
2. **Backend: `image_understanding.py`** — prompt constant + `understand_image()` wrapper
3. **Backend: `ingest_project_source` branch** — MIME detection, vision call, md_to_tree path
4. **Backend: `/outline`, `/section/{node_id}`, `/file` endpoints**
5. **Backend: `docs_stale_for_ru` in `ProjectDetail`**
6. **Frontend: `DocumentRead` type** — add `indexing_status`, `page_count`, `index_error`
7. **Frontend: `useProject` polling** — refresh when any doc indexing not done
8. **Frontend: `DocumentList` icons + status indicators**
9. **Frontend: `DocumentViewer` tabs** — type-aware rendering, Structure tree, image thumbnail
10. **Frontend: stale banner** in project overview

---

## What Does NOT Change

- No new Alembic migration
- No new database tables
- App Brain tables untouched
- `ingest_project_source` task signature unchanged (still takes `doc_id`)
- `document_trees` table unchanged (images write here same as other docs)
- RU retrieval (`_retrieve_project_sections`) unchanged — it reads `extracted_text`
  and `document_trees`, both now populated for images
- Artifact retrieval unchanged — same benefit automatically

---

## Mock Strategy (CI/tests)

- `MockLLMProvider.vision_complete()` returns content of
  `app/services/llm/fixtures/image_understanding.md`
- That fixture is a realistic markdown description of a fake architecture diagram
- `ingest_project_source` with a PNG in tests → calls mock → produces tree →
  asserts `indexing_status == 'done'` and `node_count > 0`

---

## Open Questions

1. **Upload UI** — should we explicitly allow `image/*` in the UploadPanel accept
   attribute? Currently shows "PDF, DOCX, TXT". Update to "PDF, DOCX, TXT, MD,
   PNG, JPG" once image pipeline is live.

2. **Vision cost** — Gemini vision calls are billed. Consider adding a
   `max_image_size_bytes` config gate (e.g. reject images > 20 MB before calling
   Vision API).

3. **Re-indexing** — if a document is re-uploaded (same hash is blocked by dedup)
   or if the Vision prompt is updated, there's no current mechanism to re-run
   `understand_image` on existing docs. A future `POST /documents/{doc_id}/reindex`
   endpoint could handle this.

4. **Structure tab for TXT** — currently hidden because page-chunk nodes are not
   meaningful. Revisit if TXT files in practice have large structured content
   (e.g. requirements exported as text).
