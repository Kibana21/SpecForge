# PageIndex Structure View — Design Document

**Where:** a new tab in the Corpus Documents right panel, next to **Preview** and **Facts**.
**What:** an interactive visualization of a document's **PageIndex reasoning tree** — the hierarchy of sections (TOC), their page ranges and summaries, and how nodes connect (parent → child). This makes the otherwise-invisible structure that powers Brain Wiki grounding, Deep Search drilling, and section citations tangible and explorable.

---

## Data source (already stored)

`AppDocTree.tree_json` per corpus doc, shape:
```json
{ "nodes": [
    { "node_id": "0002", "title": "Event-Driven Enterprise Payment Fabric",
      "summary": "…", "start_index": 1, "end_index": 2,
      "nodes": [ {…children…} ] }
] }
```
- Each node: `node_id`, `title`, `summary`, `start_index`/`end_index` (page range), optional `nodes` (children).
- `AppDocTree` also has `node_count`, `model`, `page_texts` (per-page text — already fetched per node via the existing `/corpus/{doc}/section/{node_id}` endpoint).

**Reality check from current data:** short docs (e.g. PayHub's 5-page PDF) produce a **flat** tree — 11 sections, no nesting. Long structured PDFs produce real hierarchy. Heading-less docs get a synthetic one-node-per-page fallback. **The viz must look good for all three** (flat, nested, fallback).

---

## Backend — one new endpoint

`GET /api/apps/{app_id}/corpus/{doc_id}/tree` → returns a UI-ready structure:
```json
{
  "has_tree": true,
  "node_count": 11,
  "model": "vertex_ai/gemini-2.5-flash",
  "doc_name": "Payhub_Advanced_Architecture_Addendum.pdf",
  "page_count": 5,
  "nodes": [ { "node_id", "title", "summary", "pages": "1-2", "depth": 0, "children": [...] } ]
}
```
- Reads `AppDocTree` for the doc (404-guard on the doc; `has_tree:false` when no tree row, e.g. doc indexed before PageIndex or vector-only).
- Normalizes `tree_json` into `{node_id, title, summary, pages, depth, children}` (compute `pages` from start/end, `depth` from nesting). Keeps it nested.
- Lightweight: titles + summaries + page ranges only (no full section text — that's lazy-loaded via the existing section endpoint on click).
- Auth: `require_app_access`. Reuses `iter_nodes`/tree helpers from `corpus_index/base.py`.

No migration, no new tables — purely a read over existing data.

---

## Frontend — new "Structure" tab

In `CorpusManager.tsx`:
- Extend the right-panel tab state `'preview' | 'facts'` → add `'structure'`; add a **Structure** tab (icon: `Network`/`GitFork`) to the tab bar, and a `<DocStructurePanel>` branch.
- `<DocStructurePanel appId docId docName>` fetches `getDocTree(appId, docId)` when selected; shows skeleton → graph, or an empty state ("No PageIndex tree — re-index this document") when `has_tree:false`.

### The visualization
Each node renders: **title**, a **page-range pill** (`pp 1-2`), and its **summary** (on hover/expand). Visual encoding:
- **Depth** → color/indent (root sections vs subsections).
- **Page span** → a small bar so you can see which sections are large.
- **Flat trees** → synthesize a **Document root** node so it reads as a hub-and-spoke (Document → 11 sections) instead of 11 loose nodes.

Interactions:
- **Click a node** → opens a side detail (reusing the existing `getCorpusSection` endpoint) showing the section's real text + a "Open in Preview" jump.
- **Hover** → summary tooltip.
- **Collapse/expand** subtrees; **pan/zoom** for big trees; a header with `node_count · model · page_count`.

---

## Visualization approach — decision needed

Three viable ways to render it; they differ in "wow", interactivity, and dependency weight:

1. **React Flow + dagre layout** (add `reactflow` + `dagre`) — a true interactive node-graph: drag, pan, zoom, minimap, animated edges. The most "brilliant/graph-like", best for nested trees and large docs. Cost: ~2 new deps.
2. **Custom SVG/CSS mind-map tree** (no deps) — hand-crafted left-to-right collapsible tree with curved connector lines, depth colors, page-span bars, animated expand. On-brand with the app's design language, zero dependencies, lighter. Slightly less "draggable-graph" feel.
3. **D3 hierarchy radial/tree** (add `d3-hierarchy`, small) — an elegant radial or top-down dendrogram. Beautiful, compact for flat docs (sections radiating from the doc), but less interactive unless we add pan/zoom ourselves.

My recommendation: **React Flow** if you want the full interactive "graph" feel you described; **custom SVG** if you'd rather keep zero deps and a bespoke look. (Asking below.)

---

## Edge cases
- **No tree row** (`has_tree:false`): empty state with a "Re-index" hint (PageIndex tree is built during indexing when `app_brain_use_pageindex` is on).
- **Flat tree**: synthesize a Document root → sections so it's still a connected graph.
- **Fallback tree** (heading-less → one node per page): renders as Document → page-1 … page-N; still useful as a page map.
- **Large trees**: pan/zoom + collapse; cap initial expanded depth (e.g. depth ≤ 2) and lazy-expand.

---

## Files to create / modify
| File | Change |
|------|--------|
| `backend/app/api/apps.py` | New `GET /{app_id}/corpus/{doc_id}/tree` endpoint |
| `backend/app/schemas/app.py` | (optional) `DocTreeResponse` schema, or inline dict |
| `frontend/lib/types.ts` | `DocTreeNode`, `DocTreeResponse` types |
| `frontend/lib/api.ts` | `getDocTree(appId, docId)` |
| `frontend/app/components/CorpusManager.tsx` | Add `'structure'` tab + `<DocStructurePanel>` |
| `frontend/app/components/DocStructurePanel.tsx` | **New** — the tree/graph viz (+ click→section detail, reuses `getCorpusSection`) |
| `frontend/package.json` | (only if React Flow / d3 chosen) add the dep |

---

## Verification
1. Open a doc with a PageIndex tree → **Structure** tab renders the section graph with titles + page ranges.
2. Flat doc (PayHub) → shows Document → 11 sections cleanly (hub), not loose nodes.
3. Click a node → its real section text loads (via `getCorpusSection`); "Open in Preview" jumps to the doc.
4. Doc without a tree → clean empty state with re-index hint.
5. Nested/long doc → hierarchy renders with collapse/expand + pan/zoom; deep trees stay readable.
