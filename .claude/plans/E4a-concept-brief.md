# E4a — Concept Brief module (detailed implementation plan)

> First module of **E4 SDLC Artifacts** (see `E4-sdlc-artifacts.md` for the umbrella + shared infra/decisions).
> Concrete typed tables, per-sub-artifact DSPy modules, row-level versioning, guided Q&A, validation gate.
> Source of truth for structure: `reference_mds/skills/concept-brief-builder/{concept-brief-template.md, SKILL.md}`.
>
> **Run THIS file** (build order §11). It is self-contained for Concept Brief and creates the **shared foundation**
> (`artifact_documents`/`artifact_messages`/`artifact_sources` + `VersionedRowMixin`, the generic orchestrator +
> `upsert_rows`, the generic artifact API router, `gather_impacted_apps_context`, impacted-apps create/edit, the
> source-material wiring, and the `require_artifact_validated` gate) that BRD/FRS will later reuse. **E4 is reference
> only** — nothing in it needs separate work for Concept Brief except the deferred `brd_*`/`frs_*` tables + manifests.

## 1. Goal & scope

Let a non-technical business user produce a **Concept Brief** (Stage 0 ideation) inside SpecForge, attached to a
`Project`, via a guided Q&A interview. DSPy generates each sub-artifact; **every row is stored in a concrete typed
table and individually versioned**; a human **validation gate** marks it ready (and later unlocks the BRD).

In scope (this file): Concept Brief end-to-end (data model, DSPy units, orchestrator/versioning, Q&A, gate, API,
markdown export, frontend builder + workspace entry, mock-first tests).
Out of scope: BRD/FRS (later E4b/E4c); they reuse the shared infra built here.

## 2. The Concept Brief structure (from the template) → units & tables

The template = YAML frontmatter + Document Control table + 6 sections:

| # | Section | Content | Generation unit | Table(s) |
|---|---------|---------|-----------------|----------|
| 1 | Problem Statement & Context Map | Business Context (prose), Problem Statement (prose), Context Map (6-row table) | `problem_context` | `cb_text_blocks`, `cb_context_map` |
| 2 | Value Hypothesis & Expected Outcomes | "If…/then…" (prose), Expected Outcomes (table 3–6), Success Metrics (table ≥1 quantifiable) | `value_hypothesis` (prose+outcomes), `metrics` | `cb_text_blocks`, `cb_outcomes`, `cb_metrics` |
| 3 | Proposed Capabilities | Capability table | `capabilities` | `cb_capabilities` |
| 4 | Scope Boundaries & Assumptions | In/Out scope + Assumptions (3 lists) | `scope` | `cb_scope_items` |
| 5 | Delivery Approach | Milestone table | `milestones` | `cb_milestones` |
| 6 | Approval Gate | Gate criteria table (clarity ≥90%, go/no-go) | `gate` (computed, not DSPy) | `cb_gate_criteria` |

**Frontmatter + Document Control** are NOT LLM units — generated at export time from project + version data
(§9): `title/description/artefactId/artefactType/generatorSkill/generatedAt` from the document; Document Control
(Version/Date/Author/Summary/Approved By) from the `VersionSnapshot`/audit history.

Context Map has 6 **fixed** dimensions (stable `row_key`s): `business_unit, new_channel, customer_segments,
current_gap, strategic_driver, engagement_goal`. Gate has 2 fixed criteria: `clarity`, `go_no_go`.

## 3. Data model (concrete typed tables)

New file `backend/app/models/artifact.py`; register every model in `backend/app/models/__init__.py`. Uses
`uuid_pk()`/`TimestampMixin` from `models/base.py`. Mirrors the existing typed-row pattern (`ExtractedRequirement`).

### 3.1 Shared (built here, reused by BRD/FRS)
- **`artifact_documents`** — one per (project, type): `id, project_id→projects(CASCADE), artifact_type
  (enum: concept_brief|brd), status (enum: in_interview|validated), unit_status JSONB (per-unit
  {completeness:int, confidence:str} — UI metadata only, NOT versioned content), validated_at TIMESTAMPTZ,
  validated_by→users(SET NULL), validated_snapshot_key TEXT, created_at, updated_at`.
  `UNIQUE(project_id, artifact_type)`, idx `(project_id)`.
- **`artifact_messages`** — Q&A transcript (mirrors `InterviewMessage`): `id, document_id→artifact_documents
  (CASCADE), project_id→projects(CASCADE), role (enum: ai|user|question|synthesis), content TEXT, citations JSONB
  default [], meta JSONB default {} ({unit_key, field, why} for questions), seq INT, created_at`.
  idx `(document_id, seq)`.
- **`artifact_sources`** — which uploaded project documents are curated as material for THIS brief (see E4
  "Source material"): `id, artifact_document_id→artifact_documents(CASCADE), source_document_id→documents(CASCADE),
  included BOOL default true, created_at`; `UNIQUE(artifact_document_id, source_document_id)`. Seeded on
  `_ensure_document` from the project's indexed docs; user toggles in the builder Source panel.

### 3.2 `VersionedRowMixin` (every cb_* table includes it)
`id (uuid pk) · document_id→artifact_documents(CASCADE) · row_key TEXT · version INT · is_current BOOL default
true · is_locked BOOL default false · status (enum: active|removed) default active · source (enum:
ai|human|regeneration) · created_by→users(SET NULL) · created_at`.
Per-table constraints: `UNIQUE(document_id, row_key, version)`, partial `UNIQUE(document_id, row_key) WHERE
is_current`, idx `(document_id) WHERE is_current`, `CHECK(version > 0)`.

### 3.3 Concept Brief tables (mixin + typed columns)
| Table | Typed columns | `row_key` |
|-------|---------------|-----------|
| `cb_text_blocks` | `field_key TEXT, text TEXT` | field_key (business_context, problem_statement, value_hypothesis_if, value_hypothesis_then) |
| `cb_context_map` | `dimension TEXT, detail TEXT` | the 6 fixed dimension slugs |
| `cb_outcomes` | `outcome TEXT, description TEXT` | ordinal slug `o-1…` |
| `cb_metrics` | `metric TEXT, description TEXT, quantifiable BOOL` | ordinal slug `m-1…` |
| `cb_capabilities` | `capability TEXT, description TEXT` | ordinal slug `cap-1…` |
| `cb_scope_items` | `kind TEXT (in_scope\|out_of_scope\|assumption), text TEXT` | `{kind}-{n}` |
| `cb_milestones` | `milestone TEXT, target TEXT, description TEXT` | ordinal slug `ms-1…` |
| `cb_gate_criteria` | `criterion TEXT, status TEXT, notes TEXT` | `clarity`, `go_no_go` |

### 3.4 Migration `backend/alembic/versions/0015_artifact_documents.py` (down_revision `0014`)
Idempotent raw SQL (mirror `0014_ask_sessions.py`). Order: enum guards (`artifact_type, artifact_status,
artifact_row_status, artifact_row_source, artifact_message_role`) via `DO $$ … EXCEPTION WHEN duplicate_object`;
`CREATE TABLE IF NOT EXISTS artifact_documents`, `artifact_messages`; then the 8 `cb_*` tables built from a small
`(name, [content-column DDL])` Python list + the shared mixin columns to stay DRY. `downgrade()` drops in reverse,
`DROP TYPE IF EXISTS`. (BRD tables come in a later migration.)

## 4. Generation units & dependency DAG

Manifest `backend/app/services/artifacts/manifest/concept_brief.py` — ordered list of units. DSPy units
(6) + 1 computed:

1. `problem_context` — writes `cb_text_blocks[business_context, problem_statement]` + `cb_context_map` (6 rows). depends_on: [].
2. `value_hypothesis` — writes `cb_text_blocks[value_hypothesis_if, value_hypothesis_then]` + `cb_outcomes`. depends_on: [problem_context].
3. `metrics` — writes `cb_metrics` (must yield ≥1 `quantifiable=true`). depends_on: [value_hypothesis].
4. `capabilities` — writes `cb_capabilities`. depends_on: [problem_context, value_hypothesis].
5. `scope` — writes `cb_scope_items` (in/out/assumptions). depends_on: [capabilities, value_hypothesis].
6. `milestones` — writes `cb_milestones`. depends_on: [capabilities, scope].
7. `gate` — **computed** at validate/refresh (no LLM): `clarity` status from `unit_status` completeness
   (Pass ≥90 / Partial 60–89 / Fail <60), `go_no_go` = Pending until human validates → Approved.

Each manifest entry carries: `unit_key, writes (tables/fields), depends_on, unit_instruction` (the section's
template `[G]` guidance, condensed), and the SKILL.md `discover_questions` for that area (§6).

## 5. DSPy modules — `backend/app/services/skills/dspy_artifacts.py`

Mirror `backend/app/services/skills/dspy_specs.py`: module-level `_configure()`→`fact_extractor/dspy_extractor.py::
_configure_dspy`, `_is_mock()`, Pydantic models, `dspy.Signature` (docstring = `unit_instruction`),
`dspy.Module(dspy.ChainOfThought)`, async `run_unit(unit_key, **inputs)` → `mock_fixture(f"artifact_{unit_key}")`
on mock else `loop.run_in_executor(None, Module(), …)`.

**Row Pydantic models map 1:1 to table columns**, e.g.:
```
class ContextMapRow(BaseModel): dimension: str; detail: str
class OutcomeRow(BaseModel): outcome: str; description: str
class MetricRow(BaseModel): metric: str; description: str; quantifiable: bool
class CapabilityRow(BaseModel): capability: str; description: str
class ScopeItemRow(BaseModel): kind: Literal["in_scope","out_of_scope","assumption"]; text: str
class MilestoneRow(BaseModel): milestone: str; target: str; description: str
class OpenQuestion(BaseModel): question: str; field: str; why: str
```
**Per-unit Signature** — inputs (only what the unit needs): `project_name, business_unit, description,
source_sections` (PageIndex retrieval over the brief's **selected** source documents — see §10.4 / E4 "Source
material"), **`impacted_apps`** (rich impacted-applications context from
`services/artifacts/app_context.py::gather_impacted_apps_context` — per-app identity + tier/domain + per-app
`impact_note` + facts grouped by capability/constraint/limitation/integration/gotcha + key wiki concepts; see E4
"Impacted Applications"), `qa_pairs` (transcript filtered to this unit), `upstream` (JSON of depends_on units'
current rows), `current_rows` (this unit's current rows, WITH row_keys), `locked_rows`. Outputs: the unit's row list(s) (e.g. `outcomes: list[OutcomeRow]`) + `open_questions:
list[OpenQuestion]` + `completeness: int (0-100)` + `confidence: Literal["high","medium","low"]`.
Docstring instructs: solution-agnostic, ground in `[S#]/[F#]` **and in the impacted applications** (anchor
capabilities/scope/risks/integrations to those apps and respect their documented constraints/limitations),
reproduce `locked_rows` verbatim, **keep existing row_keys stable; mint new keys only for new rows**, ≥1
quantifiable metric (metrics unit), Context Map uses the 6 fixed dimensions (its `new_channel` /
`current_gap` / `strategic_driver` should reflect the impacted apps + their `impact_note`).

Mock fixtures (object top-level): `backend/app/services/llm/fixtures/artifact_{problem_context,value_hypothesis,
metrics,capabilities,scope,milestones}.json` — full valid rows + open_questions + completeness/confidence.

## 6. Q&A interview flow (from SKILL.md)

SKILL.md Discover groups (seed `discover_questions` per unit): 🎯 Initiative Context (name, business problem,
driver), 🏢 Business Context (owning unit, customers, as-is), 💡 Value & Outcomes (value, success outcomes, KPIs),
📦 Scope & Assumptions (in/out, assumptions), 🚀 Delivery (milestones, MVP/phasing).

Flow (per SKILL.md "synthesise from inputs before asking"):
1. **First open** — `_ensure_document` creates the `artifact_documents` row (status=in_interview). If project has
   grounding (description + uploaded sources via PageIndex + app facts) → run `generate_all` to produce a first
   draft; each unit emits `open_questions`. If grounding is sparse, also seed the SKILL.md Discover questions as
   `question` messages so the user has somewhere to start.
2. **Answer** (`incorporate_answer`) — append the `user` message; re-run the unit the answered question is tagged
   to (via `meta.unit_key`) **plus its downstream dependents**; new `open_questions`/`synthesis` messages appended.
3. **Refine** — user can also edit any row directly, regenerate a unit, or restore a prior row version.
4. **Validate** — run the checklist (§7); on pass + human go → status=validated.

Transcript rendered like the RU interview (`question` vs `user` bubbles, citations chips).

## 7. Orchestrator, versioning & validation — `backend/app/services/artifacts/orchestrator.py`

**Generic versioning service** (one function, all tables — no per-table code, no hashing):
`upsert_rows(table_model, document_id, output_rows, source, user_id=None)`:
- For each output row, look up current by `(document_id, row_key)`.
  - none → insert `version=1, is_current=true`.
  - exists, `is_locked` → **skip** (preserve human content).
  - exists, typed content columns **differ** → insert `version+1, is_current=true`; set previous `is_current=false`.
  - exists, identical → no-op.
- Any current row whose `row_key` is absent from `output_rows` → set `status='removed'` (keep history).

**Functions:**
- `_ensure_document(project_id, type, db)` — get-or-create `artifact_documents`.
- `generate_unit(project, unit_key, db)` — gather grounding: `_retrieve_project_sections(..., document_ids=<the
  brief's included `artifact_sources`>)` (curated docs only) + `gather_impacted_apps_context` + tagged `qa_pairs` +
  `upstream`/`current`/`locked` rows → `run_unit` →
  `upsert_rows` per written table → append `synthesis` + one `question` msg per open_question (meta.unit_key) →
  update `artifact_documents.unit_status[unit_key]` → `audit.emit("artifact.unit_generated")` → commit.
- `generate_all(project, type, db)` — topological over manifest `depends_on`; independents may run concurrently.
- `incorporate_answer(project_id, type, answer, db, seq=None)` — append `user` msg; re-run answered unit +
  downstream dependents.
- `edit_row(table_model, row_id, fields, db, user_id, lock=True)` — validate vs row model; `upsert`-style insert
  next version (`source=human`, `is_locked=lock`).
- `regenerate_unit(project, unit_key, directive, db)` — re-run one unit (`source=regeneration`); no auto-lock.
- `restore_row(table_model, document_id, row_key, version, db, user_id)` — insert new version copying the chosen one.
- `unlock_row(table_model, row_id, db)`.
- `refresh_gate(document, db)` — recompute `cb_gate_criteria[clarity]` from `unit_status`; keep `go_no_go=Pending`.
- `validate(project_id, type, db, user_id)` — run §7.1 checklist; if pass: set `cb_gate_criteria[go_no_go]=Approved`,
  `status=validated`, `validated_at/by`; pin `VersionSnapshot` (`version_service.create_snapshot`, immutable,
  `changed_sections`={"table.row_key": version} of all current rows) → `validated_snapshot_key`;
  `audit.emit("artifact.validated")`.

### 7.1 Validation checklist (from SKILL.md) → checks
- problem_statement present & non-trivial · value_hypothesis_if & _then present (testable "If…then…") · ≥1
  `cb_metrics.quantifiable=true` · ≥1 capability · in_scope & out_of_scope each ≥1 · ≥1 assumption · ≥1 milestone
  · every unit `completeness ≥ 90` (→ clarity Pass) · (frontmatter/doc-control auto, always satisfiable).
Return per-check pass/fail; block validate (409 `err`) with the failing items if not all pass.

## 8. API — `backend/app/api/artifacts.py` (mount in `main.py`, `prefix="/api"`)

Router `dependencies=[Depends(get_current_user)]`, `ok()/err()` envelope, rate-limit generate/answer. Generic over
`artifact_type` (so BRD reuses it); for now `artifact_type` ∈ {`concept-brief`}.
- `GET /projects/{project_id}/artifacts/{artifact_type}` — `artifact_documents` + current rows grouped by
  section/unit + open questions (from messages) + unit_status.
- `POST …/generate` — `_ensure_document` + `generate_all`.
- `POST …/units/{unit_key}/generate` and `POST …/units/{unit_key}/regenerate` (`{directive?}`).
- `POST …/answer` (`{answer, seq?}`).
- `GET …/units/{unit_key}/rows/{row_key}/history`.
- `PATCH …/rows/{table}/{row_id}` (`{fields, lock?}`) · `POST …/rows/{table}/{row_id}/restore` (`{version}`) ·
  `POST …/rows/{table}/{row_id}/unlock`.
- `POST …/validate` · `GET …/export/markdown`.
`table` is whitelisted to the cb_* set (reject others → `err`). Schemas in `backend/app/schemas/artifact.py`
(`ArtifactDocumentRead, ArtifactMessageRead, CbRowRead` per table, `RowEditIn, UnitRegenerateIn, RowRestoreIn,
AnswerIn`). Gate factory `require_artifact_validated(artifact_type)` added to `backend/app/api/deps.py` (used by
BRD later; built now).

## 9. Markdown export — `backend/app/services/export/artifact_markdown.py` (new)

Reconstruct the template exactly: YAML frontmatter (title=`{project.name} – Concept Brief`, artefactType=
`concept-brief`, generatorSkill=`concept-brief-builder`, generatedAt=now, artefactId=`concept-{slug}`) + Document
Control table (rows from `VersionSnapshot` timeline for `concept_brief:{project_id}`) + the 6 sections rendered
from current rows (prose from `cb_text_blocks`, pipe tables from each cb_* table in template column order).
`GET …/export/markdown` returns `text/markdown` attachment (mirror `specs.py` export).

## 10. Frontend

### 10.1 Workspace container (entry point)
Edit `app/projects/[id]/page.tsx`: add an **"SDLC Artifacts"** card (reuse `.card`, `WorkflowSteps`/`ru_validated`
banner patterns) with a **Concept Brief** chip showing status (Not started / In interview / Validated) linking to
the builder; **BRD** chip disabled (locked until CB validated) with tooltip; **FRS** greyed "coming soon".

### 10.2 Builder route `app/projects/[id]/artifacts/[type]/page.tsx`
Clone `app/projects/[id]/interview/page.tsx`: `AppShell`, back-header + **Validate** button (shows checklist
failures on 409), two-column grid. **Left** = Q&A thread (`question`/`user`/`synthesis` bubbles + citations) +
composer (⌘/Ctrl+Enter). **Right** = the 6 sections; each table's rows rendered from typed columns; per-row
**Edit / History / Lock / Restore**, per-unit **Regenerate**, per-unit completeness/confidence badge (reuse
`CONF_VARIANT`). Prose blocks via `SpecEditor` + `useDebouncedSave`; table rows via small structured forms.
Row history via `ProjectContext` version panel (key `artifact-row:{table}:{rowId}`) or a drawer (timeline + diff +
restore). Empty state = "Generate Concept Brief".

**Impacted applications panel**: a read-only context strip in the builder listing the project's in-scope apps
(name, tier, `impact_note`) — what's grounding the brief — with an "Edit scope" link (opens `EditProjectModal`'s
impacted-apps editor) and a "scope changed since last generation → regenerate to incorporate" hint. App scope is
selected at project create/edit (see E4 "Impacted Applications"), not inside the builder.

### 10.4 Source material panel
A builder panel (header dropdown or left-rail section) for curating the brief's source docs (see E4 "Source
material"): reuse `UploadPanel` to add brief documents (uploads to the project → `ingest_project_source` builds the
PageIndex tree → markdown cached) + a checkbox `DocumentList` of the project's docs showing `indexing_status` (only
`done` docs ground; others show "indexing…"). Toggling persists to `artifact_sources`; newly uploaded docs default
to included. Optional "view as markdown" per doc (`DocumentMarkdown`). Grounding for (re)generation uses only the
**included** docs.

### 10.3 Client/types/hook
`api.artifacts` namespace in `lib/api.ts` (generate/regenerate/answer/get/editRow/restoreRow/unlockRow/validate/
exportUrl), types in `lib/types.ts` (mirror schemas), hook `lib/hooks/useArtifact.ts` (mirror `useUnderstanding`);
mutate after each mutation; toasts via sonner.

## 11. Build order (task checklist)
1. **Impacted-apps enabler (prereq, see E4):** `impact_note` column on `project_apps` (migration); `ProjectUpdate.app_ids`
   (+notes) in `schemas/project.py` + PATCH app-scope diff in `api/projects.py`; extract `components/AppScopePicker.tsx`
   from the wizard and wire it into `EditProjectModal.tsx` (+ keep `projects/new` using it).
2. `services/artifacts/app_context.py::gather_impacted_apps_context` (composes `load_app_facts_for_project` +
   `gather_app_brain_context` + app identity/`impact_note`).
3. `models/artifact.py` (shared `artifact_documents`/`artifact_messages`/**`artifact_sources`** + `VersionedRowMixin`
   + 8 cb_* tables) + register in `models/__init__.py`.
4. Migration `0015` (shared + `artifact_sources` + cb_* via DRY list + `impact_note`); `make migrate`; round-trip.
5. **Source-material wiring:** parameterize `understanding/orchestrator.py::_retrieve_project_sections` with
   `document_ids`; seed/read `artifact_sources` in the artifact orchestrator.
6. `services/artifacts/manifest/concept_brief.py` (units, depends_on, instructions, discover_questions, checklist).
7. `services/skills/dspy_artifacts.py` (6 unit modules + row models, `impacted_apps` input) + 6 mock fixtures.
8. `services/artifacts/orchestrator.py` (`upsert_rows` + all functions, grounding via included sources) +
   `require_artifact_validated` in `deps.py`.
9. `schemas/artifact.py` + `api/artifacts.py` (incl. `GET/PATCH …/sources`) + mount in `main.py`.
10. `services/export/artifact_markdown.py`.
11. Backend pytest (mock) — §12.
12. Frontend: `lib/api.ts`, `lib/types.ts`, `lib/hooks/useArtifact.ts`, builder page (+ impacted-apps panel +
    Source-material panel reusing `UploadPanel`/`DocumentList`), workspace card.
13. E2E verify; `make typecheck && make lint && make test-be`.

## 12. Verification
- **Migration** round-trips (8 cb_* + 3 shared tables incl. `artifact_sources` + enums).
- **Source material**: upload a doc to a project → it's indexed (mock corpus provider) and appears selectable;
  `artifact_sources` seeds included=true; deselecting a doc excludes it from `_retrieve_project_sections`
  (assert `document_ids` filter passes only included ids); generating with zero included docs still succeeds
  (grounds on project meta + impacted apps + Q&A).
- **Mock pytest** (`LLM_PROVIDER=mock`, unique ids, real PG/Redis): `generate_all` → version-1 rows across all cb_*
  tables in dependency order; Context Map has exactly 6 fixed dimensions; metrics include ≥1 quantifiable. Rerun a
  unit with no new info → **0 new versions** (typed-column compare). `edit_row` → version 2 on that row + locked;
  re-running its unit does NOT overwrite it. Drop a row across regen → `status=removed` (history kept).
  `restore_row` adds a version. `validate` blocks (409 + failing checks) when incomplete; passes when complete →
  status=validated + `VersionSnapshot` pinned. `export/markdown` reproduces the template (frontmatter + 6 sections).
- **Impacted-apps**: editing a project adds/removes apps + impact notes (`ProjectApp` rows + `impact_note` persist);
  `gather_impacted_apps_context` returns identity + facts + wiki for in-scope apps and "" when none; a generated
  Concept Brief grounded in an app reflects that app's capabilities/constraints (assert the impacted-app text/notes
  appear in the relevant unit's fixture-independent prompt inputs — covered via the mock by asserting the helper's
  output feeds the unit call).
- **E2E UI** (`make dev-be`+`make dev-fe`, `admin@specforge.test`): create/edit a project → pick impacted apps
  (+ impact notes) via `AppScopePicker` → open SDLC Artifacts card → Concept Brief → generate → builder shows the
  impacted-apps panel → answer a question (only the tagged unit + dependents re-run) → edit a capability row (verify
  lock + v2) → open its history + restore → validate → BRD chip unlocks.

## 13. Decisions / notes
- **Gate is computed, not LLM** (clarity from completeness, go/no-go from the human action) — deterministic.
- **Frontmatter + Document Control are export-time**, sourced from project + `VersionSnapshot` history (not units).
- **Keyless tables** (outcomes/metrics/capabilities/milestones/scope) key by ordinal slug → a pure reorder reads as
  a change (acceptable/auditable); fixed-key tables (context_map/gate) are stable.
- Heavy work stays in the request path like specs/understanding; if `generate_all` is slow, dispatch via
  `workers/dispatch.py` (`_run_async()` + `engine.dispose()`).
