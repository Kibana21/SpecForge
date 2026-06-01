# E3 — Test Cases Module PRD

> **The final link in the SpecForge chain**: RU → CB → BRD → **FRS → Test Cases**.
> Conceptual seed: `reference_mds/skills/e2e-test-plan-builder/SKILL.md`, elevated from a
> file-writing procedure into a first-class, versioned, **traceable** SpecForge artifact that
> mirrors the proven BRD/FRS generation engine.
>
> **Goal**: from a human-validated FRS, generate comprehensive, multi-level test cases
> (functional / integration / e2e / negative / edge-case / responsive), organized
> Module → FRS spec → test cases, where **every line item and property is editable, deletable,
> lockable and version-tracked**, users can **add a test case and link it to any FRS functional
> requirement / acceptance scenario / business rule**, and a **Coverage view proves the full
> Project → BRD → FRS → Test-Case chain**.
>
> **Depends on FRS** — generation is gated until the FRS `status='validated'` (reuses
> `require_artifact_validated("frs")`), enforcing a clean traceability chain.
>
> **Companion implementation plan**: `/Users/kartik/.claude/plans/go-through-e2e-test-plan-builder-skill-m-goofy-token.md`
> (full table DDL, orchestrator/DSPy file map, coverage pseudocode, wireframes, verification).

---

## 1. Introduction / Overview

SpecForge turns messy requirements into a validated chain of artifacts. Today that chain ends at the **FRS** (Functional Requirements Specification): once a human validates it, each FRS *spec* holds Gherkin acceptance scenarios, functional requirements (FRs), business rules, and screens. The obvious next link — and the thing QA teams actually ship against — is a **test suite that proves the built system satisfies the FRS**, and transitively the BRD business requirements the business cares about.

The **Test Cases module (E3)** generates that suite. It reads the validated FRS, decomposes it into a **test suite per module** (framed by a user-journey overview) and a **test plan per FRS spec**, then authors **comprehensive multi-level test cases** for every acceptance scenario, FR, business rule, independent test, and screen. Each case is tagged with a `test_type` and carries **traceability links** back to the exact FRS elements (and transitively to BRD requirements) it validates.

The defining feature is **traceability + coverage**: at any moment the user can open a **Coverage Galaxy** that draws the full BRD-must-requirement → FRS-spec → test-plan chain and flags exactly which scenarios, FRs, and *must*-priority business requirements are not yet tested. Generation is blocked until the FRS is validated, so the chain is always clean.

The module reuses the BRD/FRS engine wholesale — row-level versioning, locking, idempotent regeneration, Celery dispatch, the `unit_status` progress channel, and the mock-provider path — so the hard infrastructure is proven, not reinvented.

---

## 2. Goals

- **G1 — Comprehensive generation.** From a validated FRS, generate test cases covering *every* acceptance scenario (≥1 each), *every* FR (≥1 each), every business rule, each spec's independent test, and each screen — tagged across 6 test types (functional, integration, e2e, negative, edge_case, responsive).
- **G2 — First-class traceability.** Every test case links to ≥1 FRS element and rolls up transitively to BRD business requirements. The Project → BRD → FRS → Test-Case chain is queryable and *visualized*.
- **G3 — Coverage you can see and trust.** A live coverage computation reports per-spec, per-module, and per-project coverage %, and identifies uncovered FRS elements and untested *must*-BRs. Coverage gates validation (tiered by priority).
- **G4 — Full human control.** Every row and every property is editable, deletable, lockable, restorable, and version-tracked. Users can add a brand-new test case and link it to existing FRS requirements. Locked/manual rows survive AI regeneration.
- **G5 — An amazing, legible UI.** A Module → Spec → Cases workspace with inline editing, colored type/priority badges, provenance trace chips, and a coverage galaxy — matching SpecForge's existing design language.
- **G6 — Always-visible progress.** During generation the user sees exactly which step is running (Stage A vs Stage B, per-module progress bars, "now authoring spec X") via the live `unit_status` channel.
- **G7 — Rock-solid, mockable backend.** Mirror the FRS engine exactly; keep the `LLM_PROVIDER=mock` path green (zero Vertex/PageIndex calls) so CI and tests stay deterministic.

---

## 3. User Stories

> UI stories include browser verification (dev-browser skill) on a seeded validated-FRS project (`qa@specforge.test`).

### US-001: Test-cases data model + migration
**Description:** As a developer, I need versioned tables for test suites, plans, cases, and traceability so authored content persists with full history.

**Acceptance Criteria:**
- [ ] Migration `0024_test_cases_artifact.py` runs `ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'test_cases'` **first**, then creates 4 enums (`tc_test_type`, `tc_priority`, `tc_source_kind`, `tc_trace_kind`) with `DO $$ … EXCEPTION WHEN duplicate_object` guards.
- [ ] Creates `test_suites`, `test_plans`, `test_cases` (row mixin + `UNIQUE(document_id,row_key,version)` + partial `is_current` index + `CHECK(version>0)`) and `test_case_traceability` (NOT versioned, 3 indexes).
- [ ] `"test_cases"` added to the `ArtifactType` enum literal in `app/models/artifact.py`; all 4 models registered in `app/models/__init__.py`.
- [ ] `make migrate` applies cleanly; `make typecheck` passes.

### US-002: Context bundle exposes the validated FRS + readiness gate
**Description:** As the generation engine, I need a full FRS layer (plus BRD) in the context bundle, and a readiness check that blocks until FRS is validated.

**Acceptance Criteria:**
- [ ] New `context/frs_layer.py::build_frs_layer` loads modules, specs, acceptance_scenarios, FRs, business_rules, screens, FRS→BR traceability, `frs_status`, and a `formatted_context`.
- [ ] `gather_project_context(artifact_type="test_cases")` loads both BRD and FRS layers; `_compute_readiness` sets `can_generate=False` + `blocking_reason` when FRS not validated.
- [ ] `projection.py` has a `test_cases` branch giving full FRS + BRD context to units.
- [ ] `make test-be` covers the readiness gate (validated vs not).

### US-003: Stage A — plan journeys (suites + plan stubs)
**Description:** As a QA architect, I want the system to decompose the FRS into a test suite per module and a plan stub per spec so I get an organized scaffold.

**Acceptance Criteria:**
- [ ] DSPy `plan_journeys` unit emits one `test_suite` per FRS module (journey_overview + test_strategy) and one `test_plan` STUB per FRS spec (priority carried from spec).
- [ ] row_keys: suites `TS-{module_row_key}`, plans `TP-{spec_row_key}`; existing keys preserved on regen; locked rows reproduced verbatim.
- [ ] Mock fixture `test_cases_plan_journeys.json` registered; runs with zero Vertex calls under `LLM_PROVIDER=mock`.

### US-004: Stage B — author test cases per FRS spec
**Description:** As a QA architect, I want each plan filled with comprehensive multi-level test cases so I have a real, runnable plan.

**Acceptance Criteria:**
- [ ] DSPy `author_plan` unit runs **once per FRS spec** (modules parallelized, semaphore=3; specs sequential, commit per spec, 360s timeout).
- [ ] For each spec: every acceptance scenario → ≥1 case; every FR → ≥1 case; every business rule covered; independent_test → ≥1 e2e case; each screen → ≥1 responsive case; ≥1 negative case per spec; every `is_negative` scenario → ≥1 `negative` case.
- [ ] Each case sets `fr_refs/scenario_refs/br_refs` AND emits `test_case_traceability` rows; plan emits a `frs_spec` trace + transitive `brd_business_requirement` traces.
- [ ] Pydantic validators enforce: `responsive` ⇒ non-empty `viewports`; `key_assertions` non-empty; ≥1 case per plan.
- [ ] Mock fixture `test_cases_author_plan.json` with row_key remap; zero Vertex calls under mock.

### US-005: Generation endpoints + Celery + live progress
**Description:** As a user, I want to trigger generation and watch which step is running so long jobs feel transparent.

**Acceptance Criteria:**
- [ ] Endpoints `POST /generate` (Stage A, gated `require_artifact_validated("frs")`), `/design-all-plans`, `/plans/{spec}/design`, `/plans/{spec}/regenerate`, `/reset-generating`.
- [ ] Mock → in-process synchronous; real → set `status='generating'`, dispatch Celery (`_run_async` wrapper + `dispatch()`), return immediately; broker-down → reset + 503.
- [ ] `unit_status` JSONB carries `_current_unit`, per-plan `{completeness, cases_authored}`, `_module_progress {specs_done/total}`, `_refine_error`.

### US-006: Coverage computation + endpoint
**Description:** As a QA lead, I want live coverage of every FRS element and the BRD chain so I know what's untested.

**Acceptance Criteria:**
- [ ] `tc_coverage.py::compute_testcase_coverage` (pure function) builds the coverage index from both `*_refs` and traceability rows; returns per-spec, per-module, project %, uncovered list, and `must_br_uncovered` (multi-hop: a must-BR is tested only if all its implementing specs are 100%).
- [ ] `GET /coverage` recomputes live (no cache) and returns the `{project_pct, modules[], brd_chain[], summary}` payload.
- [ ] A manually added case appears in `covered_by` on the next GET.

### US-007: Edit / delete / lock / history on every row
**Description:** As a user, I want to edit, delete, lock, and view history of any suite/plan/case property.

**Acceptance Criteria:**
- [ ] `POST /{table}/{row_id}/edit` (versioned, lock-aware, `expected_version` → 409 conflict), `/delete` (soft `status='removed'`), `/unlock`, `/restore`, `GET /{table}/{row_id}/history`.
- [ ] `VALID_TC_TABLES = set(TC_TABLE_MAP)` guards generic routes; `test_case_traceability` is not editable via generic CRUD.
- [ ] Verify in browser using dev-browser skill (edit a case, delete it, restore from history).

### US-008: Add a new test case and link it to an FRS requirement
**Description:** As a QA author, I want to add my own test case and link it to an existing functional requirement / acceptance scenario / business rule.

**Acceptance Criteria:**
- [ ] `POST /plans/{plan_row_key}/cases` validates each link resolves to an active FRS row (422 otherwise), inserts with `source='human'`, `source_kind='manual'`, version=1, next `row_key {plan}-TC-NNN`.
- [ ] Each link persisted as a `test_case_traceability` row + transitive `brd_business_requirement` trace.
- [ ] Manual cases survive AI regeneration (excluded from Stage B soft-delete scope).
- [ ] Verify in browser: add case via dialog with an FR link picker; it appears and counts toward coverage.

### US-009: Validation checklist + validate gate
**Description:** As a reviewer, I want validation to block on real coverage gaps so a weak suite can't be marked done.

**Acceptance Criteria:**
- [ ] `validators/test_cases.py` produces tiered findings: CRITICAL (`zero_plans`, `plan_zero_cases` on P0/P1+must-BR, `must_br_untested`), MAJOR (`scenario_uncovered`, `fr_uncovered`, `no_negative_test`, `orphan_case`, `case_no_trace`, `responsive_no_viewports`), MINOR, COVERAGE (non-blocking), WARNING.
- [ ] `POST /validate`: blocking>0 → return findings uncommitted; else `status='validated'` + `validated_at/by/snapshot_key` + bulk-lock current rows.
- [ ] `GET /findings` returns the read-only report.

### US-010: Test Cases workspace UI (Module → Spec → Cases builder)
**Description:** As a user, I want a clear three-pane workspace to navigate suites, read plans, and edit cases inline.

**Acceptance Criteria:**
- [ ] Sidebar nav item (`CheckSquare`, locked until FRS validated, status badge) + `view==='test-cases'` branch rendering `TestCasesBuilderView`.
- [ ] Left rail: suites (per module, with coverage %) → plans; main panel: journey overview + plan header + an editable test-case table; optional coverage drawer.
- [ ] Test-type and priority shown as colored badges (new `--tc-type-*` / `--tc-priority-*` CSS vars); row hover → Edit/History/Lock/Delete; edit opens a schema-driven dialog.
- [ ] Verify in browser using dev-browser skill.

### US-011: Live generation theater
**Description:** As a user, I want a progress view that shows the running step, so generation isn't a black box.

**Acceptance Criteria:**
- [ ] SWR `refreshInterval` = 1500ms while `generating` / `_current_unit` set, else 0.
- [ ] Theater shows Phase 1/2 (plan_journeys → author_plan), per-module progress bars from `_module_progress`, and a "Now authoring: <spec> · N cases so far" line.
- [ ] A `reset-generating` recovery button appears if the job is stuck.
- [ ] Verify in browser using dev-browser skill.

### US-012: Coverage Galaxy + trace chips
**Description:** As a QA lead, I want to see and click the full traceability chain.

**Acceptance Criteria:**
- [ ] `TestCasesCoverageGalaxy` modal: 3 columns (BRD must-BRs → FRS specs → test plans) with bezier links; uncovered must-BRs and uncovered scenarios pulse red; header shows `Project coverage X% · n/m must-BRs tested`.
- [ ] `TestCasesTraceChip` on every case: color-coded chips per `tc_trace_kind` with hover tooltip (label + confidence) and click-to-jump; an unlink affordance edits the trace.
- [ ] Verify in browser using dev-browser skill.

---

## 4. Functional Requirements

**Data & context**
- FR-1: Extend `artifact_type` enum with `test_cases`; create `test_suites`, `test_plans`, `test_cases`, `test_case_traceability` (migration `0024`).
- FR-2: All versioned rows use the standard row mixin (version, is_current, is_locked, status, source, created_by) with `UNIQUE(document_id,row_key,version)`.
- FR-3: `test_case_traceability` is replace-all (not versioned), mirroring `frs_traceability`.
- FR-4: Add an `FrsLayer` to the context bundle; `artifact_type="test_cases"` loads BRD + FRS; readiness blocks until FRS validated.

**Generation**
- FR-5: Stage A `plan_journeys` produces one suite per module + one plan stub per spec.
- FR-6: Stage B `author_plan` runs once per FRS spec (modules parallel, semaphore=3; specs sequential, commit-per-spec, 360s timeout) and authors comprehensive multi-level cases + traceability.
- FR-7: Generation honors idempotency: existing row_keys preserved, locked + manual (`source='human'`) rows reproduced/preserved across regeneration.
- FR-8: All LLM calls route through the provider abstraction; `LLM_PROVIDER=mock` uses registered fixtures with zero Vertex/PageIndex calls.

**Traceability & coverage**
- FR-9: Every test case must carry ≥1 traceability row to an FRS element; plans carry a `frs_spec` trace + transitive `brd_business_requirement` traces.
- FR-10: `compute_testcase_coverage` returns per-spec/per-module/project coverage, uncovered elements, and `must_br_uncovered` via the multi-hop chain.
- FR-11: `GET /coverage` recomputes live on every call (no cache) so manual edits reflect immediately.

**Editing & control**
- FR-12: Every suite/plan/case property is editable (versioned, lock-aware, 409 on version conflict), deletable (soft), lockable/unlockable, restorable, with history.
- FR-13: `POST /plans/{plan}/cases` adds a manual case and persists its FRS link(s) as traceability (rejecting links to nonexistent FRS rows).
- FR-14: Validation produces tiered findings; `POST /validate` commits `status='validated'` + locks rows only when no blocking findings remain.
- FR-15: `GET /orphans` surfaces traceability whose target FRS row no longer exists (stale after FRS regen); never auto-deleted.

**UI/UX**
- FR-16: A locked-until-FRS-validated sidebar nav item opens a three-pane Module → Spec → Cases builder.
- FR-17: Inline-editable test-case table with colored type/priority badges, per-row Edit/History/Lock/Delete, and a schema-driven edit dialog (incl. a steps editor and tag inputs for assertions + refs).
- FR-18: An "Add test case" dialog with an FRS-element link picker (search FRs / scenarios / business rules by row_key + label).
- FR-19: A live generation theater showing phase, per-module progress bars, and the currently-authoring spec.
- FR-20: A Coverage Galaxy modal visualizing the BRD → FRS → Test chain, with uncovered nodes highlighted, plus provenance trace chips on every case.

---

## 5. Non-Goals (Out of Scope)

- **NG-1: No test execution / run tracking** (pass/fail/blocked per run). Schema is designed for a future `test_runs` table, but it is not built now.
- **NG-2: No automation-code generation** (Playwright/Cypress/etc.). Output is structured, human-readable test cases, not executable scripts.
- **NG-3: No PII handling** anywhere (project-wide non-goal — never reintroduce).
- **NG-4: No generation from a draft/unvalidated FRS.** The FRS-validated gate is mandatory.
- **NG-5: No new artifact type beyond test cases** (no test data fixtures generator, no environment/CI specs).
- **NG-6: No auto-deletion of orphaned traceability** on FRS regen — only detection + a relink/regenerate affordance.

---

## 6. Design Considerations (UI/UX — first-class)

The UI mirrors the existing FRS frontend (SWR polling, dedicated builder, three-pane layout, modal edit, trace chips, coverage galaxy, sonner toasts, lucide icons, Tailwind CSS-var design language) so it feels native.

**6.1 Workspace shell (three-pane, mirrors `FrsBuilderView`)**
```
┌───────────────────────────────────────────────────────────────────────────────────┐
│ Test Cases · Validated ✓ · PayHub             [Coverage] [Validate] [Export ▾]      │
├──────────────────────┬──────────────────────────────────────────┬───────────────────┤
│ SUITES / PLANS rail  │  PLAN PANEL                                │ COVERAGE drawer   │
│ ▸ Payments      92%  │  Suite: Payments · journey overview ▾      │ This spec 100% ▮▮ │
│   TP-M001-FRS001 ✓   │  Plan: Initiate Payment (M001-FRS001) P0   │ AS-1 ✓  AS-2 ✓    │
│   TP-M001-FRS002 ◐   │  Preconditions · Test data notes           │ FR-1 ✓  FR-2 ✗    │
│ ▸ Ledger        78%  │  ┌────┬──────────────┬────────┬─────────┐  │ Negative ✓        │
│ ▸ Cross-cutting 100% │  │TC- │ Title        │ Type   │ Traces  │  │ → traces BR-001   │
│ [+ Add plan]   ⌕     │  │001 │ Happy path…  │ e2e    │AS-1 FR1 │● │                   │
│                      │  │002 │ Reject neg…  │negative│AS-3 FR2 │● │                   │
│                      │  └────┴──────────────┴────────┴─────────┘  │                   │
│                      │  [+ Add test case]                         │                   │
└──────────────────────┴──────────────────────────────────────────┴───────────────────┘
```

**6.2 Inline editing & control.** Row hover reveals Edit (pencil) / History (clock) / Lock / Delete (trash). Edit opens `TestCaseRowEditDialog` (schema-driven: text, textarea, `test_type`/`priority` selects, tag inputs for `key_assertions` and `*_refs`, an ordered steps editor for multi-step e2e). Locked rows render at reduced opacity with a lock chip. Every property is reachable from this dialog.

**6.3 Add + link.** `AddTestCaseDialog` includes an FRS-element **link picker** (typeahead over FRs, acceptance scenarios, and business rules of the current spec, shown as row_key + label), enforcing ≥1 link before save.

**6.4 Live generation theater (mirrors `FrsConstructionTheater` + banner).**
```
Generating test plans …………………………………  ●  Phase 1/2 · plan_journeys
▸ Payments        ▓▓▓▓▓▓▓░░  5/7 specs
▸ Ledger          ▓▓▓░░░░░░  2/6 specs
▸ Cross-cutting   ▓▓▓▓▓▓▓▓▓  done
Now authoring: M001-FRS006 “Refund initiation” · 23 cases so far
```
Per-module bars + the "now authoring" line make the running step explicit at all times.

**6.5 Coverage Galaxy (mirrors `FrsCoverageGalaxy`, extended).** A 3-column SVG (BRD must-BRs → FRS specs → test plans) with cubic-bezier links; uncovered must-BRs and uncovered scenarios pulse red; header reads `Project coverage 86% · 15/18 must-BRs tested`; clicking a node filters the rail.

**6.6 Trace chips.** Color-coded by `tc_trace_kind` — `frs_acceptance_scenario` (pink), `frs_functional_requirement` (indigo), `frs_business_rule` (amber), `frs_screen` (sky), `brd_business_requirement` (green, transitive), `within_test_cases` (gray). Hover → tooltip (label + confidence); click → jump to the FRS element.

**6.7 Components to create** (`frontend/app/components/testcases/`): `TestCasesBuilderView`, `TestCasesEmptyState`, `TestCasesGenerationTheater`, `TestCasesGenerationBanner`, `TestCasesSuiteRail`, `TestCasesPlanPanel`, `TestCasesTable`, `TestCaseRowEditDialog`, `TestCaseRowActions`, `AddTestCaseDialog`, `TestCasesCoverageGalaxy`, `TestCasesTraceChip`, `TestCasesFindingsDrawer`. Plus `lib/api.ts` (`api.testcases.*`), `lib/types.ts`, `lib/testcases-manifest.ts`, sidebar + view branch in `app/projects/[id]/page.tsx`, and `--tc-*` tokens in `app/globals.css`.

---

## 7. Technical Considerations (rock-solid backend)

**7.1 Mirror the FRS engine verbatim.** Copy `upsert_frs_rows` → `upsert_tc_rows`, `_upsert_frs_traceability` → `_upsert_tc_traceability` (delete-then-insert per source row in `begin_nested()`), `generate_frs_all` → `generate_tc_all`. New files: `manifest/test_cases.py`, `skills/dspy_test_cases.py`, `artifacts/tc_orchestrator.py`, `artifacts/validators/test_cases.py`, `context/frs_layer.py`, `context/tc_coverage.py`, `api/test_cases.py`. Templates: `frs_orchestrator.py`, `dspy_frs.py`, `api/frs.py` (`/coverage` @889, `/validate` @248, dispatch+503 @752), `validators/frs.py`.

**7.2 Stage B granularity is per-spec, not per-module** — a per-module completion (3–15 specs × ~15–40 cases) truncates on `gemini-2.5-flash`; the FRS team already switched to per-spec. Loop per-spec inside per-module coroutines; commit after each spec so a late timeout never loses finished plans.

**7.3 Celery discipline.** Every async task wrapped in `_run_async()` (disposes the engine — prefork loop gotcha); dispatch via `workers/dispatch.py::dispatch()` (TCP pre-flight). Heavy LLM work never runs synchronously in the request path on the real provider.

**7.4 Gate reuse.** `require_artifact_validated("frs")` already exists (`deps.py:80`) — use it; do **not** write a new gate. Two-layer gating (deps decorator + bundle readiness) mirrors FRS-gates-on-BRD.

**7.5 BRD priority semantics.** `brd_business_requirements.priority` is the enum `must|should|could|wont`; "blocking" coverage keys off `priority=='must'` (matches the FRS coverage endpoint).

**7.6 Regeneration safety.** Stage B per-plan soft-delete scope excludes `source='human'` rows; LLM receives `locked_cases` to reproduce verbatim. Orphan detection (refs to non-active FRS rows) surfaces via the `orphan_case` validator + `GET /orphans`, never auto-deletes.

**7.7 Migration enum note.** `ALTER TYPE artifact_type ADD VALUE` may need to run outside a txn on older PG; use the `IF NOT EXISTS` form. Downgrade leaves the value in place (matches FRS/BRD migration practice).

**7.8 Coverage is computed, never stored.** Every `GET /coverage` recomputes from active rows + traceability, so manual additions and edits reflect with no cache invalidation.

---

## 8. Success Metrics

- **M1 — Coverage completeness:** ≥95% of FRS acceptance scenarios and FRs on P0/P1 specs are covered by ≥1 test case after a single generation pass on a seeded project.
- **M2 — Traceable must-BRs:** 100% of *must*-priority BRD requirements are reachable through the BRD → FRS → Test-Case chain (untested ones are explicitly listed, never silently missing).
- **M3 — Authoring speed:** a user can add a fully-linked manual test case in <3 interactions (open dialog → fill → pick FR link → save).
- **M4 — Progress transparency:** during generation the UI always names the currently-running step (phase + module + spec) — no blank/black-box state.
- **M5 — Deterministic CI:** the full module test suite passes under `LLM_PROVIDER=mock` with zero Vertex/PageIndex/network calls.
- **M6 — Regeneration safety:** 100% of locked and manual cases survive an AI regeneration of their plan.

---

## 9. Open Questions

- **OQ-1:** Should `export` produce per-spec markdown files matching the skill's template (`<frs-id>.md` + an index with a coverage summary), a single bundle, or both? (Plan assumes optional markdown export mirroring FRS.)
- **OQ-2:** Should uncovered *business rules* be MAJOR or MINOR? (Plan: MINOR, since rules are often covered implicitly by scenarios.)
- **OQ-3:** Coverage threshold for "spec fully covered" — strict 100% of elements, or a configurable threshold per priority tier?
- **OQ-4:** Do we want a one-click "regenerate affected plans" action when FRS changes orphan existing cases, or leave it manual per plan?
- **OQ-5:** Should responsive viewports be project-configurable defaults (e.g., set once in project settings) rather than authored per case?

---

## 10. Implementation map (files)

**Create (backend):** `alembic/versions/0024_test_cases_artifact.py` · `app/models/test_cases.py` (+register in `__init__.py`) · `app/services/artifacts/manifest/test_cases.py` · `app/services/skills/dspy_test_cases.py` · `app/services/artifacts/tc_orchestrator.py` · `app/services/artifacts/validators/test_cases.py` · `app/services/context/frs_layer.py` · `app/services/context/tc_coverage.py` · `app/api/test_cases.py` · `app/services/llm/fixtures/test_cases_plan_journeys.json` + `test_cases_author_plan.json`.

**Modify (backend):** `app/models/artifact.py` · `app/services/context/project_context.py` · `app/services/context/projection.py` · `workers/tasks.py` · `app/main.py` · `app/services/llm/mock_provider.py`.

**Create/modify (frontend):** `lib/api.ts`, `lib/types.ts`, `lib/testcases-manifest.ts`, `app/projects/[id]/page.tsx`, `app/globals.css`, `app/components/testcases/*` (§6.7).

**Verification:** mock-first backend tests (generate → coverage → add+link → edit/delete/history → validate → regenerate-survives-manual); `make typecheck && make lint && make test-be`; live UI walkthrough via dev-browser; optional real-Vertex smoke. Full detail in the companion plan.
