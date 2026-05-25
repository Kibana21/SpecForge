# E4 — SDLC Artifacts Module: Concept Brief → BRD → FRS (DSPy, per-sub-artifact, row-versioned)

## Context

The company has a 3-stage requirements workflow encoded as Claude-Code skills + templates in `reference_mds/`:
**rough concept → Concept Brief (Stage 0) → BRD (Stage 1) → FRS (Stage 2)**. The skills are guided Q&A
flows (Discover → Elicit → Validate → gate). The business user is **afraid to use Claude Code directly**,
so we rebuild this as **first-class modules inside the SpecForge web app**, using **DSPy** as the generation
engine, with **every row of every artifact stored in its own DB row so it can be edited and versioned individually**.

This is a **new, parallel "SDLC Artifacts" capability** attached to the existing `Project` — it does **not**
replace SpecForge's existing functional/technical/user-stories spec pipeline (E3). It reuses project context,
PageIndex source retrieval, App-Brain grounding, audit, and the DSPy/mock-first plumbing.

## Approach (per user direction)

Build **module by module**; within each module decompose the artifact into **sub-artifacts**, one **focused DSPy
module per sub-artifact** — NOT one giant whole-artifact call.

- **A "generation unit" = one focused DSPy call** that produces one prose field OR all rows of one table
  (e.g. "generate the Objectives table" → N objective rows in one small call). Not one call per row. Each produced
  **row is stored and versioned individually**.
- **Token-minimized**: each call carries only that sub-artifact's instruction + grounding + the specific upstream
  sub-artifacts it depends on — never the whole template. (Removes the BRD token-budget risk of one-shot.)
- **Dependency-ordered generation (a DAG)**: units run in order so upstream output grounds downstream (Problem
  Statement → Objectives → Business Requirements). Independent units run in parallel.
- **Template + SKILL.md drive a per-module manifest** (structure rarely changes → hardcode per module): the
  template defines the tables + typed columns; the SKILL.md defines the **Discover questions**, **elicitation
  focus**, and the **Validate checklist** (gate criteria). Read BOTH files per skill.
- **Concrete row-level storage + versioning** (see data model): one typed table per sub-artifact; each row carries
  its own `version` + `is_current`.
- **Guided Q&A interview**: open questions tagged to the affected sub-artifact; answering re-runs only that unit
  (+ downstream dependents), then human-validates at a per-artifact gate. Concept Brief validated before BRD; BRD
  before FRS (future).

> **Concept Brief (first module) has a dedicated, build-ready plan: `E4a-concept-brief.md`.** BRD/FRS will get
> `E4b`/`E4c` later. This umbrella file holds the shared decisions + cross-module model.

### Applies to all three modules (yes)
- **Concept Brief** — ~8 units / tables. Clean fit.
- **BRD** — ~24 units / tables (each ~20 template tables + free-text; BR-/objective-/risk-IDs are natural row keys).
  Strongest near-term case — exactly where one-shot would have broken.
- **FRS** (future) — decomposition effectively mandatory (endpoints/entities/screens/FRs/scenarios/rules + a
  traceability index whose rows are versionable). Same model extends directly; deferred for scope (NFR/Architecture
  inputs + Figma-less UI-spec).

### Per-module manifest — `backend/app/services/artifacts/manifest/`
One manifest per module (`concept_brief.py`, `brd.py`; `frs.py` later) from reading template + SKILL.md. Each entry
= one generation unit: `unit_key, table_model, section, ordinal, title, kind(prose|table), row_id_field(natural key
column|None), depends_on[], unit_instruction(template [G]), discover_questions(SKILL.md), validate_checks(SKILL.md)`.
Source of truth for: generation order (topological over `depends_on`), the DSPy instruction per unit, the Q&A
questions, the gate checklist, and table→section render order.

---

## Impacted Applications — project app-scope as first-class artifact context

**Why:** a Concept Brief / BRD is about a change to specific applications; grounding generation in those apps'
documented capabilities, constraints, integrations and limitations is what makes the output highly contextual.

**Mostly already exists — reuse:**
- `ProjectApp` (`models/project_intake.py`) links project↔app with `included`/`suggested`. Project **create**
  already accepts an `app_ids` list and creates `ProjectApp` rows (`api/projects.py`); the intake wizard's "Apps
  in scope" step selects them via `api.apps.suggest` → `services/projects/discovery_service.py::suggest_apps`
  (pgvector ranking). `ProjectDetail.apps_in_scope[]` already returns them.
- Grounding helpers keyed on `ProjectApp.included`: `app_context.py::load_app_facts_for_project` (AppFacts) and
  `rag/wiki_grounding.py::gather_app_brain_context` (AppWikiConcept).

**Selection model (important):** the **primary, required action is selecting apps from the registry** — the user
picks from the suggested + searchable list of **onboarded** apps (`app_ids`), **never free-types an app name**
(prevents wrong/duplicate entries; keeps grounding keyed to real `App` rows). The per-app `impact_note` is a purely
**optional** free-text annotation on a *selected* app.

**Delta to build:**
1. **Edit support (the real gap)** — app scope is only settable at create today. Add `app_ids` (+ optional per-app
   `impact_note`) to `ProjectUpdate` (`schemas/project.py`) and a diff handler in `PATCH /projects/{id}`
   (`api/projects.py`): insert newly-checked apps (`included=true`), remove unchecked, update notes; **validate every
   id is an onboarded `App`** (reject otherwise); `audit.emit`. Add **`impact_note TEXT NULL`** to `project_apps`
   (optional field — lets the user state *how* each selected app is impacted, e.g. "PayHub: add SMS channel"; richer
   grounding, safe to leave blank). Migration: fold into `0015` (or a small `0016`).
2. **Rich context helper** — new `backend/app/services/artifacts/app_context.py::gather_impacted_apps_context(
   project_id, db)` returning one formatted block per impacted app: **identity** (name, tier, domain_area, version,
   environments, description, **impact_note**) + **facts grouped by kind** (capability/constraint/limitation/
   integration/gotcha via `load_app_facts_for_project`) + **key wiki concepts** (via `gather_app_brain_context`,
   budgeted). Passed to **every** artifact DSPy unit as the `impacted_apps` input (supersedes the plain `app_facts`
   input in E4a §5).
3. **Frontend** — extract the wizard's app-select UI into a shared `AppScopePicker` component: a checkbox list of
   registry apps (suggested first, then a searchable list of all onboarded apps) — **selection only, no free-text
   app names** — with an *optional* impact-note input that appears under each *checked* app. Reuse it in both
   `app/projects/new/page.tsx` and `EditProjectModal.tsx`. Add a read-only **"Impacted applications"** context
   panel in the artifact builder (links to edit scope; hint "regenerate to incorporate" when scope changed).

**Behavior:** changing app scope affects grounding for the **next** (re)generation only; validated/locked rows are
untouched.

---

## Source material — upload → markdown → per-artifact selection

The concept-brief skill's recommended inputs are exactly meeting notes / transcripts / exec summaries / strategy
docs. **Three of four pieces already exist — reuse:**
- **Upload** (project-scoped): `api/documents.py::upload_document` + `Document` model (PDF/DOCX/XLSX/PPTX/MD/TXT,
  size-limited, SHA-256 dedup, synchronous text extraction).
- **Markdown**: `services/markdown_converter/service.py::MarkdownConverterService` (Azure / mock), cached in
  `document_markdown` (`DocumentMarkdown`) by source_hash.
- **Indexing/grounding**: `workers/tasks.py::ingest_project_source` → PageIndex `DocumentTree`;
  `understanding/orchestrator.py::_retrieve_project_sections` does `tree_search` over the project's trees. The
  artifact units already consume this as `source_sections`.
- **Frontend**: `components/{UploadPanel,DocumentList}.tsx` (mounted in the project workspace).

**Delta to build (per-artifact source curation — the only gap):**
1. **`artifact_sources` join table** — `id, artifact_document_id→artifact_documents(CASCADE),
   source_document_id→documents(CASCADE), included BOOL default true, created_at`; `UNIQUE(artifact_document_id,
   source_document_id)`. On `_ensure_document`, seed rows for the project's currently-indexed docs (included=true);
   docs uploaded later are added included=true. The user toggles inclusion per brief (Concept Brief and BRD can
   curate different sets).
2. **Parameterize retrieval** — `_retrieve_project_sections(project_id, query, top_k, db, document_ids=None)`
   filters `DocumentTree.document_id IN document_ids` (default `None` = all → preserves RU/spec behavior). The
   artifact orchestrator passes the brief's **included** source doc ids.
3. **Builder "Source material" panel** — reuse `UploadPanel` (uploads to the project + triggers
   `ingest_project_source`) + a checkbox `DocumentList` showing each doc's `indexing_status` (only `done` docs
   ground; others show "indexing…"); selection persists to `artifact_sources`. Optional: "view as markdown" per doc
   from `DocumentMarkdown`.

**Behavior:** selection affects the **next** (re)generation only; validated/locked rows untouched. With no docs (or
all deselected) the brief still generates from project name/description/business-unit + impacted apps + Q&A.

---

## Backend

### Data model — concrete typed tables (one per sub-artifact)
**No generic blob, no `content_json` for row content, no hashing.** Each sub-artifact is a plain typed table whose
columns come straight from the template — mirroring the existing normalized-row pattern (`models/requirement.py`
`ExtractedRequirement`, `models/gap.py` `GapQuestion`, `models/project_intake.py` `Assumption`). Models in
`backend/app/models/artifact.py` (register all in `models/__init__.py`).

**Shared versioning columns — `VersionedRowMixin`** (every row table includes these; keeps the ~30 tables DRY and
the versioning behaviour uniform):
`id (uuid pk) · document_id→artifact_documents(CASCADE) · row_key TEXT (stable logical-row id) · version INT ·
is_current BOOL · is_locked BOOL · status (active|removed) · source (ai|human|regeneration) · created_by→users
(SET NULL) · created_at`. Per table: `UNIQUE(document_id,row_key,version)`, partial `UNIQUE(document_id,row_key)
WHERE is_current`, index `(document_id) WHERE is_current`. Each concrete table = `VersionedRowMixin` + its own
**typed content columns**.

**Container + transcript (shared, concrete):**
- `artifact_documents` — one per (project, type): `id, project_id→projects(CASCADE), artifact_type
  (concept_brief|brd), status (in_interview|validated), unit_status JSONB (per-unit completeness/confidence — UI
  metadata only, not versioned content), validated_at, validated_by→users(SET NULL), validated_snapshot_key TEXT,
  timestamps`. `UNIQUE(project_id, artifact_type)`.
- `artifact_messages` — Q&A transcript per document (mirrors `InterviewMessage`): `id, document_id→artifact_documents
  (CASCADE), project_id, role (ai|user|question|synthesis), content, citations JSONB, meta JSONB{unit,why}, seq,
  created_at`. idx `(document_id, seq)`.

**Concept Brief row tables** (each = mixin + typed columns):
`cb_text_blocks`(field_key, text) · `cb_context_map`(dimension, detail) · `cb_outcomes`(outcome, description) ·
`cb_metrics`(metric, description) · `cb_capabilities`(capability, description) ·
`cb_scope_items`(kind[in_scope|out_of_scope|assumption], text) · `cb_milestones`(milestone, target, description) ·
`cb_gate_criteria`(criterion, status, notes).

**BRD row tables** (~21, same mixin): `brd_text_blocks`(field_key,text) · `brd_drivers`(text) ·
`brd_problem_impact`(area,description,magnitude,evidence) · `brd_objectives`(row_key=Objective ID; statement,
category, priority, owner) · `brd_benefits` · `brd_stakeholders` · `brd_actors` · `brd_scope_items`(kind,text) ·
`brd_asis_steps` · `brd_tobe_steps` · `brd_business_requirements`(row_key=BR ID; title, description, objective_ids,
stakeholder_ids, priority, acceptance_criteria) · `brd_data_needs` · `brd_reporting` · `brd_assumptions` ·
`brd_dependencies` · `brd_constraints` · `brd_risks`(row_key=Risk ID; …) · `brd_issues` · `brd_phasing` ·
`brd_change_mgmt` · `brd_kpis` · `brd_open_questions` · `brd_decisions` · `brd_references` · `brd_glossary`. Columns
per table follow the template exactly.

**Validation pin** — reuse `VersionSnapshot` + `version_service.create_snapshot` (immutable;
`document_key=f"{artifact_type}:{project_id}"`); store the map `{ "table.row_key": version }` of all current rows
at validation in `changed_sections`; save key → `artifact_documents.validated_snapshot_key`. No new snapshot table.

### How a single row is tracked + versioned (concrete — this was the confusing part)
- **Identity** = `(table, document_id, row_key)`. `row_key` = the natural ID where the template has one
  (objectives, `BR-001`, risks); else a slug (context-map dimension, glossary term) or ordinal.
- **Current artifact** = `SELECT … WHERE document_id=? AND is_current AND status='active'`, per table.
- **One row's history** = `WHERE document_id=? AND row_key=? ORDER BY version`.
- **On (re)generate a unit**: for each output row, look up the current row by `row_key` and **compare the typed
  columns** (no hashing): unchanged → no-op; changed → insert `version+1` (`is_current=true`, flip the old row to
  false); new `row_key` → insert version 1; a stored current row absent from output → `status='removed'`;
  **locked rows are skipped** so human content is preserved.
- **Human edit** = insert the next version (`source=human`, `is_locked=true`, `is_current=true`) — that one row only.
- **Restore** = insert a new version copying a chosen historical one (`is_current=true`).
- **Reliable id matching**: every (re)generate call feeds the current rows *with their ids* to the DSPy unit and
  instructs it to keep ids stable for unchanged concepts and mint new ids only for genuinely new rows.

Worked example (`brd_objectives`, currently `OBJ-1/2/3` all v1, is_current; rerun returns reworded `OBJ-1`,
identical `OBJ-2`, new `OBJ-4`): `OBJ-1`→insert v2 (old v1 is_current=false), `OBJ-2`→no-op, `OBJ-3`→status=removed,
`OBJ-4`→insert v1. Only the changed row advances.

### Migration — `backend/alembic/versions/0015_artifact_documents.py` (down_revision `0014`)
Idempotent raw SQL (mirror `0014_ask_sessions.py`): enum guards (`artifact_type, artifact_status, row_status,
row_source, message_role`) via `DO $$ … EXCEPTION WHEN duplicate_object`. Create `artifact_documents`,
`artifact_messages`, then the ~30 typed row tables. Since the row tables share the mixin columns, build them from a
small Python list of `(table_name, [typed columns])` in the migration to stay DRY. `downgrade()` drops in reverse +
`DROP TYPE IF EXISTS`.

### DSPy modules — `backend/app/services/skills/dspy_artifacts.py`
Mirror `backend/app/services/skills/dspy_specs.py` (`_configure`→`fact_extractor/dspy_extractor.py::_configure_dspy`,
`_is_mock`, Pydantic models, Signature docstring=instruction, `dspy.ChainOfThought`, async `run_*` →
`mock_fixture`/`run_in_executor`). **One Signature+Module per generation unit** (focused, small). Inputs:
`project_name, business_unit, description, source_sections` (PageIndex), `app_facts, qa_pairs(tagged), upstream
(depends_on rows), current_rows(with ids), locked_rows`. Output: the unit's rows (`list[RowModel]`) or prose model
+ `open_questions` + per-unit `confidence/completeness`. The **row Pydantic models map 1:1 to each table's typed
columns**. Generic `run_unit(unit_key,…)` dispatches via the manifest; mock → `mock_fixture(f"artifact_{unit_key}")`.

### Orchestrator — `backend/app/services/artifacts/orchestrator.py`
A single generic versioning service over the mixin handles all tables (no per-table code, no `diff.py`/hashing —
typed-column comparison replaces it):
- `upsert_rows(table_model, document_id, output_rows, source)` — the find-current / compare-typed-columns /
  insert-version / flip-current / mark-removed / skip-locked logic, reused by every unit.
- `generate_unit(project, type, unit_key)` — gather grounding (`tree_search` + `load_app_facts_for_project`) +
  tagged Q&A + current/locked rows for the unit's table → run the DSPy unit → `upsert_rows`; append `synthesis` +
  `question` messages; update `artifact_documents.unit_status`; `audit.emit`; commit.
- `generate_all` (topological over manifest `depends_on`, parallelize independents);
  `incorporate_answer` (append `user` msg → re-run the answered question's unit + downstream dependents);
  `edit_row(table_model, row_id, fields, lock=True)`; `regenerate_unit`; `restore_row`; `unlock_row`;
  `validate` (run manifest `validate_checks` → pin `VersionSnapshot` → `status=validated`, set `validated_*`).

### API — `backend/app/api/artifacts.py` (mount in `main.py`, `prefix="/api"`)
`Depends(get_current_user)`, `ok()/err()`, rate-limited. Under `/api/projects/{project_id}/artifacts/{artifact_type}`:
- `GET …` (document + current rows grouped by section/unit + open questions + unit_status)
- `POST …/generate` (all units) · `POST …/units/{unit_key}/generate` · `POST …/answer` (`{answer, seq?}`)
  — BRD routes add `Depends(require_artifact_validated("concept_brief"))`
- `GET …/units/{unit_key}/rows/{row_key}/history`
- `PATCH …/rows/{table}/{row_id}` (edit one row → new version) · `POST …/rows/{table}/{row_id}/restore` ·
  `POST …/rows/{table}/{row_id}/unlock`
- `POST …/units/{unit_key}/regenerate` (`{directive?}`) · `POST …/validate` · `GET …/export/markdown`

**Gate**: add factory `require_artifact_validated(artifact_type)` in `backend/app/api/deps.py` (loads
`ArtifactDocument`, 409 if `validated_at IS NULL`). Do NOT reuse the single `project.ru_validated` boolean.
**Schemas** `backend/app/schemas/artifact.py`: per-table Read/Edit models + `ArtifactDocumentRead, ArtifactMessageRead,
RowEditIn, UnitRegenerateIn, RowRestoreIn, AnswerIn`.

### Markdown — `backend/app/services/export/artifact_markdown.py` (new; do not extend the spec exporter)
Manifest maps each table → section + order: render current rows of each table as the template's pipe tables, prose
from `*_text_blocks`, + YAML frontmatter. Full export = sections in `ordinal` order.

### Mock fixtures (keep `LLM_PROVIDER=mock` green)
`backend/app/services/llm/fixtures/artifact_<unit_key>.json` per unit (rows + open_questions + confidence,
top-level object), loaded by `run_unit`'s `_is_mock()` branch via `mock_fixtures.py::mock_fixture`.

---

## Frontend (Next.js 14 App Router + shadcn/ui)

### Where it lives — information architecture
Everything is **inside a project**, mirroring how the RU interview lives at `app/projects/[id]/interview`. Two pieces:
1. **Container card on the project workspace** (`app/projects/[id]/page.tsx`) — an **"SDLC Artifacts" pipeline
   card** (the placeholder/container): stages **Concept Brief → BRD → FRS** as status chips (Not started / In
   interview / Validated) with **gate locks** (BRD disabled until Concept Brief validated; FRS "coming soon").
   Each opens its builder. Reuses the existing `ru_validated` banner + `WorkflowSteps` pattern. No new global
   sidebar entry.
2. **Builder sub-routes** — `app/projects/[id]/artifacts/[type]/page.tsx` (`concept-brief` | `brd`), one guided
   Q&A workspace per artifact, **structurally cloned from the `/interview` page** (sub-routes, not workspace tabs).

### Reuse vs net-new
- **Reused wholesale** from `app/projects/[id]/interview/page.tsx`: `AppShell`, back-header + Validate button, the
  two-column grid (Q&A thread + composer), `Bubble`/`Field`/confidence-badge components, toasts, `Skeleton`,
  `EmptyState`; plus `ThreePanel`, `SpecEditor`+`useDebouncedSave` (prose), `VersionBadge`, `ProjectContext`
  version panel. API via `lib/api.ts`.
- **Net-new**: the right panel becomes an **editable, versioned tables→rows view** (the RU panel is read-only) —
  each row is a card with **Edit / History / Lock / Restore** + per-unit **Regenerate**; rows render from their
  real typed columns (clean structured forms); plus the workspace **container card** and **stage-gating** visuals.

### Wiring
- **Layout** (reuse `/interview` grid): Left = Q&A thread + composer (questions tagged to units). Right = sections
  → tables → rows; per-row Edit/History/Lock/Restore + per-unit Regenerate + completion badge. Header = back +
  per-artifact Validate (runs SKILL.md checklist; shows gate state).
- **Row history**: `ProjectContext` version panel (key `artifact-row:{table}:{rowId}`) / drawer (timeline + diff +
  restore).
- **Client**: `api.artifacts` in `lib/api.ts`, types in `lib/types.ts`, hook `lib/hooks/useArtifact.ts` (mirror
  `useUnderstanding`); mutate after generate/answer/edit.

---

## Critical files
**New (backend):** `models/artifact.py` (mixin + ~30 typed tables), `alembic/versions/0015_artifact_documents.py`,
`services/skills/dspy_artifacts.py`, `services/artifacts/{manifest/concept_brief.py,manifest/brd.py,orchestrator.py,
app_context.py}` (impacted-apps context helper), `api/artifacts.py`, `schemas/artifact.py`,
`services/export/artifact_markdown.py`, `services/llm/fixtures/artifact_<unit>.json`.
**Modified (backend):** `models/__init__.py` (register models), `api/deps.py` (gate factory), `main.py` (mount);
**impacted-apps**: `models/project_intake.py` (+`impact_note`), `schemas/project.py` (`ProjectUpdate.app_ids`+notes),
`api/projects.py` (PATCH app-scope diff); **source-material**: `artifact_sources` table (in `models/artifact.py` +
migration `0015`), `services/understanding/orchestrator.py::_retrieve_project_sections` (add `document_ids` filter).
**New (frontend):** `app/projects/[id]/artifacts/[type]/page.tsx` + row/editor/history components,
`lib/hooks/useArtifact.ts`, `components/AppScopePicker.tsx` (shared app-select, extracted from the wizard).
**Modified:** `lib/api.ts`, `lib/types.ts`, `app/projects/[id]/page.tsx` (SDLC Artifacts container card + gating),
`components/EditProjectModal.tsx` (impacted-apps editor), `app/projects/new/page.tsx` (use `AppScopePicker`),
`components/DocumentList.tsx` (source-select checkbox mode; `UploadPanel` reused in the builder's Source panel).

## Reuse map (do not reinvent)
- DSPy config `services/skills/fact_extractor/dspy_extractor.py::_configure_dspy`.
- Grounding `services/understanding/orchestrator.py::_retrieve_project_sections` (PageIndex `tree_search`).
- Impacted-apps: `models/project_intake.py::ProjectApp`, `services/projects/discovery_service.py::suggest_apps`
  (+ `api/apps.py` suggest endpoint), `services/projects/app_context.py::load_app_facts_for_project`,
  `services/rag/wiki_grounding.py::gather_app_brain_context` — the new `gather_impacted_apps_context` composes these.
- Source material: `api/documents.py::upload_document` + `Document`, `services/markdown_converter/service.py` +
  `DocumentMarkdown`, `workers/tasks.py::ingest_project_source` + `DocumentTree`, FE `UploadPanel`/`DocumentList`.
- Versioning pin `services/version_service.py::create_snapshot` + `VersionSnapshot`.
- Audit `core/audit.py::emit`; envelope `schemas/envelope.py::ok/err`; mock `services/skills/mock_fixtures.py`.
- Normalized-row precedent: `ExtractedRequirement` / `GapQuestion` / `Assumption` (the typed-table pattern we copy).
- Frontend: `ThreePanel`, `SpecEditor`, `useDebouncedSave`, `VersionBadge`, interview thread, `lib/api.ts`.

## Verification
1. `make migrate`; `alembic downgrade -1` → `upgrade head` round-trips (all ~30 tables + enums).
2. Backend mock pytest (unique ids; real PG/Redis, mock LLM):
   - `generate_all` → version-1 rows in every table, in dependency order.
   - Rerun a unit with no new info → **no** new versions (typed-column compare).
   - `edit_row` → version 2 on that one row + `is_locked`; re-running its unit does NOT overwrite it; a dropped
     row → `status=removed` (history kept).
   - `regenerate_unit` / `restore_row` append exactly one version to the right row.
   - `validate` runs checklist + pins `VersionSnapshot`; BRD generate is **409** until Concept Brief validated;
     `export/markdown` renders template tables.
   - `make typecheck && make lint && make test-be` green.
3. E2E UI (`make dev-be`+`make dev-fe`, `admin@specforge.test`): project → SDLC Artifacts card → Concept Brief
   Q&A → answer (only tagged unit re-runs) → edit one row (verify lock) → row history + restore → validate →
   BRD unlocks → generate BRD → export.

## Risks
- **~30 tables** — mitigated by `VersionedRowMixin` + a loop-built migration + one generic `upsert_rows` service
  (no per-table boilerplate). The win: typed columns, trivial queries, no untyped JSON, no hashing.
- **Row identity for keyless tables** (scope bullets, glossary) by slug/ordinal → a reorder reads as a change
  (acceptable/auditable). Natural-id tables (objectives/BRs/risks) are stable.
- **Coherence** across separate small calls: dependency-ordered generation + the validate checklist (orphan BRs /
  untraced objectives).
- **Latency**: more, smaller calls — parallelize independent units; total tokens typically lower than one-shot. If
  a full `generate_all` is slow, dispatch via `workers/dispatch.py` (`_run_async()` + `engine.dispose()`).
- **FRS deferred** by design; the mixin/typed-table model extends to it directly.
