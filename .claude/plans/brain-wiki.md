# Brain Wiki — Design Document

**Roadmap:** [`01-master-roadmap.md`](01-master-roadmap.md) · **Builds on:** E1 App Brain (corpus ingestion, PageIndex trees in DB, `/ask` RAG)

---

## What Problem This Solves

OpenKB names the core flaw of standard RAG precisely: *"knowledge is rediscovered from scratch on every query — nothing accumulates."* SpecForge's App Brain has the same flaw. `/ask` re-retrieves raw chunks or tree sections every call; nothing compiles, nothing is reused.

**Brain Context was a naive first attempt** at consolidation: it flattens per-doc facts into 5 fixed kinds and deduplicates them — discarding structure and narrative, and synthesising from an *already-lossy* intermediate (extracted facts) rather than the documents themselves.

**Brain Wiki rebuilds consolidation the OpenKB way:** compile the *source documents* (via the PageIndex trees already in `app_doc_trees`) into a navigable wiki of **emergent topics** with **section-level traceability**. But the wiki is only half the story — the other half is the **agentic Ask-Your-Brain orchestration** that uses it: a BA asks a question, the orchestrator reasons over the compiled concepts, **drills down into the exact PageIndex sections**, and returns a synthesised answer with **navigable, section-level citations**. The same compiled substrate then grounds **context-aware SDLC artifact generation**.

> Confirmed decisions: **both** artifact types (per-doc summaries + cross-doc concepts) · compile is **incremental on index + manual rebuild** · Brain Context is **kept alongside** for now.

---

## What OpenKB Actually Does (read from its source)

Studied from `compiler.py`, `indexer.py`, `query.py`, `agent/tools.py`, `tree_renderer.py`, `schema.py`.

**Compilation — two artifact types, straight from documents:**
- **Summary page** — one per document (short: full text; long PDF: rendered from the PageIndex tree, node titles + summaries + page ranges).
- **Concept page** — *emergent* cross-document topics (slugs like `attention`). **Multi-source concept = cross-document synthesis = the high-value output.** Never a fixed taxonomy.
- Incremental per doc: `summary → {create,update,related} plan → concurrent concept generation → code-only backlinks + index`. A **wikilink whitelist** stops dangling links. Knowledge *accumulates* — each new doc enriches existing concepts.

**Query — an agentic, multi-hop tool loop** (`build_query_agent`, `run_query`, `MAX_TURNS=50`, `parallel_tool_calls=False`):
- Tools: `read_file(path)` (any wiki page), `get_page_content(doc, "3-5,7")` (tight page ranges from a long doc — **never the whole doc**), `get_image(path)`.
- Strategy baked into the agent prompt: read `index.md` → read relevant **summaries** → read **concept** pages → for detail, follow the summary's tree structure (page ranges) and `get_page_content` the **exact pages** → synthesise a **cited** answer. *"Before each tool call, output one short sentence explaining the reason."*
- The wiki is the retrieval substrate; the agent reasons over compiled pages first and only drills to raw pages when needed.

This query loop is the part the user is most excited about — and our DB-resident PageIndex makes it tighter than OpenKB's, because concepts can pre-link the exact `(doc_id, node_id)` sections that ground them.

---

## The SpecForge Mapping — We Already Have the Hard Parts

| OpenKB | SpecForge equivalent | Status |
|---|---|---|
| `raw/` ingested files | `AppCorpusDoc` + `StorageFile` | exists |
| `sources/<doc>.md` (short text) | `DocumentMarkdown` (correlation_id = doc_id) | exists |
| `sources/<doc>.json` + PageIndex DB | `AppDocTree.tree_json` + `page_texts` (Postgres) | exists |
| PageIndex tree (titles/summaries/ranges) | `AppDocTree.tree_json` nodes | exists |
| `get_page_content(doc, pages)` | read `page_texts[start..end]` for a node | trivial (new helper) |
| vector search | `RAGRetrievalService` (pgvector `app_chunks`) | exists |
| `summaries/<doc>.md` | **`app_wiki_summaries`** | **new** |
| `concepts/<slug>.md` | **`app_wiki_concepts`** | **new** |
| `[[wikilink]]` graph | `related_slugs` + **`tree_node_refs`** | **new** |
| `run_query` agent loop | **`AppBrainAgent` (upgraded `/ask`)** | **new (upgrades existing)** |

Decisive difference: **our PageIndex lives in the DB**, so concept pages cross-reference exact `(doc_id, node_id)` nodes, and the Ask agent gets a DB-backed `get_tree_sections` tool instead of `jq` on a 100MB JSON.

---

## Architecture (compile substrate + query orchestration)

```
AppCorpusDoc ─(ingest_corpus_doc, existing)─► AppChunk (vectors) + AppDocTree (PageIndex tree)
      │
      │  compile_wiki_for_doc  (NEW: after indexing, or manual rebuild)
      ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ Summary → Concepts-plan {create,update,related} → concurrent  │
  │ concept generation (emit tree_node_refs) → code backlinks/idx │
  └──────────────────────────────────────────────────────────────┘
      ▼
  app_wiki_summaries (1/doc)  +  app_wiki_concepts (emergent topics)
      │            wikilink graph + tree_node_refs            │
      └──────────────────────────┬───────────────────────────┘
                                 ▼
            ┌──────────────  CONSUMED BY  ──────────────┐
            │                      │                     │
   (1) Brain Wiki tab     (2) Ask-Your-Brain agent  (3) SDLC artifact
       (human browse)         (drill → cite)            generation grounding
                                 │
                                 ▼  tools: list_wiki · read_concept · read_summary
                                          get_tree_sections (PageIndex drill) · vector_search
```

---

## Data Model

### `app_wiki_summaries` — one per corpus doc

```sql
CREATE TABLE app_wiki_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    doc_id UUID NOT NULL REFERENCES app_corpus_docs(id) ON DELETE CASCADE,
    brief TEXT NOT NULL,
    content_md TEXT NOT NULL,                    -- doc summary with wikilinks
    related_slugs JSONB NOT NULL DEFAULT '[]',   -- concept slugs this doc touches
    doc_type VARCHAR(20) NOT NULL,               -- 'short' | 'pageindex'
    compiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (app_id, doc_id)
);
CREATE INDEX ix_wiki_summaries_app ON app_wiki_summaries (app_id);
```

### `app_wiki_concepts` — emergent cross-document topics

```sql
CREATE TABLE app_wiki_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    app_id UUID NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    slug VARCHAR(120) NOT NULL,                  -- emergent (e.g. 'webhook_delivery')
    title TEXT NOT NULL,
    brief TEXT NOT NULL,                         -- one-liner for index + retrieval pre-filter
    content_md TEXT NOT NULL,                    -- free-form synthesis (NOT fixed sections)
    source_doc_ids JSONB NOT NULL DEFAULT '[]',  -- contributing doc UUIDs
    related_slugs  JSONB NOT NULL DEFAULT '[]',  -- cross-refs to sibling concepts
    tree_node_refs JSONB NOT NULL DEFAULT '[]',  -- [{doc_id,node_id,title,pages}] → PageIndex sections
    compiled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (app_id, slug)
);
CREATE INDEX ix_wiki_concepts_app ON app_wiki_concepts (app_id);
```

### `apps` additions
```sql
ALTER TABLE apps ADD COLUMN wiki_status VARCHAR(20) NOT NULL DEFAULT 'idle';
ALTER TABLE apps ADD COLUMN wiki_compiled_at TIMESTAMPTZ NULL;
```

`tree_node_refs` is the spine of citations and SDLC grounding: a concept claim points at the exact `(doc_id, node_id)` in `app_doc_trees.tree_json`, with its `title` + page range, ready to render as a clickable citation and to drill into during Ask.

---

## Compilation Pipeline (per doc)

Mirrors OpenKB's `_compile_concepts`, on our DB-resident PageIndex.

```python
async def _compile_wiki_for_doc(app_id, doc_id):
    # 1. Source: short → DocumentMarkdown.markdown_text ; long → flatten AppDocTree.tree_json
    #    (reuse flatten_outline from corpus_index/base.py → "[node_id] Title (pp s-e) — summary")
    # 2. app.wiki_status='running'
    # 3. SUMMARY  → DSPy DocSummaryModule → {brief, content_md, candidate_concepts}
    # 4. PLAN     → DSPy ConceptPlanModule(summary, existing_concept_briefs) → {create,update,related}
    # 5. GENERATE → asyncio.gather over create+update:
    #               DSPy ConceptPageModule(topic, source, tree_outline, valid_slugs, valid_node_ids)
    #               → {brief, content_md, related_slugs, tree_node_refs}; append doc to source_doc_ids
    #               valid_slugs + valid_node_ids = whitelists (OpenKB technique) → no dangling refs
    # 6. BACKLINKS (code only): summary.related_slugs ↔ concepts; related → add doc to source_doc_ids
    # 7. Upsert summary row + concept rows; validate tree_node_refs against AppDocTree node_ids
    # 8. app.wiki_compiled_at=now(); wiki_status='idle'
    # Error: rollback → reset wiki_status='idle' (same pattern as synthesize_brain_context)
```

**Rebuild** = clear app's wiki rows → recompile docs in `created_at` order so concepts accumulate deterministically. **Delete doc** = drop its summary; remove doc from concepts' `source_doc_ids`/`tree_node_refs`; delete now-sourceless concepts (OpenKB `remove_doc_from_concept_pages` semantics). **Mock path** = fixture summary+2 concepts, zero Vertex/PageIndex calls.

---

## ① Ask-Your-Brain — Two Modes: Quick Search + Deep Search  ★ the centrepiece

Ask Brain exposes **two modes** behind one input, chosen with a toggle:

| | **Quick Search** (lightweight) | **Deep Search** (Brain Wiki) |
|---|---|---|
| Engine | the *existing* single-shot hybrid RAG (`AppBrainRAGService.stream_answer`) — **kept as-is** | new agentic, multi-hop loop over the compiled wiki |
| Passes | one retrieval pass (tree-search → vector fallback) → one QA call | ReAct loop: concepts → drill into sections → synthesise |
| Latency / cost | fast, 1 LLM call | slower, 3–8 LLM calls (turn-capped) |
| Cross-doc synthesis | only what one retrieval pass surfaces | pre-compiled in concepts + agent multi-hop |
| Citations | section or chunk | concept → section → chunk, deep-linkable |
| Reasoning shown | none | streamed `step` trail |
| Needs wiki compiled? | no | yes (falls back to Quick if no wiki) |
| Best for | "what does X do?", quick lookups | "compare A vs B", "full picture of X", contradictions, spec grounding |

**Quick** is today's code path, untouched — the cheap default. **Deep** is the new orchestration below. The request carries `mode: 'quick' | 'deep'` (default `quick`); the endpoint branches on it. If `deep` is requested but the app has no compiled wiki, the endpoint emits a `step` notice and **degrades to Quick** (or, if `wiki_status == 'running'`, asks the user to wait).

### Deep Search — tools the agent can call (all DB-backed, all citation-emitting)

| Tool | Backed by | Purpose |
|---|---|---|
| `list_wiki()` | `app_wiki_concepts` + `app_wiki_summaries` briefs | the "index.md" — what topics/docs exist |
| `read_concept(slug)` | `app_wiki_concepts` | cross-doc synthesis + `tree_node_refs` + `related_slugs` |
| `read_summary(doc_id)` | `app_wiki_summaries` + tree outline | per-doc overview + section map |
| `get_tree_sections(doc_id, node_ids[])` | `AppDocTree.page_texts[start..end]` | **drill into exact PageIndex sections** (the "get_page_content" analog) |
| `vector_search(query, top_k)` | `RAGRetrievalService` (pgvector) | fallback for detail not surfaced by the tree |

### The loop (ReAct; `dspy.ReAct` or a hand-rolled tool loop over the Vertex provider)

```
BA question
  1. list_wiki()                         → pick concepts/summaries by brief
  2. read_concept(slug)…                 → start from compiled cross-doc synthesis (high signal)
  3. follow tree_node_refs →
     get_tree_sections(doc, [nodes])     → pull EXACT grounding sections (precise, cheap)
  4. read_summary / more concepts        → widen if needed (multi-hop, ≤ N turns)
  5. vector_search(…)                    → only for gaps the wiki doesn't cover
  6. synthesise streamed answer with layered citations
```

The agent **starts from the compiled answer** (concepts) and **drills to proof** (sections) — the opposite of today's "retrieve blindly, then read." Concepts make most questions resolve in 1–2 hops; the tree gives surgical citations; vectors are the safety net.

### Streaming + citation model (SSE, extends current `chunk/citations/done`)

New event types so the UI shows the agent *thinking*, then answering:
- `step` — one-line reasoning before each tool call (*"Reading concept: Webhook Delivery…"*, *"Drilling into Retry Semantics §3.2…"*) — mirrors OpenKB's narrated tool calls.
- `chunk` — final answer tokens (streamed).
- `citations` — structured, **three granularities**:
  - **Concept** — `[[concepts/webhook_delivery]]` (the synthesis used)
  - **Section** — `{doc, node_id, title, pages}` → renders as a chip that **deep-links into the Corpus markdown preview at that section** (`?section=node_id`)
  - **Chunk** — `{doc, chunk_no}` fallback
- `done`.

"Awesome citations" = section-level, navigable, and provenance-layered (concept → section → page), not just `[Citation 3]`.

### Why Deep beats Quick
Single-shot hybrid can't reason about *what* to fetch and cites whole chunks. The agent reasons, fetches tight sections, and cites at section granularity — and because concepts are pre-synthesised cross-doc, answers reflect knowledge spanning multiple documents that a single retrieval pass would miss.

### How each mode behaves across MULTIPLE documents

This is the crux — most apps have several corpus docs (e.g. an architecture PDF, an API spec, an ops runbook). Both modes already span all of an app's docs, but very differently:

**Quick Search — flat, similarity-ranked across all docs.**
- Tree-search (`source_tree_search`) flattens *every* doc's tree into one outline and the LLM picks the top-K sections regardless of which doc they're in. Vector search runs over *all* `app_chunks WHERE app_id` and returns the top-K most similar chunks.
- So it *touches* multiple docs, but it's **flat and budget-capped**: it returns the K most-similar fragments. If doc A is very on-topic it can crowd out a key sentence in doc B; nothing *connects* a fact in A with a related fact in B. Good for "where is X?", weak for "reconcile X across the corpus."

**Deep Search — cross-document synthesis is pre-compiled, then verified.**
- The whole point of the wiki is that a **concept already merges multiple docs**: `source_doc_ids` lists every contributing doc and `tree_node_refs` point into *several docs'* trees. So a question that maps to a concept gets a cross-doc answer **without** the agent having to re-discover the links at query time — that synthesis happened at compile.
- The agent then: `list_wiki()` (sees all concepts + all doc summaries) → `read_concept()` (cross-doc body) → `get_tree_sections(docA,[…])` **and** `get_tree_sections(docB,[…])` to pull exact grounding from *each* contributing doc → optionally `read_summary(doc)` to widen → synthesise.
- Result for multi-doc questions:
  - **"Compare A's limits with B's"** → the agent reads both docs' relevant sections and contrasts them, citing each.
  - **"What's the full picture of webhooks?"** → one concept already spans the 3 docs that mention webhooks; citations fan out across all 3.
  - **Contradictions** (doc A: 500 TPS; doc B: 1000 TPS) → surfaced because both feed the same concept (and a future lint pass can flag it).
- Each citation names its doc, so a multi-doc answer is transparently attributed: `[Webhook Delivery] → [api-spec.pdf §3.2] + [runbook.pdf §6]`.

**Edge cases (multi-doc):** a brand-new doc that hasn't been compiled into the wiki yet is invisible to Deep until recompiled (Quick still sees its chunks immediately) — so the stale banner + "Rebuild" matters. Very large corpora: cap `list_wiki()` to concept briefs (already lightweight) and let the agent pull bodies on demand; cap agent turns so cost stays bounded regardless of doc count.

### Phase-2 multi-turn chat
OpenKB's `build_chat_agent` keeps the same tools across turns. Our `AskPanel` is single-shot today; a chat variant (retain prior turns + retrieved context) is a natural follow-up, letting a BA refine ("now compare that to the batch API").

---

## ② Context-Aware SDLC Artifact Generation

SpecForge's purpose is turning requirements into specs grounded in App Brains. Today the spec skills (`functional_spec`, `technical_spec`, `user_stories`, `reviewer`) are grounded in project requirements ± raw facts. **Brain Wiki makes them context-aware:**

- Before generation, run the **same retrieval orchestration** for the apps in the project's scope: pull the relevant concept pages (cross-doc, deduplicated) + their `tree_node_refs`.
- Inject that compiled context into the spec skill's template as **grounding with citations**.
- The generated spec then:
  - reflects **cross-document synthesis** (e.g. a constraint in doc A + an integration in doc B combined correctly — impossible from one chunk),
  - carries **section-level provenance** (each generated requirement can cite `doc › section §x.y`),
  - stays consistent across artifacts because all of them draw from the same compiled concepts.

Concretely: a `wiki_grounding` retrieval step feeds `app_brain_context` into the existing generation skills; the `reviewer` skill can flag spec claims that lack a `tree_node_ref` (ungrounded assertions). This is how the App Brain stops being a side-feature and becomes the substrate every artifact is generated from.

---

## ③ 360-Degree Understanding of the Application

The three compiled layers are three orthogonal views of the same app — together, a full picture:

| Axis | Surface | Question it answers |
|---|---|---|
| **Breadth** — Documents | `app_wiki_summaries` | "What does each source say? Is coverage complete?" |
| **Depth** — Topics | `app_wiki_concepts` | "What is the synthesised, cross-doc understanding?" |
| **Proof** — Structure | `AppDocTree` via `tree_node_refs` | "Where exactly is this grounded?" |

A BA flow: browse **concepts** to understand fast → see **which documents** back each concept (coverage + gaps) → **drill to the exact section** for proof. Breadth + depth + provenance = 360°. The Ask agent traverses the same three axes automatically; the Wiki tab exposes them for manual exploration; SDLC generation consumes all three.

Future "wiki health" (OpenKB's `lint`): surface **contradictions** across documents (doc A says max 500 TPS, doc B says 1000) and **orphan concepts** — turning the 360° view into an active completeness/consistency check on the app's knowledge.

---

## DSPy Modules

`backend/app/services/skills/wiki_compiler/dspy_wiki.py` (reuses `_configure_dspy()`):

```python
class DocSummary(BaseModel):        brief: str; content_md: str; candidate_concepts: list[str]
class ConceptAction(BaseModel):     slug: str; title: str
class ConceptPlan(BaseModel):       create: list[ConceptAction]; update: list[ConceptAction]; related: list[str]
class TreeNodeRef(BaseModel):       doc_id: str; node_id: str; title: str; pages: str
class ConceptPage(BaseModel):       brief: str; content_md: str; related_slugs: list[str]; tree_node_refs: list[TreeNodeRef]
# DocSummarySignature / ConceptPlanSignature / ConceptPageSignature — emergent topics, free-form prose,
# cite node_ids that ground each claim, cross-link only whitelisted slugs. NO fixed section template.
```

`backend/app/services/skills/app_brain_agent/` — the Ask orchestrator. Prefer **`dspy.ReAct`** with the five typed tools above (DSPy 3.x native tool-use); fall back to a hand-rolled provider tool loop if streaming needs finer control. Tools return both content and structured citation stubs the streamer emits.

---

## Backend — Tasks & API

**Tasks** (`workers/tasks.py`): `compile_wiki_for_doc(app_id, doc_id)` (dispatched at tail of `ingest_corpus_doc`, after tree build) · `rebuild_app_wiki(app_id)`.

**Endpoints** (`app/api/apps.py`):
```
GET  /{app_id}/wiki                  → {concepts:[{slug,title,brief}], summaries:[{doc_id,brief}], status, compiled_at}
GET  /{app_id}/wiki/concepts/{slug}  → full concept (content_md, source_doc_ids, related_slugs, tree_node_refs)
GET  /{app_id}/wiki/summaries/{doc}  → full summary
POST /{app_id}/wiki/rebuild          → 202; dispatch rebuild_app_wiki        (require_app_write_access)
POST /{app_id}/ask                   → body adds mode:'quick'|'deep' (default 'quick')
                                        quick → existing single-shot stream (unchanged)
                                        deep  → agentic loop; SSE step/chunk/citations/done
GET  /{app_id}/corpus/{doc}/tree     → tree outline (node_id,title,pages) to power section deep-links (if not already exposed)
```

**RAG service** (`app/services/rag/`): keep `AppBrainRAGService.stream_answer` untouched as the **Quick** path. Add a new `AppBrainAgent` (e.g. `app/services/rag/agent.py`) for **Deep** that calls `RAGRetrievalService` + tree retrieval **as tools** (`vector_search` / `get_tree_sections`) plus the wiki readers. The `/ask` endpoint dispatches to one or the other on `mode`. Deep falls back to Quick when no wiki is compiled.

---

## Frontend

- **Wiki tab** (`app/apps/[id]/page.tsx`): `{ key:'wiki', label:'Brain Wiki', icon: BookMarked }`.
- **`BrainWiki.tsx`** — two-panel (CorpusManager pattern): left rail **Concepts** + **Documents**; right panel renders `content_md` with `MarkdownLine` extended for `[[wikilinks]]` (clickable nav) and `tree_node_refs` ("Grounded in" chips → deep-link to Corpus section). Header: counts, compiled time, **Rebuild** (poll while running), stale banner.
- **`AskPanel.tsx`** upgrade: a **Quick / Deep toggle** (segmented control) next to the input — Quick is the default and behaves exactly as today; Deep sends `mode:'deep'`. In Deep mode, render `step` events as a live "research trail" above the streamed answer and `citations` as concept / section / chunk chips — **section chips deep-link** into the Corpus markdown preview at `?section=node_id`. If the wiki isn't compiled, show a subtle hint ("Deep search needs a compiled wiki — Quick used") instead of an error.
- **`CorpusManager.tsx`**: accept `?section=node_id` to scroll/highlight the target section (shared deep-link target for wiki + citations).
- **Types/api** (`lib/types.ts`, `lib/api.ts`): wiki types; `getWiki`/`getWikiConcept`/`getWikiSummary`/`rebuildWiki`; extend the SSE parser for `step` + structured citations; extend `AppDetail` with `wiki_status`/`wiki_compiled_at`.

---

## Relationship to Brain Context (kept alongside, for now)

| | Brain Context | Brain Wiki |
|---|---|---|
| Source | per-doc facts (lossy) | **source docs + PageIndex trees** |
| Topics | 5 fixed kinds | **emergent** |
| Traceability | `source_fact_ids` | `source_doc_ids` + **section-level `tree_node_refs`** |
| Graph | none | `[[wikilink]]` concept↔summary↔section |
| Feeds `/ask` | no | **yes — as the agent's primary substrate** |
| Feeds spec gen | no | **yes — context-aware grounding** |

Both ship; evaluate, then decide if Brain Context retires. The per-doc **Facts** tab stays regardless (separate lens).

---

## Phasing

- **Phase 1 — Compile + Browse**: data model, `compile_wiki_for_doc` + `rebuild`, Wiki tab. No `/ask` change yet.
- **Phase 2 — Ask-Your-Brain, two modes**: keep **Quick** (existing single-shot RAG) as the default; add **Deep** (agentic wiki loop) behind a toggle, with `step`/section citations, research trail, deep-link citations, and graceful fallback to Quick when no wiki. *(the centrepiece)*
- **Phase 3 — SDLC grounding**: `wiki_grounding` retrieval injected into spec skills; reviewer flags ungrounded claims.
- **Phase 4 — Health & chat**: contradiction/orphan lint; multi-turn Ask chat.

Cost: incremental compile + agentic Ask add LLM calls. Gate auto-incremental behind a per-app toggle if heavy; cap agent turns (e.g. ≤ 8) and prefer concept hits before drilling.

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `backend/alembic/versions/0012_brain_wiki.py` | Migration: 2 tables + 2 apps columns |
| `backend/app/models/wiki.py` | `AppWikiSummary`, `AppWikiConcept` |
| `backend/app/models/__init__.py` | Register both |
| `backend/app/models/app.py` | `wiki_status`, `wiki_compiled_at` |
| `backend/app/schemas/app.py` | Wiki read schemas + `WikiIndexResponse`; extend `AppDetail` |
| `backend/app/api/apps.py` | `/wiki*` endpoints; upgrade `/ask`; `/corpus/{doc}/tree` |
| `backend/app/services/skills/wiki_compiler/dspy_wiki.py` | DocSummary/ConceptPlan/ConceptPage modules |
| `backend/app/services/skills/app_brain_agent/agent.py` | **Ask-Your-Brain ReAct agent + 5 tools** |
| `backend/app/services/rag/rag_service.py` | Refactor `stream_answer` → agent loop; emit `step`/structured citations |
| `backend/app/services/rag/tree_retrieval.py` | Expose `get_tree_sections(doc_id, node_ids)` from `page_texts` |
| `backend/app/services/corpus_index/base.py` | Reuse `flatten_outline` for compile + agent outlines |
| `backend/workers/tasks.py` | `compile_wiki_for_doc` + `rebuild_app_wiki`; dispatch in `ingest_corpus_doc` |
| `frontend/lib/types.ts` | Wiki types; SSE `step`/citation types; extend `AppDetail` |
| `frontend/lib/api.ts` | `getWiki`/`getWikiConcept`/`getWikiSummary`/`rebuildWiki`; SSE parser update |
| `frontend/app/components/BrainWiki.tsx` | Two-panel wiki browser (+ wikilink/tree-ref rendering) |
| `frontend/app/components/AskPanel.tsx` | Research-trail steps + layered, deep-linking citations |
| `frontend/app/components/CorpusManager.tsx` | `?section=node_id` deep-link target |
| `frontend/app/apps/[id]/page.tsx` | Add Wiki tab; wire `<BrainWiki>` |

---

## Verification

1. Index a doc → `compile_wiki_for_doc` → 1 summary + ≥1 concept; `tree_node_refs` resolve to real `AppDocTree` node_ids.
2. Index an overlapping 2nd doc → an existing concept is **updated** (its `source_doc_ids` now lists both) — cross-doc accumulation works.
3. Wiki tab: Concepts + Documents rails render; concept body is free-form (not fixed sections); "Grounded in" chip deep-links to the right Corpus section.
4. **Ask**: a specific BA question streams `step` reasoning, drills via `get_tree_sections`, and returns an answer with **concept + section + chunk** citations; section chips navigate to the exact markdown section.
5. Ask answer reflects facts spanning **two documents** (proves cross-doc synthesis beats single-pass retrieval).
6. Re-index a doc → stale banner → Rebuild clears it.
7. Spec generation for a project whose app scope has a compiled wiki → generated spec includes wiki-grounded, **cited** content (Phase 3).
8. Mock path (`LLM_PROVIDER=mock`): compile + ask run with fixtures, zero Vertex/PageIndex calls (CI stays green).
9. Delete a corpus doc → summary removed; concepts drop it from `source_doc_ids`/`tree_node_refs`; sourceless concepts deleted.
