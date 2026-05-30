# Implementation Plan — E2 Intelligent Intake (Understanding Studio, Project Wiki, Clarification Engine, Provenance)

> The HOW for `.claude/prd/prd-e2-intelligent-intake-project-wiki.md` (the WHAT/WHY).
> Self-contained: signatures, models, migrations, component specs, phases.

## Context

Today's Requirement Understanding (RU) asks fill-in-the-blanks questions, never
detects contradictions/ambiguities/gaps, ignores newly-added docs, and its
understanding is siloed (never reaches CB/BRD/FRS generation). This plan turns
intake into a system that genuinely understands the corpus, asks brilliant
source-cited questions, and pours that understanding (fully traceable) into every
downstream stage — with an **amazing, intuitive** Understanding Studio UI and a
**rock-solid, reuse-first backend core**. Build is additive and mock-first so
nothing existing breaks (the `ru_validated` gate, the App Brain wiki, current RU,
and all tests stay green).

**Verified key facts** (file:line confirmed during planning):
- Alembic head = `0019_frs_artifact` → **new migrations are `0020`, `0021`**.
- App-wiki compile logic = `backend/workers/tasks.py::_compile_one_doc` (620–781) + `_compile_wiki_for_doc`/`_rebuild_app_wiki`/`_check_wiki_health` + helpers `_build_tree_context`/`_slugify`/`_strip_node_refs` (578–617). DSPy runners in `wiki_compiler/dspy_wiki.py` are app-agnostic (plain strings).
- `GapQuestion` (`backend/app/models/gap.py`) already has `resolved`, `resolution_text`, `resolved_at`, `section`, `source` (default `"gap_detector"`), `category`/`severity` Postgres enums. RU writes `source="interview"`.
- Context chokepoint: `projection.py::project_for_unit` builds `combined_parts = [App Brain, Project Documents, cb_context, (brd_context)]` — append the intake block here.
- RU frontend = `frontend/app/components/InterviewPanel.tsx` + `useUnderstanding` hook + `interview/page.tsx`; data shapes in `lib/types.ts` (`RequirementUnderstanding`, `InterviewMessage`, `UnderstandingDetail`).
- Reusable FE: `ThreePanel.tsx` (responsive rail/center/right), `Markdown.tsx`, `BrainWiki.tsx` (markdown + `GroundedIn` + section viewer), `FrsTraceChip.tsx`, `FrsCoverageGalaxy.tsx` (SVG column-graph), `BrdConfettiBurst.tsx`, `Badge`/`Button`, `useReducedMotion`, sonner `toast`.
- App-wiki section drill-down = `api.apps.getCorpusSection(appId, docId, nodeId)`; projects need a parallel section endpoint over `DocumentTree.page_texts` + `node_text()`.

---

## A. BACKEND CORE (reuse-first, additive)

### A1 — `compile_core.py`: one parameterized wiki compiler (protect E1 by copy)
New `backend/app/services/wiki/compile_core.py`. Lift the proven body of
`_compile_one_doc` (tasks.py:620–781) into a model-agnostic function driven by a
small config; **App Brain keeps its own `_compile_one_doc` untouched** (copy, not
refactor — E1 tests must stay byte-for-byte).

```python
@dataclass(frozen=True)
class WikiScope:
    summary_model: type   # AppWikiSummary | ProjectWikiSummary
    concept_model: type   # AppWikiConcept | ProjectWikiConcept
    scope_col: str        # "app_id" | "project_id"
    summary_doc_col: str  # "doc_id" | "document_id"

async def compile_doc_into_wiki(
    db, *, scope_id, scope_name, doc_id, doc_name,
    tree_json: dict | None, source_text: str, scope: WikiScope, settings,
) -> int:
    """Summary → concept-plan → parallel concept-page → whitelist-validate
    tree_node_refs → upsert summary + concepts. Returns concepts_touched."""
```
Reuse verbatim: `run_doc_summary/run_concept_plan/run_concept_page` (dspy_wiki),
`iter_nodes/find_node/node_text` (corpus_index/base), and copy the helpers
`_build_tree_context/_slugify/_strip_node_refs` into a shared
`backend/app/services/wiki/tree_text.py` (import them from App Brain too in a
later cleanup; for now App Brain keeps its private copies). Port the **mock
branch** verbatim (deterministic summary/plan/page; `tree_node_refs` = first
valid node). Project source text = `Document.extracted_text or tree_outline`,
capped 50k; `doc_type = "pageindex" if node_count>0 else "short"`.

### A2 — Project Wiki models + migration `0020`
New `backend/app/models/project_wiki.py` mirroring `models/wiki.py` exactly,
swapping `app_id→project_id` and the summary FK `doc_id (app_corpus_docs) →
document_id (documents)`:
- `ProjectWikiSummary`: `project_id`, `document_id`, `brief`, `content_md`, `related_slugs` JSONB, `doc_type`, `compiled_at`; unique `(project_id, document_id)`; index `(project_id)`.
- `ProjectWikiConcept`: `project_id`, `slug` VARCHAR(120), `title`, `brief`, `content_md`, `source_doc_ids` JSONB, `related_slugs` JSONB, `tree_node_refs` JSONB, `compiled_at`; unique `(project_id, slug)`; index `(project_id)`.

Register both in `backend/app/models/__init__.py`. Add to `Project` model:
`wiki_status` VARCHAR(20) default `'idle'`, `wiki_compiled_at` TIMESTAMPTZ,
`wiki_health` JSONB. Migration `0020_project_wiki.py` copies the
`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE … ADD COLUMN IF NOT EXISTS` style
from `0012`/`0013` (FKs CASCADE; `down_revision="0019"`).

### A3 — Project-wiki Celery tasks + ingest trigger
In `backend/workers/tasks.py` (mirror app-wiki tasks, via `_run_async`):
- `compile_project_wiki_for_doc(project_id, document_id)` → loads `Project`+`Document`, sets `project.wiki_status='running'`, `compile_doc_into_wiki(... scope=PROJECT_WIKI_SCOPE)`, sets `wiki_compiled_at`/`idle`, error-rollback resets status.
- `rebuild_project_wiki(project_id)` → delete project wiki rows, recompile docs ordered by `Document.created_at` (deterministic accumulation).
- `check_project_wiki_health(project_id)` → orphan calc + `run_wiki_lint` (validate slugs), store `Project.wiki_health`.
- **Trigger:** at the success tail of `_ingest_project_source` (tasks.py ~1108), `dispatch(compile_project_wiki_for_doc, str(doc.project_id), str(doc.id))` (TCP-preflight `dispatch`, not `.delay`). At the end of `_compile_project_wiki_for_doc`, chain `dispatch(run_project_clarification, project_id, "new_document")`.

### A4 — Clarification Engine (DSPy + orchestrator)
**`dspy_intake.py` (additive):**
```python
class ClarificationItem(BaseModel):
    question: str
    kind: Literal["contradiction","ambiguity","gap"]
    category: Literal["scope","data","security","integration","ux"]   # matches GapCategory
    severity: Literal["blocker","major","minor"]                        # matches GapSeverity
    rationale: str = ""
    citations: list[str] = []        # canonical tokens (see A9)
class ClarificationResult(BaseModel): items: list[ClarificationItem] = []
class CorpusClarifierSignature(dspy.Signature):
    """Emit only genuine contradiction/ambiguity/gap questions a BA must resolve;
    each cites conflicting/missing sources; never re-ask answered Q&A; [] if clear."""
    project_name, wiki_concepts, detected_contradictions, brief_context,
    app_brain, qa_pairs  → result: ClarificationResult
```
`CorpusClarifierModule` (ChainOfThought) + `run_corpus_clarifier(...)` with
`if _is_mock(): return mock_fixture("corpus_clarifier")` and new fixture
`backend/app/services/llm/fixtures/corpus_clarifier.json` (1 contradiction + 1
ambiguity + 1 gap, with citation tokens) registered in the mock fixture map.

**New `backend/app/services/understanding/clarifier.py`:**
```python
async def run_clarification(project_id, db, *, trigger: Literal["interview","new_document"]) -> list[dict]:
    concepts = <ProjectWikiConcept rows>
    contradictions = await run_wiki_lint(name, [ConceptForLint(...)]) if len(concepts)>=2 else {"contradictions":[]}
    grounding = await build_intake_grounding(project_id, db)     # A5
    items = (await run_corpus_clarifier(...)).get("items", [])
    # idempotent replace of UNRESOLVED source="clarifier" rows; keep resolved
    delete GapQuestion where project_id, source="clarifier", resolved=False
    insert GapQuestion(source="clarifier", kind=..., category=..., severity=..., citations=..., rationale=..., section=primary_citation)
```

### A5 — Full-context grounding (G8) — shared helper
New `build_intake_grounding(project_id, db) -> dict` in
`backend/app/services/understanding/grounding.py`, the single source of truth used
by RU `generate()`, the clarifier, and the new-doc trigger:
- `brief` = `project.description` + latest `CbDiscoverEnhancedBrief` (if any).
- `doc_breadth` = `docs_layer.outline_text`; `doc_depth` = `depth_search(probe)`.
- `app_brain` = `gather_app_brain_context(db, project_id)` (wiki concepts) **plus** `load_app_facts_for_project(...)` (facts), concatenated.
- `qa` = existing transcript Q&A.

**RU change (additive):** add `app_brain` and `brief` InputFields to
`RequirementUnderstandingSignature`; `orchestrator.generate()` populates them via
`build_intake_grounding` (replaces the current single `tree_search` + facts-only
grounding). Mock path returns the fixed fixture regardless → RU tests unaffected.

### A6 — Trigger clarifier from the interview
In `understanding/orchestrator.py::generate()`, after `_persist()` commits, call
`run_clarification(project_id, db, trigger="interview")` inline (1 lint + 1
clarifier call; the project wiki is precompiled on upload). Empty wiki → clarifier
degrades to brief+app_brain+qa.

### A7 — `GapQuestion` additive columns + migration `0021`
Add nullable `kind VARCHAR(20)`, `citations JSONB DEFAULT '[]'`, `rationale TEXT`
to `models/gap.py` and migration `0021_clarification_meta.py`
(`ADD COLUMN IF NOT EXISTS`, `down_revision="0020"`). Existing inserts/reads
unaffected (RU's `source="interview"` rows simply leave them default).

### A8 — Intake Context Pack (downstream amplification)
New `backend/app/services/context/intake_layer.py`:
```python
@dataclass
class IntakeLayer:
    understanding: dict; resolved_clarifications: list[dict]; wiki_concepts: list[dict]
    formatted_context: str; citation_index: dict
async def build_intake_layer(project_id, db) -> IntakeLayer
```
Pulls `RequirementUnderstanding.content_json` (today unused downstream),
`GapQuestion(source="clarifier", resolved=True)`, and `ProjectWikiConcept` briefs;
formats a `=== Project Understanding (Intake) ===` block in the same `Q:/A:` style
as `cb_layer._format_discover_qa`, with citation tokens inline.
**Wire:** add `intake: IntakeLayer` to `ProjectContextBundle`; build it
sequentially in `gather_project_context` (single-session rule); in
`project_for_unit`, insert `"=== Project Understanding (Intake) ===\n" +
bundle.intake.formatted_context` into `combined_parts` (after Project Documents,
before cb_context). One chokepoint → CB, BRD, and FRS all consume it.

### A9 — Provenance backend
- **Citation tokens** (canonical): `S:<document_id>:<node_id>`, `C:<concept_slug>`, `F:<app_fact_id>`, `Q:<gap_question_id>`. Concept `tree_node_refs` map to `S:` tokens; clarification `citations` carry `S:/C:/F:`.
- **Resolver** `backend/app/services/provenance/lineage.py`: `resolve_token(token, project_id, db)` → `{kind, label, doc_id?, node_id?, excerpt?}`; `lineage(project_id, node, direction)` walks: source↔concept (via `tree_node_refs`), concept/source↔clarification (via `citations`), and downstream artifact rows (extend BRD/FRS `traceability` `target_kind` with `source_section|project_concept|intake_clarification`).
- **API** `GET /projects/{id}/provenance?node=<token>&direction=backward|forward` (read-only).

### A10 — New/extended API endpoints
- Project wiki (mirror `apps.py` wiki routes): `GET /projects/{id}/wiki`, `/wiki/concepts/{slug}`, `/wiki/summaries/{doc_id}`, `POST /wiki/rebuild`, `POST /wiki/health`.
- Project source section drill-down: `GET /projects/{id}/sources/{doc_id}/section/{node_id}` → `{doc_name, title, pages, text}` via `find_node` + `node_text` over `DocumentTree`.
- Clarification answer: `POST /projects/{id}/understanding/clarifications/{gq_id}/answer` → sets `resolution_text/resolved/resolved_at`; returns updated understanding detail.
- Provenance (A9).

### A11 — Mock-first + tests
Fixtures: `corpus_clarifier.json`; `compile_core` mock branch; `run_wiki_lint`
already mock-returns `{contradictions:[]}`. New backend tests (real PG+Redis, mock
LLM): project-wiki compile populates `ProjectWikiConcept`; clarifier writes cited
`source="clarifier"` rows and never deletes `source="interview"`; `ru_validated`
gate still 409s; `build_intake_layer` content + RU understanding + concepts appear
in `project_for_unit(...).combined`; `/provenance` resolves a
source→concept→clarification chain both directions.

---

## B. FRONTEND — the Understanding Studio (make it amazing)

Rework `frontend/app/components/InterviewPanel.tsx` into `UnderstandingStudio`
(keep the file path/route; `interview/page.tsx` renders it). Reuse `ThreePanel`,
`Markdown`, `BrainWiki` internals, `FrsTraceChip`, `FrsCoverageGalaxy` pattern,
`BrdConfettiBurst`, `Badge`/`Button`, `useReducedMotion`, sonner. **Invoke the
`frontend-design` skill when building the hero surfaces** (Studio shell,
Contradiction card, Understanding meter, LineageMap) to push visual quality.

### B0 — What makes this UI *amazing* (the bar)
- **A living understanding, not a form.** The center Canvas visibly *fills in* and gains confidence as you answer — the product is thinking with you.
- **The contradiction moment is the showpiece**: two real source quotes face-to-face with a connective `⟂`, one-tap resolution, instant drill to the exact page.
- **A single emotional signal**: the `◍ Understanding` meter sweeps upward with spring motion as confidence rises and questions resolve; crossing the threshold pulses the Validate button.
- **Everything is sourced**: every card, question, and answer wears trace chips that glow on hover and drill to the source — provenance feels tangible.
- **The seal**: confetti + an "Understanding Sealed" card that names exactly what now powers downstream — a satisfying close.
- **Calm + fast**: skeleton shimmer on first load, optimistic answer submit, 60fps spring transitions all gated by `useReducedMotion()`; full keyboard nav; WCAG-AA contrast on every pair.

### B1 — Layout (reuse `ThreePanel`)
```
Header: ← Back · Requirement Understanding · ◍ 72% understood · [✦ Wiki] [Provenance] [✓ Validate]
ThreePanel:
  left  (20%) IntakeSourceRail   — Sources (ingest/wiki status) + Wiki concept index
  center(55%) UnderstandingCanvas — RU field cards (confidence bars + trace chips)  ⇄  ProjectWiki (toggle)
  right (25%) ClarificationStream — typed, prioritized questions + filters
```

### B2 — Components (props/state)
| Component | New/Reuse | Props / Notes |
|---|---|---|
| `UnderstandingStudio` | rework `InterviewPanel` | `{projectId,onBack?,onValidated?}`; owns `useUnderstanding` + new `useClarifications`/`useProjectWiki`; header meter + Validate/seal; center toggle Canvas⇄Wiki |
| `UnderstandingCanvas` + `RuFieldCard` | new | renders `content_json` fields (Objective, Stakeholders & Roles, Target Process, Functional Areas, Systems & Integrations, Risks, Scope, Assumptions); each card: title, confidence bar from `field_confidence[field]`, `IntakeTraceChip[]` from citations, amber edge + count when an open clarification targets that field |
| `ClarificationStream` + `ClarificationCard` + `IntakeContradictionCard` | new | list sorted severity→kind; filter chips `All/⚠ Contradiction/❓ Ambiguity/◌ Gap/✓ Answered`; contradiction card shows two source quotes + `[view ↗]` drill + quick-resolve buttons + freeform; ambiguity/gap = question + rationale + chips + answer field; answers call clarification-answer endpoint (optimistic) |
| `IntakeSourceRail` | new | documents w/ status icons (`✓/◐/⚠`); wiki concept index (click → center Wiki view); concept `⚠` when it has open clarifications |
| `UnderstandingMeter` | new | header pill; value = blend(mean `field_confidence.completeness`, clarification resolution rate); spring count-up; threshold pulse on Validate |
| `ProjectWiki` | reuse `BrainWiki` parameterized | accepts an API adapter (`getWiki/getWikiConcept/getWikiSummary/rebuild/health/getSection`) so the same component serves `/projects/{id}/wiki`; reuse `GroundedIn` + section viewer + health strip |
| `IntakeTraceChip` | thin wrap of `FrsTraceChip` | token `S/C/F/Q` → `{kind,label}`; click → drill (source section viewer / concept / clarification) |
| `ProvenancePanel` | new | slide-over; given a token, renders the backward chain (artifact→clarification→concept→source) using `/provenance` |
| `LineageMap` | new (pattern of `FrsCoverageGalaxy`) | SVG column-graph **Sources → Concepts → Clarifications → Artifacts**; hover highlights a path; modes Provenance (backward) / Impact (forward) |
| seal | reuse `BrdConfettiBurst` | + "Understanding Sealed" summary card with counts + "See how it flows downstream →" → opens `LineageMap` |

### B3 — API client + types (`lib/api.ts`, `lib/types.ts`)
Add `api.projects.wiki*` (mirror `api.apps.getWiki/...`), `getProjectSection(id,docId,nodeId)`, `answerClarification(id,gqId,answer)`, `provenance(id,token,dir)`, `clarifications(id)`. Add types: `ProjectWikiConcept/Summary` (reuse `WikiTreeNodeRef`/`WikiHealth`), `Clarification` (`{id,question,kind,category,severity,rationale,citations,resolved,resolution_text}`), `ProvenanceNode`/`LineageEdge`, `CitationToken`.

### B4 — Interaction / motion / a11y / responsive
Skeleton shimmer first paint; optimistic answer submit then revalidate; new-doc banner "N new from <doc>" + one-shot pulse on affected cards (reduced-motion: static highlight); spring meter; confetti on seal — all via `useReducedMotion`. Keyboard: `j/k` move questions, `Enter` opens answer, `v` Validate, `Esc` closes panels. `ThreePanel` already collapses to mobile tabs (Sources/Understanding/Clarifications). Contrast verified on accent/amber/slate chips.

---

## C. Phased rollout (each phase independently shippable & tested)
- **P1 Project Wiki core** — `compile_core.py`+`tree_text.py`, `project_wiki.py` models, `0020`, 3 Celery tasks, ingest trigger, mock branch. ✅ ingest doc (mock) → `ProjectWikiConcept` rows.
- **P2 Project Wiki UI** — wiki + section API; `ProjectWiki` via parameterized `BrainWiki`; project-workspace tab.
- **P3 Clarification Engine + grounding (G8)** — `grounding.py`, RU `app_brain`/`brief` inputs, `CorpusClarifier*`+fixture, `clarifier.py`, `0021`, interview + new-doc triggers. ✅ cited `source="clarifier"` rows; RU grounded on app wiki.
- **P4 Intake Context Pack** — `intake_layer.py` + bundle/projection wiring + clarification-answer endpoint. ✅ resolved answer + RU understanding + concepts in `combined`.
- **P5 Understanding Studio UX** — `UnderstandingStudio`/Canvas/Stream/ContradictionCard/Meter/SourceRail/seal (frontend-design skill on hero surfaces).
- **P6 Provenance** — tokens + resolver + `/provenance` API + `target_kind` extension + `ProvenancePanel` + `LineageMap` + `IntakeTraceChip`.

P1–P2 pure-additive. P3 additive to `dspy_intake.py`/`gap_questions`. P4+P6 touch shared context/traceability — gate behind `combined`/lineage tests.

## D. DO NOT BREAK
Gate untouched; clarifier rows disjoint from RU's `source="interview"`; `GapQuestion` columns additive (enums already match); App Brain wiki code copied not refactored; bundle/projection changes additive (`combined` only gains a section — verify no test pins exact `combined`); `target_kind` extension additive (guarded enum add if a DB enum exists); new Celery tasks via `_run_async`+`dispatch`; empty/heading-less docs guarded (`doc_type="short"`).

## E. Verification
`make migrate` (0020/0021 idempotent), `make test-be`, `make typecheck`, `make lint` green. Mock-mode E2E gold path: open Studio → canvas + `[S#]` chips + meter; upload `Compliance.pdf` → wiki compiles → "new questions" → `IntakeContradictionCard` (7y vs 90d) with both quotes + `view ↗`; answer → meter rises → Answered; `✦ Wiki` browse + GroundedIn + health; Validate → confetti + "Sealed"; generate Concept Brief → `ProvenancePanel` traces CB element → clarification → concept → `Compliance.pdf §4.2`. Real-mode sanity on one small doc (cites two real sections; no event-loop errors).

## F. Critical files
- new: `backend/app/services/wiki/compile_core.py`, `tree_text.py`; `backend/app/models/project_wiki.py`; `backend/alembic/versions/0020_project_wiki.py`, `0021_clarification_meta.py`; `backend/app/services/understanding/clarifier.py`, `grounding.py`; `backend/app/services/context/intake_layer.py`; `backend/app/services/provenance/lineage.py`; `backend/app/services/llm/fixtures/corpus_clarifier.json`.
- edit: `backend/app/models/__init__.py` (register), `models/project.py` (wiki cols), `models/gap.py` (additive cols), `workers/tasks.py` (project-wiki tasks + ingest trigger), `services/skills/dspy_intake.py` (`CorpusClarifier*` + RU `app_brain`/`brief` inputs), `services/understanding/orchestrator.py` (grounding + clarifier trigger), `services/context/project_context.py` + `projection.py` (intake layer), BRD/FRS traceability `target_kind` + `FrsTraceChip` styles, `app/api/` (wiki, section, clarification-answer, provenance routes), `app/api/understanding.py`.
- frontend: `components/InterviewPanel.tsx`→`UnderstandingStudio`; new `UnderstandingCanvas/RuFieldCard`, `ClarificationStream/ClarificationCard/IntakeContradictionCard`, `IntakeSourceRail`, `UnderstandingMeter`, `ProvenancePanel`, `LineageMap`, `IntakeTraceChip`, `ProjectWiki` (param `BrainWiki`); `lib/api.ts`, `lib/types.ts`, `lib/hooks/useUnderstanding.ts` (+ `useClarifications`, `useProjectWiki`).

## G. Out of scope (v1)
Clarifications gating generation (warn-only later); shared App/Project compile-core refactor (after copy ships); project-doc embeddings; auto-resolving contradictions; per-unit clarification filtering via `_UNIT_CB_ELEMENTS`.
