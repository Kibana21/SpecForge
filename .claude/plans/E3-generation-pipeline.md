# E3 — Full SDLC Generation Pipeline (Workstream 1)

## Context

A validated Requirement Understanding (RU) unblocks generating **functional / technical / user-stories / review** specs. The workspace shows a 10-stage SDLC map, but **6 of the 10 stages are dead placeholders** (always "not_started"), and the stage map the user sees is a **static, hardcoded list in `AppShell` that is never connected to the real `stage_progress` the backend already computes**. This workstream makes the pipeline real and the progress visible.

**Confirmed decisions:**
- **Build all 6 placeholder stages:** BRD, NFR, Data Model, API Design, Test Plan, Operations Guide → a fully-real 10-stage map.
- **Per-stage generation:** a data-driven **Stage Map** is the control surface — each stage shows status + its own Generate/Regenerate button (not one slow "generate everything" button). Better for real-Vertex latency + stage dependencies.

## Existing machinery to reuse (verified)
- **Spec generation:** `app/api/specs.py` — sync endpoints gated by `require_ru_validated`; `_skill_engine.run(skill, ctx, provider)`; `_allocate_and_create_spec()` (row-lock + version_number + markdown render). Skills at `app/services/skills/<name>/{instruction,template,schema}`; mock fixtures in `app/services/llm/fixtures/` + `MockProvider._SKILL_FIXTURE_MAP`.
- **`SpecType` Postgres ENUM** in `app/models/spec.py` (`functional, technical, user_stories, review`); enum-create pattern `DO $$ … EXCEPTION WHEN duplicate_object`; migrations through **0008** → next is **0009**.
- **Stage map:** `app/services/quality/quality_service.py` — `STAGES` (10 keys incl. brd/nfr/data_model/api_design/test_plan/operations) + `_SPEC_STAGE` (spec_type→stage). `compute_stage_progress` marks a stage "done" when its spec exists. Returned by `GET /api/projects/{id}` as `stage_progress` (type `StageProgress`) — **computed but never rendered**.
- **Frontend spec UI:** `OutputTabs.tsx` (hardcoded TABS), `SpecEditor.tsx` (Tiptap markdown + autosave), `GenerateSpecsButton.tsx` (hardcoded STEPS), `api.specs.*`, `SpecType` union; workspace `app/projects/[id]/page.tsx` is a `ThreePanel`. `AppShell.tsx` has a static `SDLC_STAGES` list (all `done:false`).

## Stage dependency graph (skill input context)
| spec_type | stage key | depends on |
|---|---|---|
| brd | brd | RU + extracted_requirements |
| functional | functional_spec | (existing) |
| nfr | nfr | functional_spec + non-functional requirements |
| technical | technical_spec | (existing) |
| user_stories | user_stories | (existing) |
| data_model | data_model | functional_spec + technical_spec |
| api_design | api_design | functional_spec + technical_spec + data_model |
| test_plan | test_plan | functional_spec + user_stories |
| operations | operations | technical_spec + nfr (+ api_design if present) |

## 1A. Data + skills (backend)
- **Migration `0009`** — `ALTER TYPE spec_type ADD VALUE IF NOT EXISTS '<x>'` for brd/nfr/data_model/api_design/test_plan/operations (PG12+; values added, not used in-tx → transaction-safe). Update the `SpecType` enum tuple in `app/models/spec.py`.
- **6 new skills** under `app/services/skills/<spec_type>/` (instruction.md + template.md + schema.json), modeled on `functional_spec`. Sample schemas: nfr → `{categories:[{name, requirements:[{id, statement, metric, priority}]}]}`; data_model → `{entities:[{name, fields:[…], relationships:[…]}]}`; api_design → `{endpoints:[{method, path, request, response, auth}]}`; test_plan → `{suites:[{area, cases:[{id, steps, expected}]}]}`; brd → `{business_goals, stakeholders, success_metrics, scope}`; operations → `{runbook, monitoring, slos, rollback}`.
- **6 mock fixtures** in `app/services/llm/fixtures/<spec_type>.json` + register in `_SKILL_FIXTURE_MAP`.

## 1B. Generation service + endpoints (backend, DRY)
- **`app/services/specs/registry.py`** — `SPEC_DEFS: dict[spec_type → {skill, requires:[spec_types], build_context(project, reqs, prereqs)}]` for all 9 generatable types. Single source of truth.
- **`app/services/specs/generation.py`** — `generate_spec(project_id, spec_type, db, provider) -> SpecVersion`: validate type, check prereqs (422 if missing), build context, `_skill_engine.run`, `_allocate_and_create_spec`. Refactor existing functional/technical/user_stories endpoints to delegate here.
- **Generic endpoint** `POST /api/projects/{project_id}/specs/{spec_type}` (gated by `require_ru_validated`, rate-limited) → `generate_spec`. Stage map calls this for every stage; keep named endpoints as thin delegators. (`review` keeps its own ReviewComments flow.)
- **Extend** `quality_service._SPEC_STAGE` to map all 9 spec_types → stage keys; extend markdown-export `valid_types`.

## 1C. Data-driven Stage Map (frontend)
- **`lib/specs.ts`** — `SPEC_REGISTRY` mirroring backend (spec_type → {label, stageKey, requires}) + stage order.
- **`lib/types.ts`** — extend `SpecType` with the 6 new values.
- **`StageMap` component** (`app/components/StageMap.tsx`) — renders the 10 `stage_progress` entries (status icon + label + progress); each generatable stage has a **Generate/Regenerate** button (`api.specs.generate(type)`, disabled if prereqs unmet or RU not validated, tooltip); click selects the stage. Becomes the workspace **left rail** (replaces static `WorkflowSteps`).
- **Workspace restructure** (`app/projects/[id]/page.tsx`) — left = `StageMap` (+ Documents), center = selected stage's `SpecEditor` (or gaps/review), right = context. Replaces horizontal `OutputTabs` (doesn't scale to 10). Keep gaps + review reachable; "Generate all remaining" runs not-done stages in dependency order.
- **AppShell sidebar SDLC list** — data-driven from the current project's `stage_progress` on project routes (via `ProjectContext`); generic elsewhere.

## 1D. Tests (backend)
`tests/test_spec_pipeline.py`: with mock provider, generate each new spec type (prereqs satisfied) → 200 + SpecVersion; missing prereq → 422; gate still 409 pre-validation; `stage_progress` flips each stage "done"; export includes new types.

## Files
**Create:** `alembic/versions/0009_*.py`; `app/services/skills/{brd,nfr,data_model,api_design,test_plan,operations}/*`; `app/services/llm/fixtures/{…6}.json`; `app/services/specs/{registry,generation}.py`; `frontend/lib/specs.ts`; `frontend/app/components/StageMap.tsx`; `tests/test_spec_pipeline.py`.
**Modify:** `app/models/spec.py`, `app/api/specs.py`, `app/services/quality/quality_service.py`, `app/services/llm/mock_provider.py`, `frontend/lib/types.ts`, `frontend/lib/api.ts`, `frontend/app/projects/[id]/page.tsx`, `frontend/app/components/{OutputTabs,GenerateSpecsButton,AppShell}.tsx`.

## Risks / notes
- **ENUM `ADD VALUE`** assumes PG12+ (transaction-safe; value not used in-migration). If PG<12, switch to enum-recreate.
- **6 new skills' real-Vertex quality** unproven; CI/tests use deterministic mock fixtures (no Vertex). Validate real output manually post-merge.
- **Workspace restructure** (OutputTabs→StageMap rail) is the largest single change — keep gaps/review reachable; verify in browser.
- Generation stays **sync per-request** (one LLM call each); the stage map drives one request per stage → no long chains. Mock path stays instant for CI.

## Verification
1. `make migrate` → `make dev-be`/`dev-fe`; `scripts/seed_projects.py` (validated-RU project, mock).
2. `cd backend && ./.venv/bin/python -m pytest tests/test_spec_pipeline.py -q` then full suite.
3. UI (login `admin@specforge.test`): open a validated project → Stage Map shows 10 stages; **Generate** each new deliverable per-stage → status flips to done, spec renders + editable; pre-validation the stages are gate-locked.
