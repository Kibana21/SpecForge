# E4b — BRD Builder module (detailed implementation plan)

> Second module of **E4 SDLC Artifacts** (see `E4-sdlc-artifacts.md` for the umbrella + shared decisions
> and `E4a-concept-brief.md` for the foundation this module sits on).
> Source of truth for structure: `reference_mds/skills/brd-builder/{brd-template.md, SKILL.md}`.
>
> **E4a built the shared foundation we reuse here verbatim:** `artifact_documents` / `artifact_messages` /
> `artifact_sources` containers + `VersionedRowMixin`, the generic orchestrator (`upsert_rows`,
> `generate_unit`, `generate_all`, `edit_row`, `regenerate_unit`, `restore_row`, `validate`), the generic
> artifact API router under `/api/projects/{id}/artifacts/{type}`, `gather_impacted_apps_context`, the
> impacted-apps create/edit flow, source-material wiring (`document_ids` filter into
> `_retrieve_project_sections`), the `require_artifact_validated` gate factory, the workspace SDLC pipeline
> card, and the builder shell (`ArtifactBuilderPanel`). E5 (Concept Brief Discover) established the
> Discover pattern — we reuse its module surface (DSPy enhancer + analyser, `in_discover` status,
> `DiscoverPhase`/`DiscoverQADrawer` components) and instantiate a **BRD-specific catalog**.
>
> **Net-new in E4b:** ~21 typed `brd_*` row tables, the BRD manifest (~24 generation units), one DSPy
> Signature/Module per unit, the BRD discover catalog (~18 questions), the **BRD validation checklist**
> (much stricter than CB), and the gate that unlocks FRS (`require_artifact_validated("brd")`).
>
> **Net-new cross-module infrastructure (built here, reused by every future artifact module):**
> 1. A standalone **Project Context Bundle** subsystem (`services/context/`) that composes the three
>    grounding layers — **App Brain · Project Documents (PageIndex) · Project Brief (Concept Brief)** —
>    into one typed object with per-unit projection. Replaces the inline `gather_cb_context_for_brd`
>    helper sketched in earlier drafts.
> 2. A **full-coverage contract** that statically guarantees every populated Concept Brief sub-artifact
>    is consumed by at least one BRD unit, enforced at validate time.
> 3. A typed **`brd_traceability` table** capturing, for each BRD row that has one, the explicit links
>    back to its source(s) — CB rows, app-brain facts, project document sections, or discover Q&A.
>    Shape designed to graduate to `artifact_traceability` when FRS lands.

## 1. Goal & scope

Let a business analyst (or platform admin / project owner) produce a **Business Requirements Document
(BRD)** inside SpecForge, attached to an existing `Project` whose **Concept Brief is validated**, via a
guided Discover → generate → Q&A refine → validate loop. DSPy generates each sub-artifact; every row sits
in its own typed table and is individually versioned; a stricter **validation gate** marks the BRD ready
and unlocks the FRS (E4c, future).

**In scope (this file):** BRD end-to-end — `brd_*` data model + migration, manifest + ~24 DSPy units,
BRD discover catalog + analysis, orchestration wiring (reusing the generic services), validate checklist
+ gate, API verbs, markdown export, frontend builder route + workspace gating, mock-first tests.

**Out of scope:** FRS (E4c later), changes to E4a/Concept Brief behaviour, any changes to the legacy E3
spec pipeline's deprecated `brd` `SpecType` (kept until E4c lands; flagged for removal in §14).

## 2. The BRD structure (from the template) → units & tables

The template = YAML frontmatter + Document Control table + 14 numbered sections. Each section decomposes
into one or more generation units. Frontmatter + Document Control are **export-time, not LLM units** —
sourced from `Project` + `VersionSnapshot` history (mirrors E4a §9).

| § | Section (template) | Generation unit(s) | Table(s) written |
|---|--------------------|--------------------|--------------------|
| 1 | Business Context & Background (overview, strategic alignment, drivers) | `business_context` | `brd_text_blocks` (`business_overview`, `strategic_alignment`), `brd_drivers` |
| 2 | Problem Statement & Business Drivers (current situation, problem statement, impact) | `problem` | `brd_text_blocks` (`current_situation`, `problem_statement`), `brd_problem_impact` |
| 3.1 | Objectives | `objectives` | `brd_objectives` |
| 3.2 | Expected Benefits | `benefits` | `brd_benefits` |
| 4.1 | Stakeholder Summary | `stakeholders` | `brd_stakeholders` |
| 4.2 | Users / Business Actors | `actors` | `brd_actors` |
| 5 | Scope (in / out / boundaries) | `scope` | `brd_scope_items`, `brd_text_blocks` (`scope_boundaries`) |
| 6.1 | As-Is Process | `asis_process` | `brd_text_blocks` (`asis_summary`), `brd_asis_steps` |
| 6.2 | To-Be Process | `tobe_process` | `brd_text_blocks` (`tobe_summary`), `brd_tobe_steps` |
| 6.3 | Business Rules | `business_rules` | `brd_text_blocks` (`business_rules`) |
| 7 | Business Requirements | `business_requirements` | `brd_business_requirements` |
| 8.1 | Data Needs | `data_needs` | `brd_data_needs` |
| 8.2 | Reporting & Analytics | `reporting` | `brd_reporting` |
| 9.1 | Assumptions | `assumptions` | `brd_assumptions` |
| 9.2 | Dependencies | `dependencies` | `brd_dependencies` |
| 9.3 | Constraints | `constraints` | `brd_constraints` |
| 10.1 | Risks | `risks` | `brd_risks` |
| 10.2 | Known Issues | `issues` | `brd_issues` |
| 11.1 | Implementation Approach (prose) | `implementation_approach` | `brd_text_blocks` (`implementation_approach`) |
| 11.2 | Phasing & Milestones | `phasing` | `brd_phasing` |
| 11.3 | Change Management & Training | `change_management` | `brd_change_mgmt` |
| 12.1 | KPIs | `kpis` | `brd_kpis` |
| 12.2 | Qualitative Success Criteria (prose) | `qualitative_success` | `brd_text_blocks` (`qualitative_success`) |
| 13–14 | Open Questions / Decisions / References / Glossary | `compendium` (single composite unit, AI suggests; user curates) | `brd_open_questions`, `brd_decisions`, `brd_references`, `brd_glossary` |

24 generation units writing into 21 typed row tables + the shared `brd_text_blocks`.

## 3. Data model (concrete typed tables)

Add to `backend/app/models/artifact.py` (the file E4a already created); register every new model in
`backend/app/models/__init__.py`. Each table = `VersionedRowMixin` (already defined in E4a) + the typed
columns below. **No new shared infra here** — `artifact_documents`, `artifact_messages`,
`artifact_sources`, and the mixin are reused exactly as-is. `artifact_type` already accepts `brd` as an
enum value (defined in E4a's migration 0015).

### 3.1 BRD row tables — typed columns + `row_key` policy

| Table | Typed columns | `row_key` |
|-------|---------------|-----------|
| `brd_text_blocks` | `field_key TEXT, text TEXT` | `field_key` (`business_overview`, `strategic_alignment`, `current_situation`, `problem_statement`, `scope_boundaries`, `asis_summary`, `tobe_summary`, `business_rules`, `implementation_approach`, `qualitative_success`) |
| `brd_drivers` | `text TEXT, kind TEXT` (`regulatory|competitive|cost|growth|other`) | ordinal `drv-1…` |
| `brd_problem_impact` | `area TEXT, description TEXT, magnitude TEXT, evidence TEXT` | ordinal `pi-1…` |
| `brd_objectives` | `statement TEXT, category TEXT, priority TEXT, owner TEXT` | natural `OBJ-1, OBJ-2…` (LLM-stable) |
| `brd_benefits` | `benefit TEXT, kind TEXT (financial\|operational\|customer\|strategic\|other), magnitude TEXT, timing TEXT, confidence TEXT` | ordinal `ben-1…` |
| `brd_stakeholders` | `group_name TEXT, role TEXT, responsibilities TEXT, influence TEXT (low\|medium\|high), engagement TEXT` | natural `STK-1…` |
| `brd_actors` | `persona TEXT, description TEXT, goals TEXT, pain_points TEXT, impact_of_change TEXT` | natural `ACT-1…` |
| `brd_scope_items` | `kind TEXT (in_scope\|out_of_scope), text TEXT` | `{kind}-{n}` |
| `brd_asis_steps` | `step_no INT, actor TEXT, description TEXT, inputs TEXT, outputs TEXT, pain_points TEXT` | `asis-{n}` |
| `brd_tobe_steps` | `step_no INT, actor TEXT, description TEXT, inputs TEXT, outputs TEXT, business_benefit TEXT` | `tobe-{n}` |
| `brd_business_requirements` | `title TEXT, description TEXT, objective_ids TEXT[] (FK-style refs to `brd_objectives.row_key`), stakeholder_ids TEXT[] (`brd_stakeholders.row_key`), priority TEXT (must\|should\|could\|wont), acceptance_criteria TEXT` | natural `BR-001, BR-002…` (LLM-stable) |
| `brd_data_needs` | `domain TEXT, description TEXT, source_systems TEXT, consumers TEXT, quality_expectations TEXT` | ordinal `dn-1…` |
| `brd_reporting` | `name TEXT, purpose TEXT, audience TEXT, frequency TEXT, detail_level TEXT` | ordinal `rpt-1…` |
| `brd_assumptions` | `text TEXT, impact_if_false TEXT, owner TEXT` | natural `ASM-1…` |
| `brd_dependencies` | `name TEXT, kind TEXT (system\|team\|vendor\|external\|other), criticality TEXT (low\|medium\|high), owner TEXT, notes TEXT` | natural `DEP-1…` |
| `brd_constraints` | `text TEXT, category TEXT (regulatory\|technical\|budget\|time\|policy\|other), description TEXT, implication TEXT` | natural `CON-1…` |
| `brd_risks` | `description TEXT, cause TEXT, impact TEXT, likelihood TEXT (low\|medium\|high), severity TEXT (low\|medium\|high), mitigation TEXT, owner TEXT, status TEXT (open\|mitigated\|accepted\|closed)` | natural `RSK-1…` |
| `brd_issues` | `description TEXT, impact TEXT, workaround TEXT, owner TEXT, status TEXT` | natural `ISS-1…` |
| `brd_phasing` | `phase TEXT, description TEXT, target_dates TEXT, entry_criteria TEXT, exit_criteria TEXT` | natural `PH-1…` |
| `brd_change_mgmt` | `audience TEXT, change_impact TEXT, training_needs TEXT, channel TEXT, timing TEXT` | ordinal `cm-1…` |
| `brd_kpis` | `name TEXT, baseline TEXT, target TEXT, timeframe TEXT, data_source TEXT, notes TEXT` | natural `KPI-1…` |
| `brd_open_questions` | `text TEXT, owner TEXT, due_date DATE NULL, status TEXT (open\|answered\|deferred)` | natural `Q-1…` |
| `brd_decisions` | `decision TEXT, date DATE NULL, decision_makers TEXT, rationale TEXT, impact TEXT` | natural `DEC-1…` |
| `brd_references` | `kind TEXT, title TEXT, location TEXT, notes TEXT` | natural `REF-1…` |
| `brd_glossary` | `term TEXT, definition TEXT` | `term` slug (lowercased, kebab) |
| `brd_traceability` | `target_table TEXT, target_row_key TEXT, source_kind TEXT (cb_row\|app_fact\|doc_section\|discover_qa), source_ref TEXT (canonical: e.g. `cb_outcomes:o-3`, `app_fact:UUID`, `doc:UUID#node-X` p.start-end, `discover_qa:brd:3b`), relation TEXT (derives_from\|constrained_by\|enabled_by\|informs\|annotates), excerpt TEXT (≤ 240 chars cited snippet), confidence TEXT (high\|medium\|low)` | composite slug `tr-{target_table}-{target_row_key}-{n}` |

**`TEXT[]` columns** (`brd_business_requirements.objective_ids` / `.stakeholder_ids`) use Postgres array
types — these are **soft, within-BRD** references (string row_keys); the orchestrator validates them at
write time against the current `brd_objectives` / `brd_stakeholders` rows. A trace pointing at a
removed/missing key is allowed but surfaces in the validate checklist as a finding.

**`brd_traceability` — what it captures and how it differs from `objective_ids`/`stakeholder_ids`:**
The `*_ids` arrays handle *within-BRD* linkage (BR → its own objectives / stakeholders). The
`brd_traceability` table handles *external* linkage — BR/KPI/objective/risk rows pointing **outward** to
the three grounding layers (CB rows, app facts, document sections, discover answers). Each link is its
own versioned row, written by the orchestrator on (re)generation and validated at the gate (§8.1.G).
Shape generalises to `artifact_traceability` when FRS adds FR → BR / FR → app-fact links.

### 3.2 Migration `backend/alembic/versions/0018_brd_artifact.py`

(Down-revision = the highest E4a/E5 migration — currently `0017_cb_discover_questions`.) Idempotent raw
SQL, same pattern as `0015`: enum guards for the new enum values (e.g. `brd_priority`, `brd_risk_status`,
`brd_question_status`) via `DO $$ … EXCEPTION WHEN duplicate_object`; build the 21 `brd_*` tables from
a small `(name, [content-column DDL])` Python list + the shared mixin columns to stay DRY (mirrors how
E4a's migration built the 8 `cb_*` tables). `brd_business_requirements.objective_ids` / `.stakeholder_ids`
use `TEXT[]`. `downgrade()` drops in reverse.

Also in `0018`: extend the `brd_discover_*` tables (§6 below) **only if** we decide to keep BRD-specific
discover tables; otherwise we generalise `cb_discover_*` → `artifact_discover_*` (see §13, Decision 1).

## 4. Generation units & dependency DAG

Manifest `backend/app/services/artifacts/manifest/brd.py` — ordered list of 24 unit entries. Each entry:
`unit_key, writes(tables/fields), depends_on[], unit_instruction (from template's `[G]` guidance,
condensed), discover_keys (from §6), validate_checks (§8.1)`.

```
business_context      → []
problem               → [business_context]
objectives            → [problem]                            (consumes CB objectives if available — see §5.2)
stakeholders          → [problem, business_context]
actors                → [stakeholders]
scope                 → [objectives, problem]
asis_process          → [problem, actors]
tobe_process          → [asis_process, scope, objectives]
business_rules        → [tobe_process]
business_requirements → [objectives, stakeholders, tobe_process, scope]   ★ the keystone unit
data_needs            → [business_requirements]
reporting             → [objectives, business_requirements]
benefits              → [objectives, scope]
assumptions           → [scope, business_requirements]
dependencies          → [scope, business_requirements]
constraints           → [scope]
risks                 → [objectives, scope, business_requirements]
issues                → [problem, asis_process]
implementation_approach → [scope, business_requirements, phasing-N/A]
phasing               → [implementation_approach, business_requirements]
change_management     → [stakeholders, tobe_process, phasing]
kpis                  → [objectives, benefits]
qualitative_success   → [objectives]
compendium            → [business_requirements, risks, decisions-N/A]     (suggests OQs/refs/glossary; decisions are user-only)
```

`generate_all` is a topological order over this DAG; independent peers parallelise (e.g. `stakeholders`,
`scope` and `asis_process` can fan out after `problem`). `business_requirements` is the keystone — most
downstream units consume it.

## 5. Project Context Bundle — a standalone, cross-module subsystem

> **Status:** lifted out of E4a's per-unit input plumbing into a **dedicated, reusable service**. BRD is
> the first consumer; FRS (E4c), NFR, Architecture and every future artifact module will import the same
> bundle. Built as a first-class subsystem under `backend/app/services/context/`, not a BRD-internal
> helper. This supersedes the inline `gather_cb_context_for_brd` sketch from earlier drafts.

### 5.1 What the bundle contains (the three layers — full coverage is mandatory)

A single composite object — `ProjectContextBundle` — holds **every layer of grounding context for the
current project**, in a stable typed shape. Three layers, each independently swappable / mockable.
**Full-corpus coverage is a hard invariant**: BRD generation does not run until every populated layer is
fully present (per the "Pre-generation precondition" in §5.6.1).

| Layer | Source | Underlying provider (reused) | Coverage guarantee |
|-------|--------|------------------------------|---------------------|
| **A. App Brain** | `ProjectApp.included` apps → **every** `AppFact` (across all kinds: capability / constraint / limitation / integration / gotcha) + **every** `AppWikiConcept` + per-app `impact_note` | `services/projects/app_context.py::load_app_facts_for_project` + `services/rag/wiki_grounding.py::gather_app_brain_context` (existing; new layer wraps these) | **All facts of all kinds for all in-scope apps** are included in the bundle; the wiki budgeter only trims at the prompt-rendering stage, never at the bundle stage. |
| **B. Project documents (PageIndex)** | **Every** `Document` row with `artifact_sources.included=true` AND `indexing_status='done'` — its PageIndex outline (root + sub-node titles + summaries) **plus** per-unit `tree_search` hits | `services/corpus_index` provider via `services/understanding/orchestrator.py::_retrieve_project_sections(..., document_ids=…)` (existing; from E2 + E4a) for depth-retrieval; new `services/context/docs_layer.py` for breadth-inventory | **Every included document is enumerated in the bundle** (breadth). Tree-search narrows per unit for depth-retrieval, but the doc inventory + outline is universal. |
| **C. Project Brief (Concept Brief)** | The project's **validated** Concept Brief — every current cb_* row, the original brief, the AI-enhanced brief, the full 14-question discover Q&A, the CB's pinned `VersionSnapshot` key | NEW `services/context/cb_layer.py` (full extraction, not just per-unit) | **Every populated CB sub-artifact** is in the bundle and must be projected to ≥ 1 BRD unit (§5.5). |

**Why this matters (the "every aspect must be covered" requirement):** narrow / query-only retrieval
makes generation non-deterministic over the same project corpus and silently drops material grounding.
A reviewer asking "which doc was this BR derived from?" must always have a non-empty, accurate answer
when a doc was uploaded. App Brain is the **operational-reality** layer that anchors BRs to what the
actual systems can/can't do — thinning it loses grounding. The CB is the **business-intent** layer that
the BRD must demonstrably cover end-to-end.

The bundle is **not a cache** — it is computed on demand per call, then narrowed per unit (§5.3). A
snapshot identifier of the bundle (the participating `VersionSnapshot` keys + a content hash + the
`Document` ids + their `tree_sha`s + the included `AppFact` ids) is pinned on each successful BRD
validate so FRS can prove what context the BRD was built against.

### 5.2 Module layout

```
backend/app/services/context/
├── __init__.py
├── project_context.py     # ProjectContextBundle dataclass + gather_project_context() entry-point
├── app_layer.py           # AppLayer: thin wrapper over app_context / wiki_grounding → typed shape
├── docs_layer.py          # DocsLayer: thin wrapper over corpus_index tree_search → typed shape
├── cb_layer.py            # CbLayer: full Concept Brief extraction (rows, text, discover Q&A)
├── projection.py          # project_for_unit(): per-unit narrowing of the bundle
└── coverage.py            # CoverageReport + the static coverage contract (§5.4)
```

Public entry point — the only function callers import:

```python
@dataclass
class AppFactBlock:
    app_id: UUID; app_name: str; tier: str | None
    impact_note: str | None
    facts_by_kind: dict[str, list[AppFactRow]]   # capability / constraint / limitation / integration / gotcha
    wiki_concepts: list[AppWikiConceptRow]       # ALL — budgeted only at render time

@dataclass
class AppLayer:
    apps: list[AppFactBlock]      # one per ProjectApp.included
    formatted: str                # [A#] tagged: per-app block + grouped facts + concepts

@dataclass
class DocOutlineNode:
    node_id: str; title: str; summary: str; page_start: int; page_end: int
    children: list["DocOutlineNode"]

@dataclass
class DocInventoryEntry:
    document_id: UUID; doc_name: str; mime: str; page_count: int
    indexing_status: str          # must be "done" to be in the bundle
    outline: list[DocOutlineNode] # full PageIndex tree (root + summarised nodes) — every doc
    included: bool                # mirror of artifact_sources.included for the requesting brief

@dataclass
class DocsLayer:
    docs: list[DocInventoryEntry]        # EVERY included, indexed project document — breadth
    sections: list[RetrievedSection]     # per-unit tree_search hits — depth
    formatted_inventory: str             # [DOC#] tagged: one block per doc with its outline
    formatted_sections: str              # [D#] tagged: doc + section + page range
    pending_docs: list[DocPendingEntry]  # any included doc whose indexing_status != "done"

@dataclass
class ProjectContextBundle:
    project: ProjectRead
    apps: AppLayer
    docs: DocsLayer
    cb:   CbLayer | None             # None when no validated CB (e.g. CB-only callers)
    generated_at: datetime
    snapshot_refs: dict[str, Any]    # {"cb": <key>, "doc_tree_shas": {...}, "app_fact_ids": [...]}
    coverage: CoverageReport         # see §5.4
    readiness: BundleReadiness       # see §5.6.1 — pre-generation precondition state

async def gather_project_context(
    project_id: UUID,
    *,
    db: AsyncSession,
    include_cb: bool = True,
    include_apps: bool = True,
    include_docs: bool = True,
    docs_query: str | None = None,        # per-unit tree_search query; outline is always returned
    docs_top_k: int | None = None,
    artifact_document_id: UUID | None = None,  # for artifact_sources doc filtering
    require_full_corpus: bool = True,     # fail-fast when any included doc is not yet indexed
) -> ProjectContextBundle: ...
```

`CbLayer` exposes **every** part of the validated Concept Brief — not just the bits a single unit
happens to want — so per-unit projection (§5.3) has the full surface to slice from:

```python
@dataclass
class CbLayer:
    text_blocks: dict[str, str]                  # all cb_text_blocks (keyed by field_key)
    context_map: list[CbContextMapRow]           # the 6 fixed dimensions
    outcomes: list[CbOutcomeRow]
    metrics: list[CbMetricRow]
    capabilities: list[CbCapabilityRow]
    scope_items: list[CbScopeItemRow]
    milestones: list[CbMilestoneRow]
    enhanced_brief: str | None
    original_brief: str | None
    discover_qa: list[CbDiscoverQuestionRead]    # all 14 discover Q&A with sources
    cb_snapshot_key: str                         # the validated CB's VersionSnapshot key
    formatted: str                               # [CB#] tagged, one block per cb_ sub-artifact
```

### 5.3 Per-unit projection

```python
def project_for_unit(
    bundle: ProjectContextBundle,
    *,
    artifact_type: str,           # "brd" | "frs" | …
    unit_key: str,
) -> UnitContext: ...
```

`UnitContext` is the narrowed view a DSPy unit actually consumes — three formatted strings (`apps`,
`docs`, `cb`) plus structured `traceability_seeds` (see §5.7). All knowledge of "which CB tables / which
app-fact kinds / which doc sections matter for this unit" lives in **one place**: a per-artifact
projection map in the manifest. Keeps DSPy units thin and makes coverage statically verifiable.

For BRD: a `BRD_CONTEXT_PROJECTION` table in `manifest/brd.py` (§5.5). Source of truth for which CB
pieces feed which BRD unit.

### 5.4 Full-coverage contract — "every aspect of the brief must be covered"

The BRD must demonstrably consume **every** populated Concept Brief sub-artifact. Concretely:

1. **Static map** — `BRD_CONTEXT_PROJECTION` (§5.5) declares, per BRD unit, which CB tables + which
   columns it consumes. The union of consumed cb_* tables across all BRD units must equal the set of
   non-empty cb_* tables. A `tests/test_brd_coverage_contract.py` lint-style test asserts this at the
   manifest level (no LLM needed) so a CB schema change that adds a new sub-artifact without wiring it
   into a BRD consumer fails CI immediately.
2. **Runtime report** — `gather_project_context` returns a `CoverageReport`:

   ```python
   @dataclass
   class CoverageReport:
       cb_rows_total: int              # all current, active cb_* rows + populated text-block fields
       cb_rows_projected: int          # those referenced by ≥ 1 BRD unit projection
       cb_uncovered: list[tuple[str, str]]   # (cb_table, row_key) not projected anywhere
       app_facts_total: int
       app_facts_projected: int
       doc_sections_total: int
       doc_sections_projected: int
       discover_qa_total: int
       discover_qa_projected: int
   ```
3. **Validate enforcement** — §8.1.G fails BRD validation if `coverage.cb_uncovered` is non-empty.
   Platform_admin override is permitted (and audited) per the same posture as other validate findings.

### 5.5 BRD-specific projection map (CB → BRD)

`backend/app/services/artifacts/manifest/brd.py::BRD_CONTEXT_PROJECTION` — exhaustive table. Every
populated CB element must appear in this table at least once:

| CB source | BRD consumer unit(s) | Relation |
|-----------|----------------------|----------|
| `cb_text_blocks.business_context` | `business_context` | derives_from |
| `cb_text_blocks.problem_statement` | `problem` | derives_from |
| `cb_text_blocks.value_hypothesis_if` / `_then` | `objectives`, `benefits` | informs |
| `cb_context_map.business_unit` | `stakeholders`, `business_context` | constraint |
| `cb_context_map.new_channel` | `scope`, `business_requirements` | informs |
| `cb_context_map.customer_segments` | `actors`, `stakeholders` | informs |
| `cb_context_map.current_gap` | `problem`, `asis_process` | informs |
| `cb_context_map.strategic_driver` | `business_context`, `objectives` | informs |
| `cb_context_map.engagement_goal` | `tobe_process`, `change_management` | informs |
| `cb_outcomes.*` | `objectives`, `benefits`, `kpis` | derives_from |
| `cb_metrics.*` (quantifiable + qualitative) | `kpis`, `qualitative_success` | derives_from |
| `cb_capabilities.*` | `business_requirements`, `scope` | derives_from |
| `cb_scope_items.in_scope` | `scope` | derives_from |
| `cb_scope_items.out_of_scope` | `scope` | derives_from |
| `cb_scope_items.assumption` | `assumptions` | derives_from |
| `cb_milestones.*` | `phasing`, `change_management` | derives_from |
| `cb_discover_questions.*` (answered Q&A) | `compendium`, `assumptions`, `dependencies` (when an answer flags one) | annotates |
| `cb_discover_enhanced_briefs.enhanced_brief` | `business_context` (verbatim available as upstream prose) | annotates |
| `cb_gate_criteria.*` | not projected — metadata only | — |

Every populated CB element has ≥ 1 consumer. The lone exception — `cb_gate_criteria` — is metadata
about CB validation, not requirements content; documented exclusion.

### 5.6 App Brain & document coverage (BRD-side)

**App Brain — full breadth, no kind dropped:**
- Every **app** in `ProjectApp.included` is surfaced to at least `business_context`, `scope`,
  `business_requirements`, `risks`, and `dependencies` (the "operational reality" units).
- Every app-fact **kind** (capability / constraint / limitation / integration / gotcha) has at least
  one consuming unit; the bundle carries every fact of every kind for every in-scope app — no
  query-time trimming:
  - `capability` + `integration` → `business_requirements`, `scope`, `tobe_process`
  - `constraint` + `limitation` → `risks`, `constraints`, `assumptions`, `business_requirements`
  - `gotcha` → `risks`, `issues`
- App-Brain wiki concepts are budgeted **only at prompt-render time** (token-aware truncation per unit),
  never at bundle-build time. The bundle keeps full fidelity so traceability snippets remain accurate.

**Project documents — every included doc is in the context:**
- The `DocsLayer.docs` inventory contains an entry for **every** `Document` row that is included for
  the BRD (`artifact_sources.included=true`) AND finished indexing (`indexing_status='done'`). Each
  entry carries the **full PageIndex outline** (root nodes + summarised children, page ranges). This is
  the **breadth** guarantee: a reviewer or downstream unit can always see what every project document
  covers at a glance, even when per-unit tree-search didn't surface it.
- Per-unit tree-search (`DocsLayer.sections`) narrows for **depth**: the manifest defines, per unit, a
  `docs_query` that pulls the most relevant sections from across all included trees. Breadth and depth
  are complementary, not alternatives.
- Every BRD unit that consumes documents (effectively all of `business_context`, `problem`,
  `objectives`, `stakeholders`, `actors`, `scope`, `asis_process`, `tobe_process`, `business_rules`,
  `business_requirements`, `risks`, `constraints`, `dependencies`, `assumptions`) is passed both the
  full `formatted_inventory` AND the per-unit `formatted_sections`. The unit's instruction tells it to
  prefer specific section citations from the depth-retrieval and use the inventory only for orientation.
- Zero included documents is allowed (the BRD then grounds only on apps + CB + Q&A); partial coverage
  (some included docs not yet indexed) is **not** allowed — see §5.6.1.

### 5.6.1 Pre-generation precondition — full-corpus readiness gate

`gather_project_context(..., require_full_corpus=True)` (the default for BRD generate) computes a
`BundleReadiness` and fails fast when not all included corpus is present:

```python
@dataclass
class BundleReadiness:
    ok: bool
    pending_docs: list[DocPendingEntry]      # included sources with indexing_status ∈ {pending,running}
    failed_docs:  list[DocPendingEntry]      # included sources with indexing_status='error'
    missing_apps: list[UUID]                 # in-scope apps with zero AppFacts loaded (rare; data bug)
    cb_validated: bool                        # gates the call; should already be true via the API gate
```

**Generation rule:**
- `pending_docs` non-empty → `POST …/artifacts/brd/generate` returns **409** with a structured payload
  listing the pending docs and their per-doc progress. The FE polls `GET …/documents` (existing) and
  re-attempts when all are `done`. UX banner: "X of Y documents still indexing — generation will run
  automatically when ready" (with an explicit "Generate without doc N" platform_admin escape hatch,
  audited).
- `failed_docs` non-empty → **409** with the failed list and remediation hints; user must either fix
  (re-upload, re-index) or de-select the doc from `artifact_sources` before retrying.
- `missing_apps` non-empty → **500-class** (data integrity error) — the apps in scope exist but have
  no facts; should not happen in a healthy project. Logged + audited.
- `cb_validated=false` → already 409'd at the API edge by `require_artifact_validated("concept_brief")`;
  re-asserted here as defence in depth.

**Validate gate parity:** at BRD validate time (§8.1.G) we re-check the bundle's readiness against the
**snapshot pinned at BRD generation** — if any included doc was de-selected, deleted, or marked failed
after generation, validate emits a finding ("source set changed; consider regenerating") rather than
silently passing on stale grounding.

**Why a precondition (not a best-effort):** partial-corpus generation produces BRs that miss material
constraints/capabilities documented in unfinished sources. The cost of waiting for indexing is bounded
(minutes); the cost of a missed compliance constraint in production is not.

### 5.7 Traceability emission (BRD-side wire-up)

The orchestrator wires the bundle through three roles:
1. **Generate** — `generate_unit(unit_key, …)` calls `project_for_unit(bundle, …)` → `UnitContext`, then
   passes its three formatted blocks (`apps`, `docs`, `cb`) to the DSPy signature **and** the
   `traceability_seeds` it computed (which source refs were eligible for this unit).
2. **DSPy unit output** — every row Pydantic model gains an optional `traces: list[TraceRef]` field:

   ```python
   class TraceRef(BaseModel):
       source_kind: Literal["cb_row","app_fact","doc_section","discover_qa"]
       source_ref:  str
       relation:    Literal["derives_from","constrained_by","enabled_by","informs","annotates"]
       excerpt:     str = Field(max_length=240)
       confidence:  Literal["high","medium","low"] = "medium"
   ```

   The unit's instruction tells it which `source_refs` are in-scope (from the seeds) and forbids
   inventing refs. Heuristic fallback: if the LLM returns 0 traces for a row that the manifest says
   should have ≥ 1, the orchestrator emits a "best-effort" trace pointing at the unit's primary CB
   source and flags `confidence="low"`.
3. **Persist** — `upsert_rows(brd_traceability, …)` writes one row per `TraceRef`; existing trace rows
   for the same `(target_table, target_row_key)` are diffed by `(source_kind, source_ref, relation)`
   (typed-column compare reused from E4a's versioning service).

Validate gate then asserts (§8.1.G):
- Every current `brd_business_requirements` row has ≥ 1 `brd_traceability` link.
- Every current `brd_kpis` row has ≥ 1 link (typically to a `cb_metrics` row).
- Every current `brd_objectives` row has ≥ 1 link (typically to a `cb_outcomes` row).
- Every current `brd_risks` row has ≥ 1 link (CB `out_of_scope` / app `constraint|limitation|gotcha`).

### 5.8 Reuse posture for future modules (E4c FRS and beyond)

- `services/context/` is **artifact-agnostic** — no `brd_*` symbol in it.
- `ProjectContextBundle.cb` is wrapped in an `Optional`; future modules can request `include_cb=False`
  if they ground only on apps + docs.
- When FRS lands, it adds (a) a `FrsLayer` accepting the validated BRD as an upstream layer, alongside
  the bundle's existing three, (b) its own per-unit projection map (`FRS_CONTEXT_PROJECTION`), and
  (c) the `artifact_traceability` rename that promotes `brd_traceability` to a generic table. None of
  that touches the bundle's existing shape.

### 5.9 DSPy unit prompt patterns — derived from `reference_mds/skills/brd-builder/SKILL.md`

SKILL.md doesn't ship LLM prompts directly — it encodes **invariants** that every unit prompt must
honour (solution-agnostic, traced, iterative, conflict-resolved). We translate those invariants into
a single **shared prompt scaffold** + 24 short per-unit overlays so the DSPy `Signature` docstrings
stay consistent without duplication. All of this lives in `backend/app/services/skills/
dspy_artifacts.py` as a `_BRD_SCAFFOLD` constant + per-unit overlay strings concatenated into each
Signature's docstring (DSPy reads the docstring verbatim — no Jinja, no templating engine).

#### 5.9.1 Shared scaffold — `_BRD_SCAFFOLD`

Prepended to **every** BRD unit Signature's docstring. Captures SKILL.md's universal rules:

```
You are generating one section of a Business Requirements Document (BRD). The BRD describes
**what** the business needs, never **how** it will be technically built — output stays
solution-agnostic (SKILL.md "Best Practices").

# Inputs the unit sees
- apps_context     — every fact of every kind for every in-scope app, [A#] tagged.
- docs_inventory   — outline (titles + summaries + page ranges) of every included project doc, [DOC#] tagged.
- docs_sections    — depth-retrieved sections relevant to THIS unit, [D#] tagged.
- cb_context       — the validated Concept Brief slice for THIS unit, [CB#] tagged. Treat the CB
                     as the BRD's **business intent** — the BRD operationalises it; it does not
                     contradict it without an explicit open_questions entry.
- discover_qa      — answered Q&A from the BRD Discover phase for THIS unit, [Q#] tagged.
- qa_pairs         — clarification Q&A appended after generation began.
- upstream         — current rows of the BRD units this one depends on (within the BRD).
- current_rows     — the current rows of THIS unit (with their stable row_keys).
- locked_rows      — rows the user has edited and locked; **reproduce them verbatim**.
- traceability_seeds — the set of source_ref values you are permitted to cite for this unit.

# Output rules (non-negotiable)
1. **Solution-agnostic.** Describe WHAT the business needs and what the to-be state looks like —
   not the technology that delivers it.
2. **Cite explicitly.** Every claim worth tracing carries inline `[CB#…]` / `[A#…]` / `[D#…]` /
   `[Q#…]` markers. Don't paraphrase a fact without citing its source.
3. **Conflict resolution (SKILL.md):** User statements > recent project documents > older
   references. SpecForge extension: app-brain facts sit lowest (they describe what systems can/can't
   do; business intent supersedes). On a real conflict, emit an `open_questions` entry rather than
   silently picking a side.
4. **Stable row keys.** For unchanged concepts, keep the `row_key` from `current_rows`. Mint new
   keys (continuing the natural sequence — e.g. `BR-007`) only for genuinely new rows. Never
   re-use a `status='removed'` key.
5. **Reproduce `locked_rows` verbatim** — no rephrasing, no "improvements".
6. **Emit traces.** For every output row this unit owns, populate `traces: list[TraceRef]` with
   `source_ref`s drawn from `traceability_seeds` — never invent. A row with `traces=[]` is allowed
   only when accompanied by an `open_questions` entry explaining the gap.
7. **Don't fabricate.** When inputs are silent on a fact, emit an `open_questions` row tagged
   `field=<missing-field>` rather than guessing.
8. **Register.** Business prose; present tense for as-is, future-conditional for to-be; third-person;
   no hedging ("perhaps", "might"); no marketing language; no implementation specifics.
9. **Build on upstream, don't restate it.** When `upstream` provides objectives/stakeholders/scope,
   reference them by row_key — don't redefine them in your output.
```

#### 5.9.2 Per-unit overlays — five representative examples

Each unit's Signature = `_BRD_SCAFFOLD` + a short, specific overlay describing **shape of output**,
**upstream tables to lean on**, **validate criteria the output must satisfy**. The full 24 overlays
live in `dspy_artifacts.py`; five canonical shapes:

**`business_context` (§1)** — "Compose: a 2–4 paragraph business overview, a 2–3 sentence
strategic-alignment statement, and ≥ 3 drivers each categorised as
regulatory|competitive|cost|growth|other. Seed from `cb_context.text_blocks[business_context]`;
expand with framing from `docs_inventory` (annual reports, exec memos) and `apps_context` for
operational landscape. Each driver row carries ≥ 1 trace to a CB row, doc section, or app fact."

**`objectives` (§3.1)** — "Generate 3–7 BRD objectives. Each row: single-sentence `statement`
('Reduce reconciliation time to ≤ 7 days'), `category` ∈
{operational|financial|customer|compliance|strategic}, `priority` ∈ {must,should,could}, `owner`
drawn from `cb_context.context_map.business_unit` or discover_qa. **Every objective traces to ≥ 1
`cb_outcomes` row OR the `cb_value_hypothesis_if/_then` blocks** — this is how the BRD inherits
the CB's business intent. (SKILL.md: 'Trace every requirement to an objective.')"

**`business_requirements` (§7 — keystone)** — "Generate the full BR table. Each
`brd_business_requirements` row must satisfy SKILL.md's validate checklist by construction:
- `row_key` matches `^BR-\d{3,}$` starting at `BR-001`.
- `title` — concise noun phrase, ≤ 12 words.
- `description` — one **testable** sentence using *must* / *shall* / *will* with a measurable
  predicate (deadline, threshold, observable state). NOT a feature description; not an
  implementation hint.
- `objective_ids` — ≥ 1 entry, each value present in `upstream.brd_objectives.row_key`.
- `stakeholder_ids` — ≥ 1 entry, each value present in `upstream.brd_stakeholders.row_key`.
- `priority` ∈ {must,should,could,wont} (MoSCoW).
- `acceptance_criteria` — Given-When-Then bullet list, ≥ 1 line per BR.
- `traces` — ≥ 1 outward trace per BR (CB capability / CB outcome / app capability / doc section).
Every populated `cb_capabilities` row should yield ≥ 1 BR; if intentionally deferred, emit an
`open_questions` row explaining the gap (closes the §5.4 CB-coverage loop)."

**`risks` (§10.1)** — "Generate **business** risks (not technical — those belong to FRS). Each
row: `description`, `cause`, `impact`, `likelihood ∈ {low,medium,high}`, `severity ∈
{low,medium,high}`, **non-empty `mitigation`** (SKILL.md validate criterion), `owner`. Anchor risks
in:
- `cb_scope_items.out_of_scope` (what we're NOT doing → risk),
- app `constraint` / `limitation` / `gotcha` facts (technical reality → business risk),
- `cb_metrics` (KPI thresholds → risk of missing them).
Every risk traces to ≥ 1 of those sources."

**`kpis` (§12.1)** — "Generate ≥ 1 KPI per measurable objective. Each row: `name`, `baseline`
(current state, quantified), `target` (desired state, quantified), `timeframe` (e.g. '90 days
post-launch', 'by Q4 2026'), `data_source` (which system / report provides the measurement),
`notes`. **Every KPI traces to ≥ 1 `cb_metrics` row** — if a CB quantifiable metric exists with no
corresponding KPI, emit an `open_questions` row. (SKILL.md validate: 'KPIs have baselines, targets,
and timeframes.')"

The remaining 19 overlays (process units pair as-is + to-be per SKILL.md's "Document both current
and future state processes"; assumptions/dependencies/constraints get short overlays; etc.) follow
the same shape.

#### 5.9.3 Anti-patterns (what NOT to put in unit prompts)

- **No hand-written few-shot demos in the docstring.** DSPy's optimiser (BootstrapFewShot / MIPROv2,
  enabled later) manages demonstrations separately; pinning examples in the docstring locks the model
  below the optimiser's reach.
- **No template echoing.** Each unit sees only the section it owns. Embedding the full BRD template
  would defeat the per-unit token-minimisation that motivated decomposition (E4 §Approach).
- **No cross-unit references.** Don't write "see the objectives unit" in a docstring. Each unit must
  be standalone — the orchestrator passes `upstream` rows explicitly.
- **No retrieval/scoring logic.** The bundle already handled retrieval; the unit only consumes its
  formatted context.
- **No verbatim validate checklist.** Mirror its criteria as concrete output constraints
  (e.g. "every BR has ≥ 1 `objective_ids` value"), not as a "you must pass this checklist" coda —
  the latter invites the model to *describe* compliance rather than *be* compliant. The actual
  checklist lives post-hoc in `validators/brd.py`.

#### 5.9.4 SKILL.md → prompt mapping (so the lineage is auditable)

| SKILL.md rule | Where it lands in the prompt scaffold |
|---|---|
| "Build iteratively rather than gathering all information upfront." | Discover Q&A is **per-unit** (`UNIT_DISCOVER_MAP`); each unit receives only the answers it needs. Re-running one unit doesn't reset others. |
| "Express solution-agnostic requirements focusing on **what** rather than **how**." | Scaffold rule #1 + rule #8 (register). Every overlay restates it where ambiguity is likely (e.g. `business_requirements` says "NOT a feature description"). |
| "Trace every requirement to an objective and validate with affected stakeholders." | `objective_ids` (≥ 1) + `stakeholder_ids` (≥ 1) are **structural fields** on `brd_business_requirements`, not free-text prose. Enforced by the row Pydantic model + validate §8.1.B. |
| "Document both current and future state processes." | Two distinct units — `asis_process` + `tobe_process` — both required; manifest dependency forces `tobe_process` to run after `asis_process`. |
| "Conflict resolution: User > Recent docs > Older refs." | Scaffold rule #3. Discover answers (user) override docs/apps; on real conflicts the unit emits an `open_questions` row instead of silently choosing. |
| "Every requirement has a unique ID (BR-001), testable description, linked objective, impacted stakeholders, AC, priority." | `business_requirements` overlay explicitly lists every field + heuristic for "testable". Validate §8.1.B re-checks. |
| "KPIs have baselines, targets, and timeframes." | `kpis` overlay names them as required fields. Validate §8.1.C re-checks. |
| "Risks identified with mitigations." | `risks` overlay requires non-empty `mitigation`. Validate §8.1.D re-checks. |
| Question states ❓✅❌ + composite IDs + `(New)` marker | Lives in Discover UI (E5 pattern, reused per-type). Not in DSPy prompts directly. |
| Output modes (`summary`, `section`, `full`, `diff`) | Lives at the API/FE layer (`GET …/artifacts/brd?mode=…`), not in the units. The units only produce row sets; rendering is downstream. |

#### 5.9.5 How discover Q&A enters prompts

Per `UNIT_DISCOVER_MAP` (§6.1), each unit receives **only its own** discover Q&A subset as
`discover_qa`. The scaffold's rule #3 tells the unit to **prefer discover answers when they conflict
with retrieved sources** — this is SKILL.md's "User > docs > apps" priority operationalised. The
`source` field on each discover answer (`brief|documents|app_brain|user|ai_enhanced|project`) lets
the unit weight its sources correctly without seeing the underlying retrieval machinery.

## 6. Discover phase for BRD

Reuses E5's pattern. Two design choices:

**Decision 1 (proposed):** generalise the E5 tables. Rename `cb_discover_questions` →
`artifact_discover_questions` and `cb_discover_enhanced_briefs` → `artifact_discover_enhanced_briefs`,
both keyed by `artifact_document_id` (which already carries `artifact_type`). One migration in `0018`
performs the rename + adds an index on `(artifact_document_id, question_key)`. Net result: zero new
discover tables for BRD — we share E5's. (Alternative: copy-paste `brd_discover_*` tables. Rejected for
duplication.)

**Decision 2:** the **catalog** is per-artifact-type. Add `backend/app/services/artifacts/
discover_catalog.py::DISCOVER_QUESTIONS_BY_TYPE` so E5's existing `discover_catalog` becomes a dict keyed
by `artifact_type`. CB keeps its 14 questions; BRD gets its own 18 (see §6.1). The `UNIT_DISCOVER_MAP`
and `PROJECT_PREFILL` likewise become per-type.

### 6.1 BRD Discover Catalog (18 questions, derived from SKILL.md Discover + Elicit areas)

| Key | Category | Question | Primary sources |
|-----|----------|----------|-----------------|
| 1a | initiative | Initiative name (working title for the BRD)? | project + CB |
| 1b | initiative | Concise restatement of the business problem this BRD solves | CB.problem_statement + brief |
| 1c | initiative | Primary business driver — regulatory, competitive, cost, growth? | CB + brief + docs |
| 1d | initiative | Initiative type — process change, system implementation, organizational, mixed? | brief |
| 2a | objectives | Top 3–5 measurable objectives this BRD must deliver | CB.outcomes + brief + docs |
| 2b | objectives | Which existing KPIs are in scope as baselines? | CB.metrics + app_brain.KPIs |
| 2c | objectives | What benefits are expected (financial / operational / customer / strategic)? | brief + docs |
| 3a | stakeholders | Executive sponsor + accountable owner | project (members) + brief |
| 3b | stakeholders | Most-impacted user groups / personas | app_brain users + docs |
| 3c | stakeholders | Stakeholder groups that must approve the BRD | brief + project members |
| 4a | processes | Briefly describe the current (as-is) process and its pain points | docs + app_brain.gotchas |
| 4b | processes | Briefly describe the desired (to-be) process | brief + CB.capabilities |
| 4c | processes | Material business rules / policies that constrain the to-be | docs + app_brain.constraints |
| 5a | scope | Items explicitly **out of scope** for this BRD | brief |
| 5b | scope | Major assumptions / dependencies / constraints | brief + docs + app_brain |
| 6a | risks | Top business risks if this initiative fails or is delayed | brief + docs |
| 7a | delivery | Known milestones / target dates / phasing constraints | brief + project.go_live_date |
| 7b | delivery | Change-management considerations (training, comms, rollout) | brief + app_brain |

**Project-field prefills (no LLM):**
```python
BRD_PROJECT_PREFILL = {
    "1a": lambda p: f"{p.name} — Business Requirements Document",
    "7a": lambda p: p.go_live_date.isoformat() if p.go_live_date else "",
}
```

**`UNIT_DISCOVER_MAP` for BRD** (which discover questions feed which unit):
```python
{
  "business_context":      ["1a","1b","1c","1d"],
  "problem":               ["1b","1c","4a"],
  "objectives":            ["2a","2c"],
  "stakeholders":          ["3a","3b","3c"],
  "actors":                ["3b"],
  "scope":                 ["5a","5b"],
  "asis_process":          ["4a"],
  "tobe_process":          ["4b","4c"],
  "business_rules":        ["4c"],
  "business_requirements": ["2a","4b","5a","5b"],
  "assumptions":           ["5b"],
  "dependencies":          ["5b"],
  "constraints":           ["5b"],
  "risks":                 ["6a","5b"],
  "kpis":                  ["2b","2c"],
  "benefits":              ["2c"],
  "phasing":               ["7a"],
  "change_management":     ["7b","3b"],
  # data_needs/reporting/issues/implementation_approach/qualitative_success/compendium: [] (rely on upstream rows)
}
```

### 6.2 DSPy modules — reuse E5

`BriefEnhancerModule` and `DiscoverAnalysisModule` from `dspy_discover.py` are **artifact-type agnostic**
(they take `questions_json` as input). We pass the BRD catalog at call time. **No new DSPy code for
discover.** Mock fixtures: `artifact_discover_brd_enhance_brief.json`,
`artifact_discover_brd_analysis.json` — both follow the existing schema.

### 6.3 Service functions

Reuse E5's `enhance_brief` / `analyze_brief` / `get_questions` / `answer_question` / `complete_discover`
unchanged. The functions already take `(project, artifact_type, ...)` — wire them through the per-type
catalog (Decision 2). `complete_discover("brd")` sets `doc.status = "in_interview"` and dispatches the
generation Celery task (see §7).

## 7. Orchestrator hooks (additions to E4a's generic orchestrator)

The generic `upsert_rows`, `generate_unit`, `generate_all`, `edit_row`, `regenerate_unit`, `restore_row`,
`validate` work as-is. **Net additions are wiring + traceability persistence, not new core functions:**

1. **Readiness check up front.** `generate_all("brd", …)` calls
   `gather_project_context(project_id, require_full_corpus=True)` once and checks `bundle.readiness.ok`;
   any pending/failed doc or missing app surfaces as a structured 409 from the enqueueing endpoint
   (§5.6.1). The bundle is computed once per `generate_all` call and reused across units — never per-unit
   from scratch (avoids re-indexing thrash and keeps `snapshot_refs` stable across the run).
2. **Bundle is the single context input to units.** `generate_unit(unit_key, bundle, …)` calls
   `project_for_unit(bundle, artifact_type="brd", unit_key=…)` to obtain the unit's narrowed view, then
   passes `apps_context: str`, `docs_inventory: str`, `docs_sections: str`, `cb_context: str` as
   separate DSPy inputs (clearer than one merged blob, easier for the unit to cite). Both
   `docs_inventory` (breadth — every included doc) AND `docs_sections` (depth — per-unit tree_search
   hits) are passed; the unit's instruction prefers depth citations and uses the inventory for
   orientation. Concept Brief units leave `cb_context` untouched (the bundle's `cb` is None when the
   caller is the CB itself).
3. **Trace persistence.** After `upsert_rows(…)` writes the unit's primary rows, the orchestrator
   collects each row's emitted `TraceRef`s (see §5.7), maps them to `brd_traceability` rows
   (`target_table=<unit's primary table>, target_row_key=row.row_key, …`), and runs
   `upsert_rows(brd_traceability, …)`. On regeneration, trace rows for unchanged target rows are kept;
   traces for changed/removed targets are versioned exactly like other rows.
4. **Gate re-check.** `generate_all("brd", …)` re-checks `require_artifact_validated("concept_brief")`
   inside the Celery task path (already enforced at the API edge — defence in depth).
5. **Validate selector.** `validate("brd", …)` runs the BRD-specific checklist (§8.1) — including the
   coverage + traceability + readiness checks introduced here — instead of CB's. Selector: the
   manifest's `validate_checks` list.

Celery task `workers/tasks.py::generate_brd(project_id, discover_context)` mirrors the existing
`generate_concept_brief` task; the bundle is built **inside** the task (NOT passed across the Celery
boundary — bundles can be large) via `gather_project_context(project_id, …)`. Real path uses a
dispatcher (`workers/dispatch.py::_run_async`) because BRD's ~24 units × Vertex latency can push
wall-time well past a typical request budget; the endpoint enqueues, the FE polls
`GET …/artifacts/brd` for status.

## 8. Validation gate — much stricter than CB

### 8.1 Checklist (from SKILL.md "Validate" + the template's invariants)

Implemented in `backend/app/services/artifacts/validators/brd.py` as a list of named checks. Each check
returns `(ok: bool, finding: str)`. The endpoint returns 409 with the failing checks (mirrors E4a).

**A. Required sections complete (existence):**
- `brd_text_blocks` has non-trivial entries for: `business_overview`, `problem_statement`,
  `current_situation` (≥ 200 chars combined per row, non-placeholder).
- `brd_drivers` ≥ 1.
- `brd_objectives` ≥ 1; `brd_stakeholders` ≥ 1; `brd_actors` ≥ 1.
- `brd_scope_items` has both ≥ 1 `in_scope` AND ≥ 1 `out_of_scope`.
- `brd_business_requirements` ≥ 1.

**B. Business Requirements quality (the hard part — SKILL.md is explicit):**
For every current `brd_business_requirements` row:
- `row_key` matches `^BR-\d{3,}$`.
- `title` non-empty; `description` ≥ 1 testable sentence (heuristic: presence of measurable verb
  like *must / shall / will / by ≤ … / within … / ≥ …*).
- `objective_ids` ⊆ current `brd_objectives.row_key` set AND ≥ 1.
- `stakeholder_ids` ⊆ current `brd_stakeholders.row_key` set AND ≥ 1.
- `priority ∈ {must, should, could, wont}`.
- `acceptance_criteria` non-empty AND looks like a list / Given-When-Then (heuristic: ≥ 1 line
  starting with `-`, `*`, `1.`, `Given`).

**C. KPIs (template Optional but SKILL.md Validate insists):**
- If any `brd_kpis` rows exist → each row must have `baseline`, `target`, AND `timeframe` non-empty.
- Soft gate: if `brd_objectives` ≥ 1 AND `brd_kpis` = 0 → emit a **warning** finding ("BRD validated
  with no KPIs"); pass.

**D. Risks:**
- For every current `brd_risks` row: `mitigation` non-empty AND `severity, likelihood ∈ {low,medium,high}`.

**E. Trace integrity:**
- No `brd_business_requirements.objective_ids` entry points at a `status='removed'` objective.
- No `brd_kpis` references an objective by name that no current `brd_objectives` row matches (best-effort
  fuzzy: KPI name appearing in objective.statement).

**F. Per-unit completeness:** every unit in the manifest has `unit_status[unit_key].completeness ≥ 90`.

**G. Context coverage + traceability (new — enforces §5.4 + §5.7):**
- `bundle.coverage.cb_uncovered == []` — every populated Concept Brief sub-artifact is consumed by ≥ 1
  BRD unit per the static `BRD_CONTEXT_PROJECTION`. Findings: list of `(cb_table, row_key)`.
- `bundle.readiness.ok` at the time of the BRD's last generation snapshot, AND the **current**
  `artifact_sources` set matches the pinned `snapshot_refs.doc_ids`. If a source was added / removed
  since generation, emit a finding ("Source set changed; consider regenerating before validating").
- **Every `brd_business_requirements` row has ≥ 1 `brd_traceability` link** (mandatory). A BR with no
  trace cannot be approved.
- **Every `brd_kpis` row has ≥ 1 `brd_traceability` link** — typically to a `cb_metrics` row.
- **Every `brd_objectives` row has ≥ 1 `brd_traceability` link** — typically to a `cb_outcomes` row or
  CB `value_hypothesis_*`.
- **Every `brd_risks` row has ≥ 1 `brd_traceability` link** — typically to a CB `out_of_scope` /
  `assumption` or an app `constraint|limitation|gotcha` fact.
- For every `brd_traceability` row, `source_ref` must resolve in the pinned bundle (i.e. the CB row,
  app fact, doc section, or discover Q&A it points at must still exist in current state). Orphan trace
  refs surface as findings, not silent passes.
- Soft check: every `ProjectApp.included` app has ≥ 1 `brd_traceability` row pointing at one of its
  facts. If an in-scope app contributed nothing to the BRD, surface a warning finding ("App X is in
  scope but no BR/risk/constraint traces back to its facts — review or remove from scope").

### 8.2 On pass
Set `cb_gate_criteria` analogue (we don't have one in BRD's template — skip), set
`artifact_documents.status='validated'`, write `validated_at`/`validated_by`, pin a `VersionSnapshot`
with `document_key=f"brd:{project_id}"` and `changed_sections={"table.row_key": version, …}` of all
current rows. `audit.emit("artifact.validated", artifact_type="brd")`.

### 8.3 Downstream gate
`require_artifact_validated("brd")` becomes the **prerequisite for FRS** (E4c). For now it's wired only
into a placeholder FRS router stub that returns 501 — the gate factory is exercised by tests.

## 9. API — additions to E4a's generic router

The generic router already covers everything **except**:
- The legacy E3 `POST /api/projects/{id}/specs/brd` endpoint (one-shot generation into a `Spec` row).
  **Behaviour decision:** keep the endpoint live but mark it `Deprecation: true` in response headers
  and add a `services/specs/registry.py` flag `legacy_only=True`; the StageMap UI hides the legacy
  BRD generate button when the new BRD artifact exists. Removal lands with E4c (FRS-only break).

- `POST /api/projects/{id}/artifacts/brd/generate` → enqueues `generate_brd` (Celery) and returns
  `{job_id, status:"queued"}`; the FE polls `GET …/artifacts/brd` for `status` ∈
  `in_discover|in_interview|generating|validated`.

- `POST …/artifacts/brd/validate` runs the §8.1 checklist; 409 envelopes the failing items.

- `GET …/artifacts/brd/export/markdown` returns the rendered BRD as `text/markdown` attachment.

All other verbs (`POST units/{unit_key}/generate`, `POST .../regenerate`, `POST .../answer`,
`PATCH .../rows/{table}/{row_id}`, `POST .../rows/{table}/{row_id}/restore`, history, unlock, source
toggles, discover endpoints) are **already generic** in E4a/E5 — they accept `artifact_type="brd"` once
the manifest + tables exist. The `table` whitelist in those routes is extended to the `brd_*` set.

**Schemas** (`backend/app/schemas/artifact.py` extensions): per-table `BrdRowRead` types for the 21
tables + their `RowEditIn` shapes. Use a small Pydantic generator (one factory function that introspects
the SQLAlchemy column list) to avoid 21 hand-written pairs.

## 10. Markdown export

`backend/app/services/export/artifact_markdown.py` (built by E4a) is already manifest-driven. Register
the BRD manifest's section order + table column mapping. The exporter then:
1. Renders YAML frontmatter (title=`{project.name} — Business Requirements Document`,
   `artefactType="brd"`, `generatorSkill="brd-builder"`, `artefactId="brd-{project.human_id.lower()}"`,
   `generatedAt=now()`).
2. Builds the Document Control table from `VersionSnapshot` history of `brd:{project_id}` (rows: version,
   date, author, summary, approved-by).
3. Renders each of the 14 sections in template order: prose blocks from `brd_text_blocks` filtered by
   `field_key`, pipe tables from each `brd_*` row table in template column order, `current` rows only.
4. Appends an auto-generated **Appendix A — Traceability Matrix** (the BRD template's §14.1
   "References" is replaced/augmented by this) — one row per `(target_table, target_row_key)` showing
   its trace links. Columns: BRD Row · Source Kind · Source Ref (human-readable: e.g. "CB outcomes / o-3:
   Reduce reconciliation time 70%", "PayHub / capability: Multi-rail settlement", "151012-Press-Release.pdf
   § Problem Overview (p.2)") · Relation · Excerpt · Confidence.
5. Appends **Appendix B — Context Sources Snapshot**: the bundle's `snapshot_refs` rendered as a table —
   pinned CB version, included doc ids + `tree_sha`s + filenames, included app ids + names — so a
   reviewer can reproduce exactly what context the BRD was generated against.

No new exporter code beyond manifest registration + the two appendix renderers. Smoke-test: golden-file
diff against `tests/fixtures/exports/brd_golden.md`.

## 11. Frontend

### 11.1 Workspace card (`app/projects/[id]/page.tsx`)

The SDLC Artifacts pipeline card already has a **BRD chip** (built by E4a as disabled-with-tooltip).
Wire it live:
- **Disabled** while `cb.status !== "validated"` → tooltip "Validate the Concept Brief first".
- **Active** once CB is validated. Click → `/projects/[id]/artifacts/brd`.
- Status chip mirrors the artifact's `status` (`in_discover|in_interview|validated`).
- Once BRD is validated, the **FRS chip** flips from "coming soon" to disabled-with-tooltip (no live
  builder yet) — establishes the next gate visually.

### 11.2 Builder route `app/projects/[id]/artifacts/brd/page.tsx`

**Identical shell as Concept Brief** — uses the same `ArtifactBuilderPanel` component (E4a) and the
E5 `DiscoverPhase` / `DiscoverQADrawer` (parameterised by `artifactType`). Net-new visuals:
1. **BRD has ~21 row tables** vs CB's 8 → the right panel's section list becomes scrollable with
   **per-section anchors** in a sticky sub-rail (Section 1 → 14 quick-jump). Reuse the section emoji
   set from SKILL.md (🎯 / 👥 / 🔄 / 📊 / ⚡).
2. **Project Context strip — three sources, collapsible** at the top of the right column. One row per
   layer with a count badge and an expand-to-detail action; reuses the workspace's source-badge palette
   from E5:
   - **App Brain — `N apps · M facts`** — chips per in-scope app with `impact_note`; click → drawer
     showing facts grouped by kind (capability / constraint / limitation / integration / gotcha) +
     wiki concepts. Edit-scope link → `EditProjectModal`.
   - **Project documents — `K of K indexed`** — every included doc as a chip with `indexing_status`
     icon; click → drawer with each doc's PageIndex outline (root nodes + summaries + page ranges)
     plus a "view markdown" affordance. Pending / failed docs are surfaced visibly (see §11.2.1).
   - **Concept Brief — `validated v.X`** — collapsible preview of the validated CB's problem statement
     + objectives + capabilities; "Open Concept Brief →" link. Banner "CB changed since last BRD
     generation — regenerate to incorporate" when the project's CB has a newer `VersionSnapshot` than
     the BRD's pinned `snapshot_refs.cb`.
3. **Trace chips on rows** — each BR / KPI / objective / risk row shows chips for its
   `brd_traceability` links: e.g. `← CB: o-3` (CB outcome) / `← PayHub: capability` (app fact) /
   `← Press-Release.pdf §Problem` (doc section). Clicking a chip opens a side preview of the source
   snippet. A row with **zero** outward traces is rendered with a red "no trace" badge and lists in the
   Validate findings (§8.1.G). Within-BRD `objective_ids` / `stakeholder_ids` chips render alongside
   external trace chips, visually distinct (filled vs outlined).
4. **CB coverage panel** (new) — a small "CB coverage: X/X covered" badge in the action bar; click →
   drawer showing the `BRD_CONTEXT_PROJECTION` matrix with green/red dots per cb_* row. Uncovered CB
   rows are listed in their own group so the user can either edit a BRD row to cite them or accept the
   gap (audited).
5. **KPI row form**: explicit baseline + target + timeframe fields are required (red border until
   filled); reflects the validate check.
6. **Validate button** shows count of failing checks as a badge (e.g. `Validate (3 findings)`); clicking
   opens a drawer with the §8.1 results grouped by check category (A–G), with the coverage + trace
   findings under their own header.

### 11.2.1 Document readiness UX

The builder's "Generate BRD" CTA is **disabled** with an inline message whenever
`bundle.readiness.pending_docs` is non-empty, surfacing per-doc progress:

```
⏳ 2 of 5 documents still indexing — generation will run automatically when ready
   • 151012-Press-Release.pdf   running   (47% · ~30s remaining)
   • Settlement-Manual.docx     pending
```

When `failed_docs` is non-empty, the CTA is disabled and the row shows a re-upload / re-index action.
A platform_admin "Generate anyway (skip pending docs)" escape hatch is offered behind a confirm dialog
(audited as `brd.generate.partial_corpus`). Zero included docs is allowed and the CTA is enabled with a
neutral "No project documents in scope — generating from apps + CB only" notice.

### 11.3 Client / hook

`api.artifacts` namespace already exists; only `lib/types.ts` needs `Brd*Row` types for the 21 tables.
`useArtifact(projectId, "brd")` reuses the existing hook unchanged.

## 12. Build order

**Phase A — Standalone Project Context Bundle subsystem (cross-module foundation).** Build this first
because BRD generation depends on it AND because FRS will reuse it verbatim.

1. `services/context/{__init__.py, project_context.py, app_layer.py, docs_layer.py, cb_layer.py,
   projection.py, coverage.py}` — the bundle subsystem (§5.1–5.4). Reuses existing
   `load_app_facts_for_project` / `gather_app_brain_context` / `_retrieve_project_sections` as
   primitives. Adds the new `DocsLayer` breadth-inventory (full PageIndex outline per included doc) +
   `BundleReadiness` precondition (§5.6.1).
2. `tests/test_project_context_bundle.py` — mock-fixture unit tests for: layer composition, full-corpus
   readiness gate (pending → 409, all-done → ok, zero docs → ok), CB layer extraction, per-unit
   projection, snapshot_refs determinism.

**Phase B — Generalise E5 discover.**
3. Rename `cb_discover_*` → `artifact_discover_*` (Decision 1+2); pivot catalog to per-`artifact_type`.
   Single migration step inside `0018`.

**Phase C — BRD data + manifest.**
4. `models/artifact.py`: 21 `brd_*` model classes + `brd_traceability` (using `VersionedRowMixin`);
   register in `models/__init__.py`.
5. Migration `0018_brd_artifact.py`: 22 tables (21 + traceability, DRY loop) + the discover rename +
   enum guards; round-trip test.
6. `services/artifacts/manifest/brd.py`: 24 unit entries (writes, depends_on, instruction,
   discover_keys, validate_checks, docs_query) + `BRD_CONTEXT_PROJECTION` map (§5.5) +
   `tests/test_brd_coverage_contract.py` (the static CB-coverage lint).

**Phase D — DSPy + validators + discover catalog.**
7. `services/skills/dspy_artifacts.py`: 24 unit Modules + 24 row Pydantic model groups (each row model
   gains an optional `traces: list[TraceRef]` field) + 24 mock fixtures under
   `services/llm/fixtures/artifact_<brd_unit>.json` (mocks include realistic traces).
8. `services/artifacts/validators/brd.py`: §8.1 A–G checklist (including the new coverage + trace +
   readiness checks); wire into `validate("brd", …)`.
9. `services/artifacts/discover_catalog.py`: per-type registry + the BRD catalog (§6.1).

**Phase E — Orchestrator + transport.**
10. Plumb `ProjectContextBundle` through `generate_unit` (replaces the per-unit `cb_context` sketch);
    add traceability emission to `upsert_rows`.
11. `workers/tasks.py::generate_brd` Celery task + `dispatch._run_async` wrapper; readiness 409
    surfacing in the enqueue endpoint.
12. `api/artifacts.py`: extend `table` whitelist to `brd_*` (incl. `brd_traceability`); add the
    BRD-specific export route + the readiness-payload shape for the 409 response.
13. `schemas/artifact.py`: per-table `BrdRowRead` (incl. `BrdTraceabilityRead`) + `RowEditIn` via a
    factory.

**Phase F — Export + frontend.**
14. `services/export/artifact_markdown.py`: register BRD manifest (mainly data) + Appendix A
    (traceability matrix) + Appendix B (snapshot refs); golden export test.
15. Frontend: `lib/types.ts` BRD row types; flip BRD chip in workspace card; build the **tri-layer
    Project Context strip** (App Brain · Documents · CB) + trace chips on BR/KPI/objective/risk rows
    + CB coverage panel + KPI-row required-fields form + Validate findings drawer + the document
    readiness UX (§11.2.1).

**Phase G — Verify + retire legacy.**
16. E2E + mock pytest verification (§14).
17. Mark legacy `POST /api/projects/{id}/specs/brd` deprecated in API + hide its UI when the new BRD
    artifact exists.

## 13. Decisions / notes

1. **Project Context Bundle is a standalone subsystem** (`services/context/`), not a BRD-internal
   helper. Built once here, reused by every future artifact module (FRS, NFR, Architecture, …). The
   subsystem is artifact-agnostic; per-artifact knowledge lives in each manifest's
   `*_CONTEXT_PROJECTION` map.
2. **Full-corpus coverage is mandatory**, not best-effort. The bundle carries: every fact of every kind
   for every in-scope app, every included project document's PageIndex outline (breadth) PLUS per-unit
   tree-search hits (depth), and every populated CB sub-artifact. BRD generation **blocks** on partial
   doc indexing (with progress UX), rather than silently generating against a subset.
3. **CB → BRD coverage is statically verified.** A `BRD_CONTEXT_PROJECTION` table is the contract;
   a lint-style test fails CI if any populated CB sub-artifact has no BRD consumer. Runtime
   `CoverageReport` is a defence-in-depth re-check at validate time.
4. **BR / KPI / objective / risk traceability is mandatory** — every such row must carry ≥ 1
   outward trace to its source (CB row · app fact · doc section · discover Q&A) in `brd_traceability`.
   Within-BRD references (`objective_ids`, `stakeholder_ids`) are separate and complementary.
5. **Generalise discover tables** (`artifact_discover_*`) rather than duplicate per-type — eliminates
   ~140 lines of model + migration code per new artifact and trivialises FRS later. Migration includes
   a forward rename + data preservation; `cb_*` historical rows keep their `artifact_document_id`.
6. **Per-type catalogs**, not per-type DSPy modules. `BriefEnhancerModule` and `DiscoverAnalysisModule`
   are already artifact-agnostic; only the question list changes.
7. **BRD generation is async (Celery)** — ~24 units × Vertex latency exceeds a sane request budget;
   CB stayed sync because it's only 6 units. Mock path stays inline (fixtures resolve instantly).
8. **Bundle is built inside the Celery task, not passed across the boundary** — bundles can be large
   and contain DB-bound objects. The task rebuilds from `project_id` and pins `snapshot_refs` on the
   resulting validate `VersionSnapshot`.
9. **Concept Brief → BRD context is a one-way snapshot read**, not a live link. Editing CB after BRD
   generation does **not** retroactively change BRD rows; the FE surfaces a "CB changed — regenerate"
   hint and lets the user choose when to absorb the delta.
10. **Trace integrity is a validate-gate finding, not a write-time block.** A BR can reference an
    objective_id (within-BRD) or a CB row (external trace) that later gets removed. The orphan is
    surfaced at validate time, not silently mutated. Auditable.
11. **Document Control table is export-time, computed.** Versions come from `VersionSnapshot` history
    of `brd:{project_id}`; "approved by" comes from `validated_by`. Appendix A (traceability matrix)
    and Appendix B (context snapshot) are also export-time, computed from `brd_traceability` and the
    pinned `snapshot_refs`. No new persistence.
12. **Legacy E3 `brd` spec stays alive** for back-compat through E4b; flagged for removal in E4c when
    FRS lands and the new pipeline fully supersedes the old.
13. **PII out of scope** (project-wide). BRD rows can contain PII-like content (stakeholder names,
    customer segments); we do not detect/classify/redact. Confirmed by memory + project CLAUDE.md.

## 14. Verification

**Migration round-trip:** `make migrate`; `alembic downgrade -1` → `upgrade head` reproduces all 21 BRD
tables + enums + the discover rename. Existing CB rows are intact post-rename.

**Mock pytest (`LLM_PROVIDER=mock`, real PG/Redis, unique ids):**

*Project Context Bundle subsystem:*
- `gather_project_context` returns full apps + full docs inventory + full CB layer for a healthy
  fixture project.
- Coverage report on a fully-populated CB shows `cb_uncovered=[]` against `BRD_CONTEXT_PROJECTION`.
- `tests/test_brd_coverage_contract.py` (static lint) passes — every populated cb_* table has a BRD
  consumer.
- **Readiness gate:** a project with one `indexing_status='running'` doc → `bundle.readiness.ok=false`
  with the pending doc surfaced; `POST …/artifacts/brd/generate` returns 409 with the readiness
  payload. Once the doc flips to `done`, the same call enqueues successfully.
- A project with zero included docs → `bundle.readiness.ok=true`; generation proceeds; the BRD is
  validatable without doc traces (just CB + apps traces).
- `snapshot_refs` is deterministic for the same input state; changes when an included doc/app/CB
  version changes.

*BRD generation + versioning:*
- `generate_brd` → version-1 rows in every `brd_*` table in dependency order; BR rows reference current
  objective+stakeholder row_keys.
- **Every** generated BR / KPI / objective / risk row has ≥ 1 `brd_traceability` row populated by the
  orchestrator (mocks include realistic `traces`).
- Rerunning a unit with no new info → 0 new versions for both primary rows AND trace rows
  (typed-column compare).

*Validation gate (§8.1):*
- Blocks (409) on: missing KPI baseline (C); orphan objective_id within-BRD (B); non-testable BR
  description (B); a BR with zero `brd_traceability` links (G); `cb_uncovered` non-empty (G); a stale
  source set where a doc was de-selected post-generation (G — soft finding); an in-scope app with
  no contributing traces (G — warning).
- Once all pass: `status=validated`, `VersionSnapshot` pinned with `snapshot_refs`, `audit.emit` fires.

*Edits + traces:*
- `edit_row(brd_business_requirements, …)` → version 2, locked; re-running the unit does not overwrite;
  the BR's traces persist unless explicitly removed by the user.
- Editing a BR to remove its last trace → blocked (409) with a clear "BRs require ≥ 1 source trace"
  message; user must either add a manual trace OR delete the BR.

*CB → BRD wiring:*
- With CB validated, every BRD unit consuming CB sees a non-empty `cb_context` slice per
  `BRD_CONTEXT_PROJECTION`.
- With CB NOT validated, BRD endpoints 409 (gate). `require_artifact_validated("brd")` works
  symmetrically (stub FRS endpoint returns 409 → 501 once BRD validated).

*Export:*
- `export/markdown` reproduces template structure (golden diff empty), AND Appendix A renders one row
  per `brd_traceability` link with human-readable source refs, AND Appendix B lists the pinned
  `snapshot_refs`.

**Live (opt-in, `@pytest.mark.slow`):** one end-to-end with real Vertex on a small seeded project to
sanity-check unit prompts. Excluded from CI.

**E2E UI** (`make dev-be` + `make dev-fe`, `admin@specforge.test`): create project → seed CB → validate
CB → BRD chip activates → open BRD builder → discover → 4 gap questions → analyze → generate (Celery
progress) → builder shows 14 sections + ~21 tables + CB context strip + impacted-apps strip → edit a BR
(verify trace chips + lock + v2) → validate (3 findings shown, fix them) → re-validate (pass) → export
markdown → BRD chip flips to "Validated", FRS chip flips to "coming soon (disabled — BRD validated ✓)".

**Lint/type/test:** `make typecheck && make lint && make test-be` green.

## 15. Risks

- **Bundle build cost.** Building a `ProjectContextBundle` with full doc inventory + every app fact +
  full CB rows can be 10–100s of KB and 50+ DB rows. Mitigation: build once per `generate_all` and
  re-use across units; the formatted strings are computed lazily per layer; tree-search hits are
  capped by `top_k`; the wiki budgeter trims only at prompt-render time. For the unit-level re-run
  path (`generate_unit` after a Q&A answer), the bundle is rebuilt — measure and add a per-task in-
  memory cache if it shows up.
- **Full-corpus readiness blocks generation.** A user with a slow-indexing 200-page PDF can't generate
  BRD for minutes. Mitigation: indexing is async + visible (the existing per-doc progress UI);
  platform_admin "Generate anyway (skip pending docs)" escape hatch exists; the cost of waiting (mins)
  is bounded vs. the cost of missing a documented constraint (unbounded).
- **CB coverage map drift.** A new `cb_*` sub-artifact added without a BRD consumer slips through.
  Mitigation: `tests/test_brd_coverage_contract.py` (static, no LLM) fails CI immediately on a missing
  consumer.
- **LLM trace fabrication.** Units may invent plausible-but-wrong `source_ref`s. Mitigation: the unit's
  `traceability_seeds` enumerate the *allowed* refs for that unit; the orchestrator drops any
  `source_ref` not in the seeds and emits a "best-effort" fallback trace pointing at the unit's primary
  CB source with `confidence="low"`. Validate gate's "orphan trace" check (§8.1.G) catches anything
  that slips through.
- **Manifest is the contract** — a regression in `manifest/brd.py` (wrong `depends_on`, missing
  `writes`, mistyped `row_key`, mis-mapped `BRD_CONTEXT_PROJECTION`) breaks generation silently. Add a
  manifest self-test (`tests/test_brd_manifest.py`): every `writes` table exists; every `depends_on`
  resolves; the DAG is acyclic; every unit has ≥ 1 discover key OR an explicit `[]`; every
  `BRD_CONTEXT_PROJECTION` row's BRD unit exists and writes the table it claims to consume into.
- **Within-BRD trace drift** — easy to introduce on regen (objective_id removed, BR still cites it).
  Mitigation: the orchestrator passes `current_rows` *with* row_keys to the DSPy unit and the unit
  prompt instructs id-stability; trace integrity is enforced at validate, not write.
- **Vertex latency on `generate_all`** — ~24 units. Mitigation: Celery + topological parallelism (e.g.
  `stakeholders`/`scope`/`asis_process` fan out after `problem`). Budget: aim for ≤ 90 s p50 on real
  Vertex with parallel branches.
- **Discover-table rename touches existing CB data.** Mitigation: the rename in `0018` uses
  `ALTER TABLE … RENAME TO` (atomic in PG) + index renames in the same migration; downgrade reverses.
  Idempotency guards (`IF EXISTS`) keep the migration safe on partial-state DBs.
- **KPI / risk validation heuristics** can flag false positives (e.g. a perfectly good descriptive
  AC that just lacks a `must/shall`). Surface findings as a *blocking checklist with overrides allowed
  only to platform_admin* (audited) — same posture as CB validate today. Tune over time.
- **Legacy E3 `brd` spec coexistence** — two BRD-shaped objects on the same project until E4c.
  Mitigation: the workspace card hides the legacy one once the new artifact exists; documented in the
  changelog.
- **FRS deferred** — the gate factory is wired and tested via a stub endpoint so we don't ship a
  regression later.
