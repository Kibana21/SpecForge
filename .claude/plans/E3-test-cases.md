# E3 — Test Cases Module: Detailed Implementation Plan

> **Canonical plan for the Test Cases module.** Source of truth: `.claude/prd/prd-e3-test-cases.md`.
> Conceptual seed: `reference_mds/skills/e2e-test-plan-builder/SKILL.md`.
> **This plan emphasizes three things:** (1) **Context Engineering** — the exact, full context that
> yields *brilliant* test cases; (2) **Outcome Richness** — a quality rubric + richer fields
> (`test_data`, `expected_observability`, `outcomes_summary`) + a "Testing Outcomes" rollup;
> (3) a deep **UI/UX** spec covering every state and interaction.

---

## Context

SpecForge produces a validated chain **Project → Concept Brief → BRD → FRS**. The FRS is the last artifact today: each validated FRS *spec* carries Gherkin acceptance scenarios, functional requirements (FRs), business rules, screens/UI components, endpoints, data entities, an independent-test narrative, data-and-validation rules, errors-and-edge-cases, and observability hooks. The missing link — the thing QA ships against — is a **traceable, AI-generated test suite** that proves the system satisfies the FRS, and transitively the BRD requirements the business cares about.

The `e2e-test-plan-builder` SKILL is the seed (one plan per FRS, every acceptance scenario → one case, a smoke test, responsive/navigation tests, a coverage matrix). We elevate it into a first-class, versioned, **traceable** module that mirrors the proven BRD/FRS engine end-to-end (row-level versioning, locking, idempotent regeneration, Celery dispatch, `unit_status` progress channel, mock-provider path).

**Confirmed decisions:** (1) **comprehensive multi-level** breadth — `test_type ∈ {functional, integration, e2e, negative, edge_case, responsive}`; (2) structure **Module → FRS spec → test cases**, framed by a module-level user-journey overview; (3) **authoring + coverage only** now (schema future-proofs a `test_runs` table); (4) generation **gated on FRS validated** (reuse `require_artifact_validated("frs")`).

**Intended outcome:** A QA architect opens the Test Cases workspace on a validated-FRS project, clicks Generate, watches a live per-module/per-spec theater, then lands in a Module→Spec→Cases builder where **every property is editable/deletable/lockable/versioned**, can **add a case and link it to any FRS FR/scenario/business-rule**, sees a **Coverage Galaxy** drawing the full Project→BRD→FRS→Test chain with untested *must*-BRs called out, and a **Testing Outcomes** panel summarizing *what the suite proves*.

---

## 0. Architecture at a glance

```
Validated FRS  ──gather_project_context(artifact_type="test_cases")──►  ProjectContextBundle
 (+ BRD, CB,                                                   {apps, docs, cb, brd, FRS(new FrsLayer), intake}
  App Brain,                                                                     │
  NFR)                                                                           ▼
        Stage A  plan_journeys (1 DSPy call)  ── test_suites (per module, journey + outcomes_summary)
                                                 + test_plan STUBS (per spec, coverage_targets)
                                                                                 │
        Stage B  author_plan (1 DSPy call PER FRS SPEC; modules parallel sem=3)  ── test_cases (+ rich fields)
                                                                                    + test_case_traceability
                                                                                 │
                       unit_status JSONB merge ──► frontend polling (live theater)
                                                                                 │
              validate() → status='validated' + lock rows      GET /coverage → Coverage Galaxy + Outcomes
```

Two DSPy stages mirror FRS (Stage A modularize → Stage B per-spec design). **Stage B is per-FRS-spec, not per-module** — a comprehensive plan is ~15–40 cases/spec and a per-module completion truncates on `gemini-2.5-flash` (the FRS team already learned this). Modules parallelize (semaphore=3); specs within a module run sequentially, committing after each so a late timeout never loses finished work.

---

## 1. Context Engineering — *what yields brilliant test cases* (the headline)

A test case is only as good as the context the generator sees. Generic context → generic "click button, see result" cases. **Brilliant** test cases are specific (real entity/field names, real value ranges), outcome-oriented (assert the business outcome, not just the click), edge-aware (boundary + error paths from the FRS), and observable (assert logs/metrics/audit events). To get there, the Stage B `author_plan` call receives a **fully-assembled per-spec context pack** — not just the spec text.

### 1.1 The per-spec context pack (`target_spec` + corpus layers)
Assembled by `tc_orchestrator` from the `FrsLayer` + BRD + CB + App Brain + NFR + project docs, then projected by `project_for_unit(..., "test_cases")`. Every element below is injected, and each maps to the test types it powers:

| Context element (source) | Powers `test_type` | What the generator must extract |
|---|---|---|
| **acceptance_scenarios** — G/W/T, `is_negative`, `fr_refs` (`frs_acceptance_scenarios`) | functional, negative | 1 functional case per positive scenario; ≥1 negative case per `is_negative` scenario; assertions in FRS language (exact labels/messages) |
| **functional_requirements** — `requirement_text`, `scenario_refs` (`frs_functional_requirements`) | functional, integration | a verification case asserting the FR behavior holds; cross-link to its scenarios |
| **independent_test** narrative (`frs_specs.independent_test`) | e2e (smoke) | the TC-001 system-boundary walkthrough — always first |
| **data_and_validation** (`frs_specs.data_and_validation`) | edge_case, negative | boundary values (min/max/empty/overflow), format violations, required-field omissions → `test_data` |
| **errors_and_edge_cases** (`frs_specs.errors_and_edge_cases`) | negative, edge_case | error-path assertions + recovery expectations |
| **business_rules** — `description`, `logic_decision`, `applies_to` (`frs_business_rules`) | functional, edge_case | rule-enforcement cases (rule satisfied / violated) |
| **screens** — `layout`, `navigation`, `interactive_behavior`, `user_roles` (`frs_screens`) | responsive, e2e | viewport tests at named breakpoints; navigation/anchor tests; role context |
| **ui_components** — `validation`, `behavior`, `actions` (`frs_ui_components`) | functional, edge_case, responsive | field-level validation cases, control behavior, disabled/enabled states |
| **endpoints** — `request_spec`, `response_spec`, `error_handling`, `security` (`frs_endpoints`) | integration, e2e | API-level assertions: status codes, response contract, auth required, error envelope |
| **data_entities** — `columns`, `keys_constraints`, `relationships` (`frs_data_entities`) | edge_case, integration | persistence assertions, constraint-violation cases (unique/FK/not-null) |
| **module_actors** — roles/personas (`frs_module_actors`) | all (sets `auth_role`, `auth_required`) | which persona runs the case; unauthorized-access negatives |
| **observability** (`frs_specs.observability`) | all (sets `expected_observability`) | which logs/metrics/traces/audit events the case must assert |
| **BRD** business_requirements (`must|should|could|wont`) + objectives + KPIs | all (outcome framing) | tie each assertion to the business outcome / KPI it protects; prioritize must-BR coverage |
| **NFR drivers** (FRS traceability `nfr_driver`) | edge_case, integration (perf/security flavor) | threshold assertions (latency, throughput, authz) where present |
| **App Brain facts** (`apps.formatted_context`) | all | real domain entity names, valid value ranges, true business constraints → specific, non-generic data |
| **project docs** (depth_search sections) | all | source language for assertions; flag gaps where docs are silent |

### 1.2 Context rules (enforced in the DSPy instruction + validator)
1. **Full-corpus, no partial coverage** (project rule): the spec's *entire* sub-row set + BRD + CB + App Brain is in context before authoring. The orchestrator blocks a spec if its FRS rows failed to load.
2. **Use FRS language verbatim** in assertions (exact field labels, error messages, values) — this is what makes coverage traceable and the case executable.
3. **Don't invent requirements.** If the FRS is silent on a behavior, do not test it — emit an `open_question` and flag it in an Open Questions list (SKILL rule 8). Prevents hallucinated cases.
4. **Cross-cutting is asserted, not retested.** If a spec `depends_on` a Cross-cutting Standards FRS (MOD-000) for an error envelope / RBAC base, the case *asserts the shared behavior appears* and references it via `within_test_cases`/`frs_spec` trace — it does not duplicate the foundation's full suite (SKILL rule 5).
5. **Outcome-oriented assertions.** Every case carries ≥1 assertion phrased as the *business/observable outcome* (e.g., "ledger balance debited by exactly the transfer amount" not "API returns 200"), linked to the BR/KPI it protects.

This section is the deliverable for "be clear on the context": the generator always sees the full spec, its sub-rows, the upstream chain, and the domain truth — and is told how each maps to test types and outcomes.

---

## 2. Outcome Richness — what a *brilliant* test case contains

### 2.1 Test-case quality rubric (drives the DSPy instruction + the validator's "rich" check)
A case is **rich** when it has all of:
- a **specific, observable `expected_result`** (FRS language; never "works correctly"),
- **≥2 concrete `key_assertions`** (outcome-level, not just HTTP status),
- **`test_data`** for any data-dependent case (setup rows + the exact input values, incl. boundary values for edge/negative),
- **`expected_observability`** when the spec defines observability (the log/metric/audit event the case asserts),
- **≥1 traceability link** to the FRS element(s) it validates,
- for `negative`/`edge_case`: an **error/recovery assertion** (what the system must reject + how it recovers),
- for `responsive`: a non-empty **`viewports`** list at the spec's named breakpoints.

### 2.2 New first-class fields for outcome richness (additive to the §3 schema)
- `test_cases.test_data` JSONB `default '{}'` — `{ "setup": [...], "inputs": {...}, "boundary": [...] }`. Makes a case self-contained + executable.
- `test_cases.expected_observability` JSONB `default '[]'` — `[{kind: log|metric|trace|audit, signal, assertion}]`, traced to `frs_specs.observability`.
- `test_plans.outcomes_summary` TEXT — "What this plan proves" (1–3 sentences; generated Stage B).
- `test_suites.outcomes_summary` TEXT — module-level "what the journey proves" (generated Stage A).

### 2.3 "Testing Outcomes" rollup (computed, surfaced in UI + `/coverage`)
For each module and the project, compute and expose:
- **outcomes proven** — the BR/objective/KPI set verified by ≥1 covering case (via traceability),
- **risk coverage** — count of negative + edge_case cases per spec (the "did we test the unhappy paths" signal),
- **test-type distribution** — how many of each type (functional/integration/e2e/negative/edge_case/responsive),
- **uncovered outcomes** — must-BRs / scenarios / FRs with no covering case.

This is returned by `GET /coverage` (§6) and rendered as the **Testing Outcomes panel** (§9.6).

---

## 3. Data model — 4 tables + enum extension (migration `0024_test_cases_artifact.py`)

Hand-written raw SQL: `ALTER TYPE … ADD VALUE IF NOT EXISTS`, `DO $$ … EXCEPTION WHEN duplicate_object` enum guards, `CREATE TABLE IF NOT EXISTS`. Models use `create_type=False`. Register all 4 models in `backend/app/models/__init__.py`.

### 3.0 Extend `artifact_type` enum (load-bearing — run first)
`artifact_type` is a PG enum `("concept_brief","brd","frs")` (`app/models/artifact.py:19`). Before any test_cases `ArtifactDocument` insert:
```sql
ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'test_cases';
```
(May need to run outside a txn block on older PG — `IF NOT EXISTS` form.) Then add `"test_cases"` to the `ArtifactType = Enum(...)` literal.

### 3.1 Enums (`create_type=False`)
```
tc_test_type   = {functional, integration, e2e, negative, edge_case, responsive}
tc_priority    = {P0, P1, P2, P3}
tc_source_kind = {acceptance_scenario, functional_requirement, business_rule,
                  independent_test, screen, manual}
tc_trace_kind  = {frs_spec, frs_acceptance_scenario, frs_functional_requirement,
                  frs_business_rule, frs_screen, brd_business_requirement, within_test_cases}
```

### Row mixin (every versioned table)
`id` uuid pk · `document_id` FK `artifact_documents ON DELETE CASCADE` · `row_key` · `version` CHECK(>0) · `is_current` · `is_locked` · `status`(active|removed) · `source`(ai|human|regeneration) · `created_by` FK `users SET NULL` · `created_at`. Constraints: `UNIQUE(document_id,row_key,version)`, partial index `ON (document_id) WHERE is_current`.

### 3.2 `test_suites` — one per FRS module
```
row_key TEXT            -- TS-{module_row_key}
module_row_key TEXT     -- → frs_modules.row_key
title TEXT
journey_overview TEXT   -- actor → goal → steps narrative framing the plans
test_strategy TEXT      -- which test_types apply + why
outcomes_summary TEXT   -- NEW: "what this journey proves"
completeness INT default 0
confidence TEXT default 'low'
```
Index `(document_id, module_row_key)`.

### 3.3 `test_plans` — one per FRS spec
```
row_key TEXT            -- TP-{spec_row_key}
suite_row_key TEXT      -- → test_suites.row_key
spec_row_key TEXT       -- → frs_specs.row_key
module_row_key TEXT     -- denormalized
title TEXT
preconditions TEXT
test_data_notes TEXT    -- echoes frs_specs.data_and_validation
coverage_targets JSONB default '{}'  -- NEW: {scenarios:[...], frs:[...], business_rules:[...], screens:[...]} the plan MUST cover (Stage A sets; validator checks against)
outcomes_summary TEXT   -- NEW: "what this plan proves"
priority tc_priority default 'P1'
summary TEXT
completeness INT default 0
confidence TEXT default 'low'
```
Indexes `(document_id, spec_row_key)`, `(document_id, suite_row_key)`.

### 3.4 `test_cases`
```
row_key TEXT            -- "{plan_row_key}-TC-001" zero-padded (NOT bare TC-001)
plan_row_key TEXT       -- → test_plans.row_key
spec_row_key TEXT       -- denormalized
module_row_key TEXT     -- denormalized
title TEXT
test_type tc_test_type
source_kind tc_source_kind
source_ref TEXT null     -- FRS element row_key the case derives from (e.g. M001-FRS001-AS-3)
given TEXT default ''     -- Gherkin (bare given/when/then cols are fine; FRS uses them)
when  TEXT default ''
then  TEXT default ''
steps JSONB default '[]'        -- [{step, expected}] for multi-step e2e/integration
preconditions TEXT default ''
key_assertions JSONB default '[]'        -- ≥2 outcome-level assertions (validator: rich check)
test_data JSONB default '{}'             -- NEW: {setup, inputs, boundary}
expected_result TEXT default ''          -- specific observable outcome (table view + emphasis)
expected_observability JSONB default '[]'-- NEW: [{kind, signal, assertion}] tied to frs.observability
viewports JSONB default '[]'             -- responsive only
auth_required BOOL default false
auth_role TEXT null                      -- persona/role (frs_module_actors / frs_screens.user_roles)
priority tc_priority default 'P1'
fr_refs JSONB default '[]'               -- frs_functional_requirements row_keys
scenario_refs JSONB default '[]'         -- frs_acceptance_scenarios row_keys
br_refs JSONB default '[]'               -- frs_business_rules row_keys (local FRS BR-N)
```
Indexes `(document_id, plan_row_key)`, `(document_id, spec_row_key)`, `(document_id, module_row_key)`, `(document_id, test_type)`.

### 3.5 `test_case_traceability` — NOT versioned, replace-all (mirror `FrsTraceability`)
```
id, document_id (FK CASCADE),
source_table TEXT   -- 'test_cases' | 'test_plans' | 'test_suites'
source_row_key TEXT
target_kind tc_trace_kind
target_ref TEXT
target_label TEXT default ''
confidence TEXT default 'high'
created_at
```
Indexes `(document_id)`, `(document_id, source_table, source_row_key)`, `(document_id, target_kind, target_ref)`. `target_ref` per kind as in the PRD (incl. transitive `brd_business_requirement`→`BR-001`).

### 3.6 Manifest maps (`manifest/test_cases.py`, mirror `manifest/frs.py:237`)
`TC_TABLE_MAP {table→model}` (3 versioned tables; traceability bespoke). `TC_TYPED_COLS {table→editable non-mixin cols}` (drives versioned upsert + generic edit). `TC_INT_COLS = {test_suites:{completeness}, test_plans:{completeness}}`.

### 3.7 Future `test_runs` (design now, build later — do NOT create)
`test_runs(id, document_id, test_case_row_key, run_at, viewport NULL, status{pass|fail|blocked|skipped}, evidence_url, executed_by)`. Drops in cleanly (row_key stable; viewport already a column).

---

## 4. Context wiring (`context/frs_layer.py` + `project_context.py` + `projection.py`)
- **New `frs_layer.py::build_frs_layer(project_id, db) -> FrsLayer`** (mirror `brd_layer.py`): loads `frs_status`, modules, specs (incl. narrative/independent_test/data_and_validation/errors_and_edge_cases/observability), acceptance_scenarios, functional_requirements, business_rules, screens, ui_components, endpoints, data_entities, module_actors, and `FrsTraceability` (the FRS→BR rows for the transitive rollup), plus a `formatted_context` projection per §1.1.
- **`project_context.py`**: add `@dataclass FrsLayer` + `frs: FrsLayer | None` to `ProjectContextBundle`; `gather_project_context(artifact_type="test_cases")` loads **both** `build_brd_layer` and `build_frs_layer`; `_compute_readiness` adds `frs_ready = frs is not None and frs.frs_status == "validated"` → folds into `can_generate` + `blocking_reason`.
- **`projection.py`**: add a `test_cases` branch in `project_for_unit` giving `frs_context = bundle.frs.formatted_context` + `brd_context` + App Brain + NFR + depth_search doc sections (the full §1.1 pack).

---

## 5. DSPy units + orchestration

### 5.1 Manifest (`manifest/test_cases.py`) — `TcUnitSpec` mirrors `FrsUnitSpec`
- **`plan_journeys`** (Stage A, 1 call): writes `["test_suites","test_plans"]`, depends `[]`, 120s. Emits one suite/module (journey_overview + test_strategy + outcomes_summary) and one plan STUB/spec (priority carried, `coverage_targets` enumerating the scenarios/FRs/business-rules/screens the plan must cover). row_keys `TS-{module}` / `TP-{spec}`. Preserve current keys; reproduce locked verbatim.
- **`author_plan`** (Stage B, per FRS spec, parallel-per-module): writes `["test_plans","test_cases","test_case_traceability"]`, depends `["plan_journeys"]`, 360s. Authors comprehensive multi-level cases per §1–§2: cover every scenario/FR/business-rule/independent_test/screen; tag `test_type`; fill rich fields (`test_data`, `key_assertions`, `expected_result`, `expected_observability`); set `*_refs` + emit traceability rows (incl. transitive `brd_business_requirement`); write `outcomes_summary`. ≥1 negative per spec; every `is_negative` scenario → ≥1 negative case. Reproduce locked cases verbatim.

### 5.2 DSPy (`skills/dspy_test_cases.py`, mirror `dspy_frs.py`)
Pydantic output models + `dspy.Signature` (typed docstring carrying the §1.2 rules + §2.1 rubric) + `ChainOfThought` + async `run_*()` returning `_load_fixture(...)` when `_is_mock()` else `run_in_executor`. Stage B uses the `asyncio.shield` + `TimeoutError` re-raise pattern (`dspy_frs.py:710`).
- Stage A signature inputs: `project_name, business_unit, frs_context, brd_context, cb_context, app_brain, source_sections, qa_pairs, current_plans, locked_plans`.
- Stage B signature inputs: `target_spec_row_key, target_spec` (full spec + all sub-rows JSON), `module_context, sibling_plans_summary, brd_context, cb_context, app_brain, nfr_context, source_sections, qa_pairs, current_plan`.
- **Pydantic validators (hard rules):** `test_type: Literal[...]`; `responsive ⇒ viewports non-empty`; `key_assertions: min_length=2`; `expected_result` non-empty; `negative/edge_case ⇒ ≥1 error-style assertion`; `TcAuthorPlanOutput.test_cases: min_length=1`.
- **Mock fixtures:** `fixtures/test_cases_plan_journeys.json` + `test_cases_author_plan.json`, registered in `MockProvider._SKILL_FIXTURE_MAP`; copy the fixture-row_key remap from `run_design_spec`. **`LLM_PROVIDER=mock` stays green, zero Vertex calls.**

### 5.3 Orchestrator (`tc_orchestrator.py`, mirror `frs_orchestrator.py`)
`upsert_tc_rows` ← `upsert_frs_rows`; `_upsert_tc_traceability` ← `_upsert_frs_traceability` (delete-then-insert per source, `begin_nested()`); `generate_tc_plan_journeys` (Stage A); `generate_tc_author_plan(spec_row_key)` (Stage B per spec — set `unit_status._current_unit`, run, persist cases **scoping soft-delete to AI-authored `{plan}` children only, excluding `source='human'`**, replace-all traceability, JSONB merge, **commit per spec**); `generate_tc_all(..., max_parallel_modules=3)` (per-module coroutines, own `AsyncSessionLocal`, specs sequential, `Semaphore(3)`); `run_tc_stage_b`, `regenerate_tc_plan`, `get_tc_detail`, `reset_tc_generating`; CRUD `edit/delete/unlock/restore/history/add_tc_case`.

### 5.4 Celery + progress
`workers/tasks.py`: `generate_test_cases`, `design_all_test_plans`, `regenerate_test_cases_plan`, each in `_run_async()`, dispatched via `dispatch()`. API: mock → in-process; real → `status='generating'` + dispatch + return; broker down → reset + 503. Progress via atomic JSONB merge into `artifact_documents.unit_status`:
`_current_unit` (`plan_journeys` → `author_plan_{spec}`); per-plan `{completeness, cases_authored}`; `_module_progress {specs_total, specs_done}`; `_refine_error`.

---

## 6. Traceability + coverage + Testing Outcomes (`tc_coverage.py` + `GET /coverage`)

`compute_testcase_coverage(frs_rows, tc_rows, traces, brd_must_brs, frs_spec_to_br)` — pure function (no DB), builds the coverage index from BOTH `*_refs` and traceability rows. Returns `TcCoverageReport`:
- `entries` (one per required FRS element: every AS, FR, business_rule, screen, independent_test; `covered_by`, `is_covered`, `has_negative`),
- `per_spec` / `per_module` `{total, covered, pct, negative_ok}`, `project_pct`, `uncovered`,
- `must_br_uncovered` (multi-hop: a `must` BR is tested iff *all* its implementing specs are 100%),
- **`outcomes`** (NEW): per-module `{outcomes_proven:[BR/obj/KPI], risk_coverage:{negative, edge}, type_distribution:{...}, uncovered_outcomes:[...]}`.

`GET /coverage` recomputes live on every call (no cache — manual edits reflect immediately), loads active FRS + test_cases + `test_case_traceability` + `FrsTraceability(target_kind='brd_business_requirement')`, serializes `{project_pct, modules[], brd_chain[], outcomes, summary}`:
```json
{
  "project_pct": 86.4,
  "modules": [{"module_row_key":"MOD-001","title":"...","pct":92,"plan_count":4,"case_count":61,
    "specs":[{"spec_row_key":"M001-FRS001","title":"...","pct":100,"priority":"P0",
      "elements":[{"kind":"acceptance_scenario","frs_row_key":"M001-FRS001-AS-1","is_negative":false,
                   "covered_by":["TP-M001-FRS001-TC-001"]}]}]}],
  "brd_chain": [{"br_row_key":"BR-007","priority":"must","implementing_specs":["M003-FRS002"],"tested":false,
                 "reason":"M003-FRS002 has 2 uncovered acceptance scenarios"}],
  "outcomes": {"MOD-001": {"outcomes_proven":["BR-001","KPI:failed-transfer-rate"],
               "risk_coverage":{"negative":12,"edge":8},
               "type_distribution":{"functional":18,"integration":9,"e2e":5,"negative":12,"edge_case":8,"responsive":4},
               "uncovered_outcomes":["FR-2","BR-007"]}},
  "summary": {"total_elements":312,"covered":270,"must_br_total":18,"must_br_tested":15,"must_br_untested":3}
}
```
Powers the Coverage Galaxy (§9.5) and Testing Outcomes panel (§9.6).

---

## 7. Validation checklist (`validators/test_cases.py`, mirror `validators/frs.py`)
`summarize_findings` → `blocking = critical + major`; row rules fire only on authored plans.
- **CRITICAL (block):** `zero_plans`; `plan_zero_cases` (P0/P1 spec implementing a must-BR, 0 cases); `must_br_untested` (multi-hop chain fails for a must-BR).
- **MAJOR (block):** `scenario_uncovered`; `fr_uncovered`; `no_negative_test`; `orphan_case` (refs → non-active FRS row); `case_no_trace`; `responsive_no_viewports`; **`case_not_rich`** (NEW: <2 assertions OR empty `expected_result` OR negative/edge missing an error assertion).
- **MINOR:** `business_rule_uncovered`; `plan_completeness<90`; `independent_test_uncovered`; **`missing_observability_assertion`** (spec defines observability but case omits `expected_observability`).
- **COVERAGE (non-block):** uncovered scenario/FR on P2/P3 spec.
- **WARNING:** `screen_no_responsive`.
`POST /validate` (mirror `frs.py:248`): blocking>0 → findings uncommitted; else `status='validated'` + `validated_at/by/snapshot_key` + bulk-lock current rows.

---

## 8. API (`app/api/test_cases.py`, mounted in `main.py`, envelope `ok`/`err`)
Under `/api/projects/{project_id}/artifacts/test_cases`:
```
GET    /                                  detail (suites→plans→cases + traceability + unit_status + messages)
POST   /readiness                         {frs_ready, brd_ready, can_generate, blocking_reason}
POST   /generate                          Stage A  (gate require_artifact_validated('frs'))
POST   /design-all-plans                  Stage B all/remaining
POST   /plans/{spec_row_key}/design       Stage B one plan
POST   /plans/{spec_row_key}/regenerate   regenerate one plan
POST   /reset-generating
GET    /coverage                          §6 payload (chain + outcomes)
GET    /findings                          read-only validation report
POST   /validate                          validate + commit + lock
POST   /plans/{plan_row_key}/cases        ADD manual case + link (≥1 FRS link required)
POST   /{table}/{row_id}/edit             versioned edit (lock-aware, 409 on version conflict)
POST   /{table}/{row_id}/delete           soft delete
POST   /{table}/{row_id}/unlock | /restore
GET    /{table}/{row_id}/history
GET    /orphans                           dangling-traceability diagnostic
GET    /export                            markdown bundle (SKILL template + coverage matrix)
```
`VALID_TC_TABLES = set(TC_TABLE_MAP)` guards generic routes (traceability not editable generically).

### Add + link (`add_tc_case`, the confirmed requirement)
Resolve doc+plan (404) → **validate each FRS link resolves to an active FRS row (422 else)** → next `row_key {plan}-TC-{n:03d}` → insert `source='human', source_kind='manual'` → persist each link as a `test_case_traceability` row + transitive `brd_business_requirement` trace → commit. Coverage reflects on next GET (live recompute). Manual cases survive AI regen (excluded from Stage B soft-delete scope).

---

## 9. UI / UX — Module → Spec → Cases workspace (deep spec)

Mirrors the FRS frontend (SWR polling, dedicated builder, three-pane, modal edit, trace chips, coverage galaxy, sonner toasts, lucide, Tailwind CSS-var tokens). New sidebar nav item in `app/projects/[id]/page.tsx` (`CheckSquare`, `locked` until FRS validated, status badge) → `view==='test-cases'` → `<TestCasesBuilderView/>`.

### 9.0 State machine (every state has a designed screen)
`locked` (FRS not validated) → `ready` (empty, can generate) → `generating` (theater) → `authored` (`in_interview`) → `validated`; plus `error`/`stuck` (recovery) and `orphaned` (FRS changed) overlays.

**Locked / Ready / Empty states**
```
┌ Test Cases ───────────────────────────────────────────────┐
│  🔒 Locked                                                  │
│  Test cases unlock once the FRS is validated.              │
│  FRS status: In Review · 3 specs pending validation        │
│  [ Go to FRS → ]                                           │
└────────────────────────────────────────────────────────────┘
        ── when FRS validated ──►
┌ Test Cases · Ready ────────────────────────────────────────┐
│  Generate a full, traceable test suite from your FRS.      │
│  Source: FRS v4 · 6 modules · 23 specs · 142 scenarios     │
│  Will produce: ~1 suite/module, 1 plan/spec, multi-level   │
│  cases (functional · integration · e2e · negative · edge · │
│  responsive) with full BRD→FRS→Test traceability.          │
│  [ ⚡ Generate test cases ]   readiness ✓ all FRS validated │
└────────────────────────────────────────────────────────────┘
```

### 9.1 Three-pane builder (authored/validated)
```
┌ Test Cases · Validated ✓ · PayHub          [Coverage] [Outcomes] [Validate] [Export ▾] ┐
├──────────────────────┬───────────────────────────────────────────┬──────────────────────┤
│ SUITES / PLANS rail  │  PLAN PANEL                                 │ COVERAGE drawer      │
│ search ⌕  type ▾     │  Suite: Payments · journey overview ▾       │ Plan 100% ▰▰▰▰▰▰    │
│ ▸ Payments      92%  │  "Move money between accounts safely…"      │ AS-1 ✓ AS-2 ✓ AS-3 ✓ │
│   TP-…FRS001 ✓ P0    │  ─────────────────────────────────────────  │ FR-1 ✓ FR-2 ✗        │
│   TP-…FRS002 ◐ P1    │  Plan: Initiate Payment (M001-FRS001) · P0  │ Negative ✓ (3)       │
│ ▸ Ledger        78%  │  Proves ▸ "BR-001 funds debited exactly…"   │ Outcomes ▸ BR-001,KPI│
│ ▸ Cross-cutting 100% │  Preconditions · Test data notes            │                      │
│ [+ Add plan]         │  ┌ filter: type ▾  priority ▾  search ⌕ ──┐ │                      │
│                      │  │TC-001 Happy path transfer   e2e  AS-1 ●││                      │
│                      │  │TC-002 Reject negative amount neg AS-3 ●││                      │
│                      │  │TC-003 Mobile layout         resp SCR-1●││                      │
│                      │  └─────────────────────────────────────────┘│                      │
│                      │  [+ Add test case]                          │                      │
└──────────────────────┴───────────────────────────────────────────┴──────────────────────┘
```
- **Left rail** (`TestCasesSuiteRail`): suites grouped (Foundation/Vertical/Cross-cutting per FRS layer), each with a coverage ring; expand → plan rows with status dot (✓ authored / ◐ partial / ○ stub) + priority chip. Filter by test_type/search.
- **Plan panel** (`TestCasesPlanPanel`): journey overview (collapsible), the plan's **"Proves"** line (outcomes_summary), preconditions/test-data notes, then the **test-case table** with a local filter bar (type, priority, search).
- **Coverage drawer**: per-plan element checklist (AS/FR/BR/screen) with ✓/✗, negative count, and the outcomes/BRs this plan protects. Toggled from header.

### 9.2 Test-case row + expanded detail card (`TestCasesTable` + row expand)
Collapsed row: `TC-id · title · type badge · priority chip · trace chips · row actions (Edit/History/Lock/Delete)`. Click → expand to the **rich detail card** that showcases outcome richness:
```
TC-002 · Reject negative amount            [negative] [P0]   ✎ ⟲ 🔒 🗑
Source: Acceptance Scenario AS-3  ·  Auth: analyst
Given a funded account
When the user enters a transfer amount of -50.00
Then the transfer is rejected with "Amount must be greater than zero"
Test data ▸ inputs:{amount:-50.00}  boundary:[0, -0.01, min]
Key assertions
  ☑ Inline error "Amount must be greater than zero" shown on the Amount field
  ☑ No ledger entry is created (balance unchanged)
  ☑ Submit button remains disabled until corrected
Expected observability ▸ audit: "transfer.rejected" event with reason=invalid_amount
Expected result ▸ Transfer blocked client- and server-side; account balance unchanged.
Traces ▸ [AS-3] [FR-2] [BR-001 must]
```
Every field is inline-editable (pencil → `TestCaseRowEditDialog`). Locked rows render dimmed + lock chip; editing a locked row prompts unlock.

### 9.3 Edit dialog (`TestCaseRowEditDialog`, schema-driven)
Fields: title (text), test_type/priority (select w/ colored option), source_kind/source_ref (select), given/when/then (textarea), steps (ordered step editor add/remove/reorder), key_assertions (tag/list editor, min 2 enforced with inline hint), test_data (key-value + boundary list), expected_result (textarea), expected_observability (rows of {kind, signal, assertion}), viewports (multiselect chips, shown only for responsive), auth_required/auth_role, and the `*_refs` (FRS-element pickers — see 9.4). Save = optimistic update + version bump; 409 → toast "Edited elsewhere — reloaded."

### 9.4 Add + link dialog (`AddTestCaseDialog`) with live coverage delta
- Step 1 pick type + write G/W/T or steps + assertions.
- Step 2 **link picker**: typeahead over the current spec's FRs / acceptance scenarios / business rules (row_key + label); ≥1 required.
- **Live coverage delta**: as links are chosen, a strip shows "This will cover **FR-2**, **AS-3** → plan coverage 80% → **100%**". Reinforces the traceability value at creation time.
- Save → POST `/plans/{plan}/cases`; new case animates into the table; coverage ring updates.

### 9.5 Coverage Galaxy (`TestCasesCoverageGalaxy`, full chain)
Modal SVG, **three columns**: BRD must-BRs → FRS specs → Test plans, cubic-bezier links. Uncovered must-BRs and uncovered scenarios **pulse red**. Header: `Project coverage 86% · 15/18 must-BRs tested`. A top alert banner lists untested must-BRs with one-click jump. Hover a node → highlight its links + tooltip; click → filter the rail to that path. Per-module coverage shown as a heat-tinted column header. Honors `prefers-reduced-motion` (no pulse, static red ring).

### 9.6 Testing Outcomes panel (`TestingOutcomesPanel`, the "outcome richness" surface)
Opened from the header `[Outcomes]`. Per module + project:
```
Testing Outcomes — Payments module
Proves ▸ BR-001 (funds debited exactly), BR-004 (idempotent retry), KPI "failed-transfer rate < 0.1%"
Coverage     ▰▰▰▰▰▰▰▰▱▱  86%        Risk coverage  ▸ 12 negative · 8 edge
Test types   functional ███ 18 · integration ██ 9 · e2e █ 5 · negative ███ 12 · edge ██ 8 · responsive █ 4
Uncovered outcomes ⚠  FR-2 (refund path) · BR-007 (must) — no test yet  [ Generate missing ]
```
A coverage donut, a test-type distribution bar, the proven-outcomes list (from traceability → BR/objective/KPI), and an uncovered-outcomes call-to-action. This is *what the suite proves*, not just counts.

### 9.7 Live generation theater (`TestCasesGenerationTheater` + banner)
SWR `refreshInterval` 1500ms while `generating` / `_current_unit` set, else 0. Two phases driven by `unit_status`:
```
Generating test plans ……………………………  ● Phase 1/2 · plan_journeys
▸ Payments       ▓▓▓▓▓▓▓░░  5/7 specs
▸ Ledger         ▓▓▓░░░░░░  2/6 specs
▸ Cross-cutting  ▓▓▓▓▓▓▓▓▓  done
Now authoring: M001-FRS006 "Refund initiation" · 23 cases so far · 4 negative
```
Per-module bars (`_module_progress`) + the "now authoring" line make the running step explicit. Stuck (>N s no progress) → recovery button (`reset-generating`). Errors surface as a non-blocking strip ("FRS010 failed — retry") from `_refine_error`.

### 9.8 Findings drawer, badges, tokens, a11y
- `TestCasesFindingsDrawer`: grouped critical/major/minor/coverage/warning with jump-to-row + suggested fix (mirror FRS).
- `TestCasesTraceChip`: color per `tc_trace_kind` — AS pink · FR indigo · BR amber · screen sky · brd_business_requirement green (transitive, "must" gets a ring) · within_test_cases gray. Hover tooltip (label + confidence); click → jump; unlink affordance.
- New `--tc-type-*` / `--tc-priority-*` CSS vars in `globals.css`.
- Keyboard: `e` edit focused row, `n` new case, `/` focus search, arrow-nav rail; full focus rings; `aria-live` on the theater progress; reduced-motion respected.

### 9.9 Frontend files
`lib/api.ts` (`api.testcases.*`), `lib/types.ts` (`TestCasesDetail, TestSuiteRow, TestPlanRow, TestCaseRow, TestCasesCoverage, TestCasesFinding`), `lib/testcases-manifest.ts` (type/priority tokens + icons). Components `frontend/app/components/testcases/`: `TestCasesBuilderView, TestCasesEmptyState, TestCasesLockedState, TestCasesGenerationTheater, TestCasesGenerationBanner, TestCasesSuiteRail, TestCasesPlanPanel, TestCasesTable, TestCaseDetailCard, TestCaseRowEditDialog, TestCaseRowActions, AddTestCaseDialog, TestCasesCoverageGalaxy, TestingOutcomesPanel, TestCasesTraceChip, TestCasesFindingsDrawer`.

---

## 10. Risks & mitigations
- **FRS regen → stale refs.** FRS row_keys are stable under edit (only deletion/modularize re-runs orphan). `orphan_case` validator + `GET /orphans` detect; never auto-delete — offer relink/regenerate.
- **Manual cases clobbered on regen.** Stage B soft-delete scope excludes `source='human'`.
- **Context size / timeout.** Per-spec Stage B + commit-per-spec keeps completions small + durable; sem=3 respects Vertex limits.
- **Generic/weak cases.** The §1 context pack + §2 rubric + `case_not_rich` validator force specificity and outcome-orientation.
- **Enum extension** mandatory before any insert (§3.0); downgrade leaves value in place (matches FRS/BRD practice).

---

## 11. Critical files

**Templates to copy first:** `backend/app/services/artifacts/frs_orchestrator.py` (upsert / traceability replace-all / per-spec loop / `generate_frs_all`) · `backend/app/services/skills/dspy_frs.py` (per-spec signature, shield/timeout, mock remap) · `backend/app/api/frs.py` (endpoints, `/coverage` @889, `/validate` @248, dispatch+503 @752) · `backend/app/services/artifacts/validators/frs.py` · `backend/app/api/deps.py:80` (`require_artifact_validated`) · `backend/app/services/context/{brd_layer,project_context,projection,coverage}.py` · `frontend/app/components/frs/*`.

**Create (backend):** `alembic/versions/0024_test_cases_artifact.py` · `app/models/test_cases.py` (+register in `__init__.py`) · `app/services/artifacts/manifest/test_cases.py` · `app/services/skills/dspy_test_cases.py` · `app/services/artifacts/tc_orchestrator.py` · `app/services/artifacts/validators/test_cases.py` · `app/services/context/frs_layer.py` · `app/services/context/tc_coverage.py` · `app/api/test_cases.py` · `app/services/llm/fixtures/test_cases_{plan_journeys,author_plan}.json`.

**Modify (backend):** `app/models/artifact.py` · `app/services/context/{project_context,projection}.py` · `workers/tasks.py` · `app/main.py` · `app/services/llm/mock_provider.py`.

**Create/modify (frontend):** `lib/{api,types}.ts`, `lib/testcases-manifest.ts`, `app/projects/[id]/page.tsx`, `app/globals.css`, `app/components/testcases/*` (§9.9).

---

## 12. Verification (end-to-end, mock-first)
1. **Migration:** `make migrate` → `0024` applies, `\dT+ artifact_type` shows `test_cases`, 4 tables exist.
2. **Backend tests** (`backend/tests/test_test_cases.py`, `LLM_PROVIDER=mock`, seed a validated-FRS project):
   - `POST /generate` → suites + plan stubs (Stage A, with `coverage_targets`); after `design-all-plans` every spec has ≥1 case, ≥1 negative, rich fields populated, traces present.
   - `GET /coverage` → `project_pct`, `must_br` rollup, `outcomes` block; an uncovered scenario appears in `uncovered`.
   - `POST /plans/{plan}/cases` with `fr_refs` link → case created `source='human'`; coverage now shows it covering that FR (live recompute).
   - `edit` → `delete` → `history` → version bump / soft-delete / restore.
   - `validate` incomplete → 4xx + findings (incl. `case_not_rich`); complete → `validated` + rows locked.
   - regenerate a plan → manual case survives.
   - assert **zero Vertex/PageIndex/network calls**.
3. **Static:** `make typecheck && make lint && make test-be`.
4. **Live UI:** `make dev-be` + `make dev-fe` + `make worker` (Redis :6379), login `qa@specforge.test`, open a validated-FRS project → Test Cases. Generate → watch theater (per-module bars + "now authoring"). Expand a case → see rich detail card. Add+link a case → live coverage delta. Open Coverage Galaxy (3-column chain, pulsing untested must-BR) and Testing Outcomes panel. Validate → badge flips to Validated ✓. (Verify with dev-browser skill.)
5. **Prod smoke (optional, real Vertex):** `POST /generate` returns immediately `generating`; Celery authors per-spec; `_current_unit` advances; final detail renders.

---

## 13. Build order (tasks)
1. Model + migration `0024` (+ register, extend enum) → `make migrate`.
2. Context: `frs_layer.py` + bundle/readiness/projection wiring.
3. Manifest + DSPy units + mock fixtures (mock path green).
4. Orchestrator + Celery tasks + dispatch.
5. `tc_coverage.py` + validator.
6. API router + mount.
7. Backend tests (mock) → typecheck/lint/test-be green.
8. Frontend: api/types/manifest → builder shell → rail/panel/table → detail card + edit dialog → add/link → theater → coverage galaxy + outcomes panel → findings drawer → nav wiring + tokens.
9. Live UI verification (dev-browser) + optional prod smoke.
