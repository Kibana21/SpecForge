# PRD — E2 Intelligent Intake: Understanding Studio, Project Wiki, Clarification Engine & Provenance

> Companion implementation planning lives in `.claude/plans/`. This PRD says
> **WHAT** to build and **WHY**; phased rollout and file map are included for
> execution. Naming follows the project convention `prd-<E#>-<slug>.md`.

---

## 1. Context — why this is being built

After a user uploads documents and writes a brief, SpecForge runs **Requirement
Understanding (RU)** — the human-validated gate (`Project.ru_validated`) that
must pass before any spec (Concept Brief → BRD → FRS) is generated.

Today RU is **stateless re-synthesis** (`backend/app/services/understanding/orchestrator.py`):
each turn it retrieves a few doc sections via PageIndex `tree_search` (probe =
project name + description), loads in-scope app facts, replays the transcript,
and runs one DSPy call (`RequirementUnderstandingSignature`,
`backend/app/services/skills/dspy_intake.py`) that fills a fixed RU schema and
emits `open_questions`.

**The problem:** those questions are *schema-completion* prompts — the signature
literally says "generate open_questions ONLY for fields you genuinely cannot
infer." It is a fill-in-the-blanks system. It does **not** detect
**contradictions** (doc A vs doc B vs brief vs app fact), **ambiguous /
under-specified concepts**, or cross-document **gaps**; it does not react to a
**new document**; and the understanding it builds is **siloed** —
`RequirementUnderstanding.content_json` never reaches CB/BRD/FRS generation
context (verified: only quality/triage/embedding read it). A `GapDetector` DSPy
skill was even scaffolded and never wired in.

**Intended outcome.** Intake should genuinely *understand* the corpus, ask
brilliant source-citing questions about contradictions/ambiguities/gaps
(triggered in the interview **and** whenever a document is added), and — once
validated — pour that understanding into every downstream stage as first-class,
**fully traceable** context. The experience should make the user *feel* the
system "gets" their project.

**Approved decisions:** (1) build a **Project Wiki** as the grounded foundation;
(2) **upgrade the existing RU interview** surface (no separate panel);
(3) the Project Wiki is **user-visible / navigable**. **Plus the user's
emphases:** an *amazing, intuitive UI/UX*; the system must *understand the
project deeply and amplify downstream context*; **traceability is a first-class
requirement**.

---

## 2. Goals & non-goals

**Goals**
- G1 — **Project Wiki**: emergent, source-grounded concepts compiled from the project's own `DocumentTree`s, with contradiction/orphan health, navigable in the UI.
- G2 — **Clarification Engine**: high-signal **contradiction / ambiguity / gap** questions, each citing conflicting or missing sources.
- G3 — Questions regenerate when a **new document** is ingested.
- G4 — **Intake Context Pack**: the validated RU + resolved clarifications + wiki concepts flow into the shared generation context for CB/BRD/FRS.
- G5 — **Understanding Studio**: an intuitive, beautiful intake workspace built on the existing RU surface.
- G6 — **Provenance spine**: one citation model threads source section → concept → clarification → answer → downstream artifact, navigable backward (provenance) and forward (impact).
- G7 — Mock-first; CI green with zero Vertex/PageIndex calls.
- G8 — **Full-context grounding**: RU synthesis *and* the clarifier reason over the COMPLETE intake corpus — the brief, **all** uploaded documents, and the **associated App Brain (wiki concepts + facts)** of in-scope apps — so questions are maximally pertinent.

**Non-goals (v1)**
- Not changing the gate contract (`ru_validated` still gates; clarifications do not block — future may *warn* on unresolved blockers).
- No vector embeddings for project docs (reasoning stays on PageIndex trees).
- No auto-resolution of contradictions — the engine asks; the human decides.
- No in-place refactor of the App Brain (E1) wiki code (copy-then-parameterize to protect E1).

---

## 3. Experience principles (the UX north stars)

1. **Understanding over interrogation.** The hero is a *living understanding of the project*, not a question queue. Questions are how the understanding improves.
2. **Show, don't just ask.** A contradiction is shown as two real source quotes side-by-side — the most "intelligent" thing the product does.
3. **Provenance is the product.** Every claim, concept, question, and answer carries clickable source chips that drill to the exact document section. Nothing is unsourced.
4. **Felt progress.** An "Understanding meter" rises as questions resolve and confidence climbs — the emotional core of intake.
5. **Calm density.** Reuse the builder design language (left rail + center canvas + right stream, layer-accent colors, collapsible cards, trace chips, confetti on seal). Motion gated by `useReducedMotion()`.
6. **Continuity with downstream.** Validation visibly "seals" the understanding and states that it now powers every spec — closing the loop the user cares about.

---

## 4. Solution overview — three pillars on the existing RU spine

```
Upload docs ─▶ ingest_project_source (PageIndex tree)
                    │
                    ├─▶ [P1] compile_project_wiki_for_doc ── ProjectWikiConcept (grounded concepts + WikiLint contradictions)
                    │                                              │
RU interview turn ──┤                                             │
                    ▼                                              ▼
            [P2] Clarification Engine (WikiLint + CorpusClarifier) → GapQuestion(source="clarifier", citations)
                    │
                    ▼
      ┌─────────────  UNDERSTANDING STUDIO (upgraded RU surface)  ─────────────┐
      │  Canvas (structured RU + confidence + citations) · Clarification Stream │
      │  · Project Wiki tab · Provenance panel · Understanding meter            │
      └────────────────────────────────────────────────────────────────────────┘
                    │ user answers + Validate ("seal")
                    ▼
            [P3] Intake Context Pack  (RU understanding + resolved clarifications + wiki concepts, all carrying citation tokens)
                    │ gather_project_context()
                    ▼
        CB / BRD / FRS generation  →  rows record traceability back to intake (source_section | project_concept | intake_clarification)
```

- **P1 Project Wiki** — grounded substrate + navigable knowledge view.
- **P2 Clarification Engine** — intelligent questions over the wiki + brief + facts + Q&A.
- **P3 Intake Context Pack + Provenance** — understanding flows downstream, fully traced.

---

## 5. UX design — the Understanding Studio

Upgrade `frontend/app/projects/[id]/interview/` into a three-zone workspace that matches the FRS builder vocabulary. `useUnderstanding` is extended (not replaced).

### 5.1 Layout

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ ← Back   Requirement Understanding    ◍ 72% understood    [ ✦ Wiki ] [ Provenance ] [ ✓ Validate ] │
├───────────────┬───────────────────────────────────────────────────────┬────────────────┤
│ SOURCES        │  UNDERSTANDING CANVAS                                  │ CLARIFICATIONS │
│ • Brief        │  ┌── Objective ───────────────── ●●●●○ 80% ─────────┐ │ ⚠ 2  ❓ 3  ◌ 1 │
│ • Claims.pdf ✓ │  │ Automate claims intake & triage…   [S2][S5]      │ │ ─────────────  │
│ • Comp.pdf ⚠   │  └────────────────────────────────────────────────┘ │ ⚠ Data retention│
│ • TechSpec ✓   │  ┌── Stakeholders & Roles ─────── ●●●○○ 60% ────────┐ │   blocker  [▸]  │
│                │  │ Claims adjuster, Compliance off… [S1]            │ │ ❓ "SLA" undefined│
│ WIKI CONCEPTS  │  └────────────────────────────────────────────────┘ │ ◌ No error-path  │
│ ▸ Claims Intake│  ┌── Systems & Integrations ───── ●●○○○ 40% ⚠1 ─────┐ │   spec for …     │
│ ▸ Retention ⚠  │  │ Guidewire, Doc store…            [S3][F1]        │ │                  │
│ ▸ Triage Rules │  └────────────────────────────────────────────────┘ │ [All|⚠|❓|◌|✓]   │
└───────────────┴───────────────────────────────────────────────────────┴────────────────┘
```

- **Left rail — Sources & Wiki**: project documents with ingest/wiki status (`✓` ready, `◐` indexing, `⚠` has unresolved contradiction); below, the wiki concept index (click → opens concept page in center). Concepts with open clarifications show `⚠`.
- **Center — Understanding Canvas**: the RU rendered as structured cards (Objective, Stakeholders & Roles, Target Process, Functional Areas, Systems & Integrations, Risks, Scope, Assumptions). Each card shows a **confidence/completeness bar** (from existing `field_confidence`), **source trace chips** (`[S#]`/`[F#]` → drill-down slide-over), and an **amber edge + count** if it has open clarifications. A header toggle swaps the canvas for the **Wiki view** (reused `BrainWiki.tsx`).
- **Right — Clarification Stream**: prioritized smart questions (severity → kind), filterable (`All / Contradictions / Ambiguities / Gaps / Answered`). A "N new from <doc>" banner appears after a document is ingested.

### 5.2 The Understanding meter
Top-of-header `◍ 72% understood` = blend of mean `field_confidence.completeness` across RU fields and clarification resolution rate. Rises as questions are answered (animated). Validate is *encouraged* once it clears a threshold and **no blocker-severity contradictions remain** (encouraged, not enforced — gate contract unchanged).

### 5.3 Contradiction card (hero component) — `IntakeContradictionCard`
```
┌─ ⚠ Contradiction · Data retention · blocker ───────────────────────────┐
│ Two sources disagree on how long claim records are kept.               │
│                                                                        │
│  📄 Compliance_Policy.pdf › §4.2 Retention                [view ↗]    │
│     "Claim records must be retained for 7 years."                      │
│                       ⟂                                                │
│  📄 Tech_Spec.docx › §3 Storage                            [view ↗]    │
│     "Purge claim data after 90 days."                                  │
│                                                                        │
│  ▸ Why it matters: drives the data model + a compliance NFR in the BRD.│
│                                                                        │
│  [ 7 years ✓ ]  [ 90 days ✓ ]  [ Both apply ▾ ]                        │
│  └ or type a precise resolution……………………………………………  [ Save ]            │
└────────────────────────────────────────────────────────────────────────┘
```
`view ↗` opens the cited PageIndex section in a slide-over (reuse the wiki "Grounded in" section viewer). Ambiguity (amber) and Gap (slate) cards are simpler: question + rationale + source chips + answer field.

### 5.4 New-document awareness
On ingest+wiki-compile of a new doc: a toast + a stream banner "**3 new questions from Compliance.pdf**", and the affected canvas cards / wiki concepts pulse once (reduced-motion: static highlight).

### 5.5 The "seal" moment (validation)
On Validate: `BrdConfettiBurst`, then an **Understanding Sealed** summary:
> SpecForge now understands **PayHub Claims**: **14 concepts mapped · 9 clarifications resolved · 23 source sections cited.** This understanding now powers your Concept Brief, BRD, and FRS. **[ See how it flows downstream → ]** (opens Provenance).

### 5.6 Project Wiki view
Reuse `frontend/app/components/BrainWiki.tsx` parameterized to `/projects/{id}/wiki`: concept index, concept pages with "Grounded in" `tree_node_refs` drill-down, and a health strip (contradictions/orphans). Available as the `✦ Wiki` toggle in the Studio and as a tab in the project workspace.

### 5.7 Frontend components (new/reused)
| Component | Status | Purpose |
|---|---|---|
| `UnderstandingStudio` (rework of interview page) | extend | 3-zone shell + meter + Validate/seal |
| `UnderstandingCanvas` + `RuFieldCard` | new | structured RU cards w/ confidence + trace chips |
| `ClarificationStream` + `ClarificationCard` + `IntakeContradictionCard` | new | typed, prioritized smart questions |
| `IntakeSourceRail` | new | sources + wiki concept index |
| `ProjectWiki` (param of `BrainWiki.tsx`) | reuse | navigable wiki |
| `ProvenancePanel` + `LineageMap` | new | provenance/impact (see §7) |
| `IntakeTraceChip` (param of `FrsTraceChip`) | reuse | `[S#]/[C#]/[F#]/[Q#]` chips, drill-down |
| `BrdConfettiBurst`, wiki section viewer, `useReducedMotion` | reuse | seal moment, drill-down, motion |

---

## 6. Backend design (reuse-first)

### 6.0 Full-context grounding (G8) — feed RU + clarifier the whole corpus
Today `understanding/orchestrator.generate()` grounds RU on only: a single
`tree_search` over docs (probe = name+description) + app **facts** + Q&A. It
**omits the App Brain wiki concepts** and uses thin brief grounding. Both the RU
synthesis and the new clarifier must reason over the **complete intake context**:

1. **Brief** — the project brief/description AND (if present) the latest
   `CbDiscoverEnhancedBrief` for the project. Pass as an explicit `brief` input.
2. **All uploaded documents** — not just top-K of one probe. Provide corpus
   **breadth** (per-doc PageIndex outlines, like `docs_layer.outline_text`) plus
   **targeted depth** (`tree_search`/`depth_search`) so no document is invisible
   to questioning. Reuse `backend/app/services/context/docs_layer.py` helpers.
3. **Associated App Brain — wiki + facts** — include in-scope apps' **wiki
   concepts** (reuse `backend/app/services/rag/wiki_grounding.py::gather_app_brain_context`,
   which already loads `AppWikiConcept` for a project's in-scope apps), in
   addition to the existing `AppFact`s.

**Implementation (additive):** add an `app_brain` InputField to
`RequirementUnderstandingSignature` (wiki concepts + facts, formatted) and a
`brief` InputField; `generate()` populates them via the helpers above. Mirror the
same inputs into `CorpusClarifierSignature` (it already takes `app_facts`,
`brief_context`, `wiki_concepts`; extend `app_facts`→`app_brain` to carry app
wiki concepts too). This is purely additive — new signature inputs default
safely and the mock fixtures are unchanged, so existing RU tests keep passing.
A shared helper `build_intake_grounding(project_id, db) -> {brief, doc_breadth,
doc_depth, app_brain, qa}` centralizes assembly so RU, the clarifier, and the
new-document trigger all ground identically.

### 6.1 Pillar 1 — Project Wiki
**Reuse unchanged**: all DSPy modules in `backend/app/services/skills/wiki_compiler/dspy_wiki.py` (`run_doc_summary`, `run_concept_plan`, `run_concept_page`, `run_wiki_lint`) and tree utils in `backend/app/services/corpus_index/base.py`.

**New compile core** `backend/app/services/wiki/compile_core.py`:
`compile_doc_into_wiki(db, *, scope_id, scope_name, doc_id, doc_name, tree_json, page_texts, source_text, ConceptModel, SummaryModel, scope_col, settings) -> int` — a **copy** of `workers/tasks.py::_compile_one_doc`, parameterized over scope/models (copy, **not** in-place refactor, to protect E1). Project source: text from `Document.extracted_text`, tree from `DocumentTree`; `doc_type="pageindex"` if `node_count>0` else `"short"`; port the mock branch verbatim.

**New models** `backend/app/models/project_wiki.py` (mirror `wiki.py`): `ProjectWikiSummary` (`project_id`,`document_id`,`brief`,`content_md`,`related_slugs`,`doc_type`,`compiled_at`; unique `(project_id,document_id)`), `ProjectWikiConcept` (`project_id`,`slug`,`title`,`brief`,`content_md`,`source_doc_ids`,`related_slugs`,`tree_node_refs`,`compiled_at`; unique `(project_id,slug)`). Register in `backend/app/models/__init__.py`. Add `Project.wiki_status/wiki_compiled_at/wiki_health`.

**Migration** `0014_project_wiki.py` (copy `0012`/`0013` `op.execute` idempotent style; FKs CASCADE).

**Celery tasks** (`backend/workers/tasks.py`, via `_run_async`): `compile_project_wiki_for_doc`, `rebuild_project_wiki`, `check_project_wiki_health` — mirror the app-wiki tasks; deterministic doc order by `Document.created_at`.

**API** (mirror app-wiki routes): `GET /projects/{id}/wiki`, `/wiki/concepts/{slug}`, `/wiki/summaries/{doc_id}`, `POST /wiki/rebuild`, `POST /wiki/health`.

### 6.2 Pillar 2 — Clarification Engine
**New DSPy** in `dspy_intake.py` (additive): `CorpusClarifierSignature` →
```python
class ClarificationItem(BaseModel):
    question: str; kind: Literal["contradiction","ambiguity","gap"]
    category: Literal["scope","data","security","integration","ux"]
    severity: Literal["blocker","major","minor"]
    rationale: str = ""
    citations: list[str] = []   # canonical tokens: "S:<doc>:<node>", "C:<slug>", "F:<fact>"
```
Inputs: `project_name, wiki_concepts, detected_contradictions, brief_context, app_facts, qa_pairs`. Docstring: emit only genuine contradiction/ambiguity/gap items, each citing conflicting/missing sources, never re-asking answered Q&A. Add `CorpusClarifierModule`, `run_corpus_clarifier(...)` with `if _is_mock(): return mock_fixture("corpus_clarifier")` + fixture `backend/app/services/llm/fixtures/corpus_clarifier.json`.

**New orchestrator** `backend/app/services/understanding/clarifier.py`:
`run_clarification(project_id, db, *, trigger) ` → load `ProjectWikiConcept`s → if ≥2, `run_wiki_lint` (validate slugs like `_check_wiki_health`) → format → `run_corpus_clarifier` → persist.

**Persistence — reuse `GapQuestion`, `source="clarifier"`** (disjoint from RU's `source="interview"`). Idempotent replace of unresolved `source="clarifier"` rows; resolved rows preserved. **Additive migration** `0015_clarification_meta.py`: nullable `kind VARCHAR(20)`, `citations JSONB DEFAULT '[]'`, `rationale TEXT` on `gap_questions`.

### 6.3 Pillar 3 — Intake Context Pack (downstream amplification)
This is the "feeds downstream" requirement, expanded beyond just answers.

**New layer** `backend/app/services/context/intake_layer.py`:
```
@dataclass
class IntakeLayer:
    understanding: dict          # validated RU.content_json (objective, process, systems, integrations, roles, risks, scope)
    resolved_clarifications: list[dict]   # {question, answer, kind, citations}
    wiki_concepts: list[dict]    # {slug, title, brief, citations}
    formatted_context: str       # "=== Project Understanding (Intake) ===" block, citation-tagged
    citation_index: dict         # token -> {kind, label, doc_id?, node_id?, excerpt?}  (for traceability)
async def build_intake_layer(project_id, db) -> IntakeLayer
```
Pulls `RequirementUnderstanding.content_json` (today unused downstream!), `GapQuestion(source="clarifier", resolved=True)`, and `ProjectWikiConcept` briefs. Formats Q→A + understanding + concept briefs with their citation tokens inline.

**Plumb** into `backend/app/services/context/project_context.py`: add `intake: IntakeLayer` to `ProjectContextBundle`; build sequentially (single-session rule). In `backend/app/services/context/projection.py::project_for_unit`, append `bundle.intake.formatted_context` to `combined` — the single chokepoint all of CB/BRD/FRS share. (No per-unit map change needed for v1; optionally add to `_UNIT_CB_ELEMENTS` later.)

**Answer capture**: `POST /projects/{id}/understanding/clarifications/{gq_id}/answer` (additive, in `understanding.py`) sets `resolution_text/resolved/resolved_at`.

---

## 7. Traceability / Provenance — the spine

### 7.1 Canonical citation tokens
One vocabulary threads everything (RU already emits `[S#]/[F#]` with a citations list; we canonicalize):
- `S:<document_id>:<node_id>` — a source document section (PageIndex node).
- `C:<concept_slug>` — a project wiki concept.
- `F:<app_fact_id>` — an in-scope app fact.
- `Q:<gap_question_id>` — a clarification Q&A.

`ProjectWikiConcept.tree_node_refs` are `S:` tokens; clarification `citations` carry `S:/C:/F:` tokens; the Intake Layer's `citation_index` resolves any token to a human label + drill-down target.

### 7.2 The lineage chain
```
Source section (S) ─grounds→ Wiki concept (C) ─cited by→ Clarification (Q) ─answered→ Intake Context Pack
                                                                                          │ consumed by
                                                                                          ▼
                                                        CB row / BRD requirement / FRS spec
                                                          └─ traceability row (target_kind ∈ {source_section, project_concept, intake_clarification})
```
**Downstream wiring (reuse existing traceability):** extend the BRD/FRS traceability `target_kind` palettes (and `FrsTraceChip`/`BrdTraceChip` styles) with `source_section`, `project_concept`, `intake_clarification`. Because the Intake Context Pack injects citation tokens alongside each fact, generators can emit traceability rows pointing back to intake — so an FRS spec or BRD requirement is traceable all the way to a PageIndex section.

### 7.3 Provenance UI
- **`IntakeTraceChip`** (param of `FrsTraceChip`): renders `S/C/F/Q` chips everywhere (canvas cards, clarifications, wiki, downstream rows); click → drill to the exact source section (reuse wiki section viewer) or the concept/clarification.
- **`ProvenancePanel`** (backward): from any element (RU field, clarification, BRD requirement, FRS spec) → "Where did this come from?" walks the chain to source sections.
- **`LineageMap`** (project-level, column-graph like `FrsCoverageGalaxy`): **Sources → Concepts → Clarifications → Artifacts**, hover a node to highlight its full path. Two modes:
  - **Provenance (backward)**: select an artifact element → highlight the concepts, clarifications, and sources behind it.
  - **Impact (forward)**: select a source document → highlight every concept it grounds, every clarification citing it, and every downstream element that traces back. ("If I change this doc, what breaks?")
- **API**: `GET /projects/{id}/provenance?node=<token>&direction=backward|forward` returns the scoped lineage (resolved from `tree_node_refs`, clarification `citations`, and existing traceability tables). Read-only.

---

## 8. Triggers
- **Interview turn**: end of `understanding/orchestrator.generate` (post-`_persist` commit) → run the clarifier **inline** (1–2 LLM calls; wiki precompiled). Empty wiki → degrade to brief+facts+Q&A.
- **New document**: success tail of `_ingest_project_source` → `dispatch(compile_project_wiki_for_doc, ...)`; chain `run_project_clarification` at the end of the compile task so the wiki is fresh first. New `source="clarifier"` rows surface on next GET/poll. Use `dispatch(...)` (TCP pre-flight), not `.delay`.

---

## 9. Mock-first
- `run_corpus_clarifier` → `corpus_clarifier.json` fixture.
- `compile_core` mock branch ported from `_compile_one_doc` (deterministic, no network).
- `run_wiki_lint` already mock-returns `{"contradictions": []}` → clarifier sees "(none)".
- Tests (real PG+Redis, mock LLM) assert: wiki rows populate; clarifier writes `source="clarifier"` rows with citation tokens; resolved answers + RU understanding + concepts appear in the gathered bundle's `combined`; provenance API resolves a known token chain.

---

## 10. DO NOT BREAK — risk analysis
1. **Gate** — untouched; clarifications never gate; `require_ru_validated`/`understanding/validate` unchanged.
2. **Existing RU flow** — orchestrator keeps writing/replacing `source="interview"` rows; clarifier only touches `source="clarifier"` (disjoint replace queries). Schema-completion `open_questions` preserved (shown lower-priority in the Studio).
3. **`GapQuestion`** — additive nullable columns; enums already match clarifier literals.
4. **App Brain wiki (E1)** — **copy, don't refactor**; `_compile_one_doc`/`rebuild_app_wiki`/`check_wiki_health` + tests byte-for-byte unchanged.
5. **Context bundle** — additive field + layer; callers use the factory; `combined` gains a section (strictly more grounding). Verify no test asserts an exact `combined` string.
6. **Traceability `target_kind`** — extending the palette is additive; existing kinds unaffected (verify validators/enums tolerate new values; if a DB enum exists, add values via guarded migration).
7. **Celery loop-safety** — new tasks via `_run_async`, dispatched via `dispatch(...)`.
8. **Empty/heading-less docs** — `compile_core` guards `doc_type="short"`; clarifier degrades without a wiki.
9. **RU content downstream** — newly consumed by the Intake Layer; additive (no generator previously depended on its absence).
10. **New RU signature inputs (G8)** — adding `app_brain`/`brief` InputFields to `RequirementUnderstandingSignature` is additive; the mock path returns the fixed `requirement_understanding.json` fixture regardless of inputs, so existing RU tests are unaffected. `gather_app_brain_context` is reused as-is (already used by spec generation), no new app-side code.

---

## 11. Phased rollout
- **P1 — Project Wiki (additive, isolated):** models, `0014`, `compile_core.py`, compile/rebuild tasks, ingest trigger, mock branch. Test: ingest a doc (mock) → `ProjectWikiConcept` rows.
- **P2 — Project Wiki UI:** wiki routes + `ProjectWiki` (reuse `BrainWiki.tsx`).
- **P3 — Clarification Engine + full-context grounding (G8):** `build_intake_grounding` helper (brief + doc breadth/depth + App Brain wiki+facts); add `app_brain`/`brief` inputs to `RequirementUnderstandingSignature` and feed the clarifier the same; `CorpusClarifier` signature/module/runner/fixture; `clarifier.py`; `0015` additive migration; triggers. Test: `source="clarifier"` rows w/ citations; RU grounding includes app wiki concepts.
- **P4 — Intake Context Pack (requirement-critical):** `intake_layer.py`; wire into `ProjectContextBundle` + `gather_project_context` + `projection`; answer endpoint. Test: resolve clarification → bundle `combined` contains RU understanding + answer + concepts.
- **P5 — Understanding Studio UX:** rebuild the interview page (canvas + stream + meter + seal), `IntakeContradictionCard`, source rail, wiki toggle.
- **P6 — Provenance:** citation-token canonicalization, `target_kind` extensions, `ProvenancePanel` + `LineageMap`, `/provenance` API.

P1–P2 pure-additive. P3 additive to `dspy_intake.py` + `gap_questions`. P4 + P6 touch shared context/traceability — gate behind `combined`/lineage tests.

---

## 12. Verification (end-to-end)
- `make migrate` applies `0014`/`0015` (+ any guarded enum add) cleanly; `make test-be`, `make typecheck`, `make lint` green.
- New tests: project-wiki compile (mock); clarifier emits cited `source="clarifier"` rows and never deletes `source="interview"`; gate still 409s when `ru_validated` false; **Intake Context Pack** — resolve a clarification, gather bundle, assert RU understanding + answer + concept briefs present in `combined`; **provenance** — `/provenance` resolves a source→concept→clarification→artifact chain both directions.
- Mock-mode E2E walkthrough (the gold path):
  1. Open Understanding Studio for the seeded project → canvas shows structured RU with confidence + `[S#]` chips; meter at N%.
  2. Upload `Compliance.pdf` → wiki compiles → toast "new questions"; an `IntakeContradictionCard` (retention 7y vs 90d) appears with both source quotes; `view ↗` drills to the section.
  3. Answer it → meter rises; card moves to "Answered".
  4. `✦ Wiki` → browse concepts + "Grounded in" citations + health strip.
  5. Validate → confetti + "Understanding Sealed" summary.
  6. Generate Concept Brief → open `ProvenancePanel` on a CB element → trace back to the clarification → concept → `Compliance.pdf §4.2`.
- Real-mode sanity (`LLM_PROVIDER=gemini`, one small doc): contradiction cites two real sections; no event-loop binding errors across wiki tasks.

---

## 13. Critical files
| Path | Change |
|---|---|
| `backend/app/models/project_wiki.py` | **new** models |
| `backend/app/models/__init__.py` | register models |
| `backend/app/models/project.py` | `wiki_status/compiled_at/health` |
| `backend/app/models/gap.py` | additive `kind/citations/rationale` |
| `backend/alembic/versions/0014_project_wiki.py`, `0015_clarification_meta.py` | **new** migrations |
| `backend/app/services/wiki/compile_core.py` | **new** model-agnostic compile (copied) |
| `backend/app/services/skills/dspy_intake.py` | add `CorpusClarifier*`; add `app_brain`/`brief` inputs to `RequirementUnderstandingSignature` |
| `backend/app/services/llm/fixtures/corpus_clarifier.json` | **new** fixture |
| `backend/app/services/understanding/clarifier.py` | **new** orchestrator |
| `backend/app/services/understanding/orchestrator.py` | trigger clarifier post-`generate`; ground RU on brief + all docs + App Brain wiki+facts via `build_intake_grounding` (RU semantics intact) |
| `backend/app/services/rag/wiki_grounding.py::gather_app_brain_context` | **reuse** — pull in-scope App Brain wiki concepts into RU/clarifier grounding |
| `backend/app/services/context/intake_layer.py` | **new** Intake Context Pack |
| `backend/app/services/context/project_context.py`, `projection.py` | wire intake layer into `combined` |
| `backend/app/services/artifacts/.../traceability` + `FrsTraceChip`/BRD trace | extend `target_kind`: source_section/project_concept/intake_clarification |
| `backend/workers/tasks.py` | project-wiki tasks + ingest trigger chain |
| `backend/app/api/` (wiki, provenance routes) + `understanding.py` (clarification answer) | **new**/additive endpoints |
| `frontend/app/projects/[id]/interview/` (→ `UnderstandingStudio`) + `useUnderstanding` | Studio rework |
| `frontend/app/components/` | `UnderstandingCanvas`, `ClarificationStream`, `IntakeContradictionCard`, `IntakeSourceRail`, `ProvenancePanel`, `LineageMap`, `ProjectWiki` (param of `BrainWiki.tsx`), `IntakeTraceChip` (param of `FrsTraceChip`) |

---

## 14. Out of scope / future
- Clarifications gating generation (warn on unresolved blockers) — deliberate v1 non-goal.
- Factoring App Brain `_compile_one_doc` + project variant onto one shared core (after copy-first ships).
- Vector embeddings for project docs; auto-resolution of contradictions; per-unit clarification filtering via `_UNIT_CB_ELEMENTS`; live collaborative intake.
