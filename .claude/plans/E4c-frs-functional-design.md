# E4c · Part 2 — FRS Functional Design (Stage B) · Implementation Plan

> **Companion to** `.claude/prd/prd-e4c-frs-functional-design.md` (the product spec).
> That doc says **WHAT** to build; this doc says **HOW** — file by file, table by
> table, component by component — with the visual design language and the
> rugged-backend invariants spelled out.
>
> **Reference skill**: `reference_mds/skills/frs-builder/guidelines/functional-design.md`
> + `templates/frs-template.md`. Stage B turns each Stage A backlog stub into a
> development-ready FRS following that 12-section template.

---

## Context

Stage A (already shipped) decomposed the validated BRD into 5–12 business-capability
modules + an FRS backlog of stub specs. Each stub has a title, priority, BR refs, and
nothing else.

Stage B turns each stub into a full FRS document covering:
- Narrative (intent + 1–2 paragraphs)
- §1 UI specification (screens, components, data mapping) — gated by Figma link
- §2 Backend spec (endpoints with request/response/errors/security/operational)
- §3 Data spec (entities with columns, keys, indexes, relationships, cache)
- §4 Cross-cutting (business rules, security)
- Independent test
- ≥6 acceptance scenarios (≥2 negative)
- ≥1 functional requirement (each tracing to ≥1 scenario; each scenario to ≥1 FR)
- Data & validation, errors & edge cases, observability
- Optional implementation tasks
- Traceability (replace-all, not versioned)

When Stage B is complete, the user validates → all rows lock → markdown export
becomes available → Test Cases artifact unlocks.

**Why this matters now**: Stage A's "Continue to Stage 2" banner currently dead-ends.
This plan turns that banner into the real handoff to Stage B's parallel per-module
generation.

**Two product principles drive every decision below** (inherited from Stage A):
- **Rugged backend**: idempotent generation, atomic JSONB merges, per-row savepoints,
  row-level locking, soft-delete by status, mock-first DSPy, dispose-per-task
  connection pool, optimistic concurrency on edits, parallel module designs capped
  at 3 concurrent Vertex calls.
- **Brilliant UI**: every artifact row Edit/Lock/Delete on hover via the generic
  `FrsRowEditDialog`; trace chips everywhere; collapsible sections for calm density;
  per-module nested rail; coverage galaxy; two-phase generation viz; findings
  drawer with one-click accept-fix; confetti on validate. All motion gated by
  `useReducedMotion()`.

---

## 1. What's already in place (huge head-start from Stage A)

Stage B reuses far more than it builds. Key reuses:

| Existing | Reuse strategy |
|---|---|
| `models/frs.py` — all 14 tables, including the 8 Stage B sub-row tables | **No changes** — Stage A migration created them; Stage B just writes to them |
| `alembic/versions/0019_frs_artifact.py` — 15 tables + 8 enums | **No new migration** — `frs_http_method` and `frs_trace_kind` enums already exist |
| `manifest/frs.py` — `FRS_TABLE_MAP` and `FRS_TYPED_COLS` entries for all 8 Stage B tables | **No table-registration work** — they're already wired |
| `frs_orchestrator.py::upsert_frs_rows` — savepoint-per-row versioned upsert with diff detection + lock preservation + scope-bounded soft-delete | **Reused unchanged** for all 8 Stage B sub-row tables |
| `frs_orchestrator.py::_ensure_frs_document` — race-safe get-or-create | **Reused** |
| `frs_orchestrator.py::_coerce_row_types` — string→int coercion | **Reused**; `frs_acceptance_scenarios.scenario_index` already registered |
| Generic API row endpoints — `POST /artifacts/frs/{table}/{row_id}/edit \| delete \| unlock \| restore`, `GET .../history` | **Inherit unchanged** — every Stage B sub-row gets edit/lock/delete/restore for free via the FRS_TABLE_MAP lookup |
| `FrsRowEditDialog` (built this session) — schema-driven generic editor | **Reused** for every Stage B sub-row type, just provide the field schema per type |
| `validators/frs.py` — `_finding`, `_active_rows`, `_GROUP_ORDER`, the 5-group hierarchy | **Reused** — append Stage B rule families to the same validator entrypoint |
| `dspy_frs.py::_is_mock`, `_load_fixture`, `_configure` | **Reused** |
| `BrdLayer` + `gather_project_context(artifact_type='frs')` | **Reused** — Stage B uses the same bundle |
| `_run_async` Celery wrapper, dispatch pattern, audit-light logging | **Reused** |
| `FrsTraceChip` (Stage A) | **Extended** with new target_kind palette for NFR / app_fact / doc_section / discover_qa / within_frs |
| `FrsModuleRail` | **Extended** to nest individual spec rows under each module |
| `FrsBuilderView` state machine | **Extended** with three new surfaces (FrsSpecPanel, FrsFindingsDrawer, FrsCoverageGalaxy) |
| `FrsConstructionTheater` (Stage A) | **Wrapped** by a new `FrsTwoPhaseGenerationViz` that adds Phase B parallel module bars |
| `BrdConfettiBurst` | **Reused** for the validate moment |

**Net new tables**: 0. **Net new migrations**: 0. **Net new SQL machinery**: 1
helper (`_upsert_frs_traceability` for replace-all semantics on the non-versioned
trace table).

---

## 2. Architecture & key design decisions

### 2.1 Two-stage pipeline (Stage A done, Stage B is the focus here)

```
RU validated ─▶ Concept Brief ─▶ BRD validated ─▶ Stage A (modularize) ─▶ Stage B (design)
                                                  ─ done ─                  ─ this plan ─

Stage B parallel fan-out:
  Module 1 ── design_module ─┐
  Module 2 ── design_module ─┤  asyncio.Semaphore(3)
  Module 3 ── design_module ─┘
  Module 4 ── design_module ──→ waits for slot
  Module 5 ── design_module ──→ waits for slot
```

Each `design_module` call is ONE DSPy invocation that produces all of that module's
specs in one shot (including their screens, components, endpoints, entities,
business rules, scenarios, FRs, decisions, traceability rows).

### 2.2 The 8 design decisions baked into Stage B

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **Figma link is link-only (no MCP fetch in v1)** | Captured per-screen as `figma_link`. Downstream coding agent fetches design when generating code. v2+ can add MCP fetch behind the same `figma_link` field with no schema change. |
| 2 | **Skip-Figma always available** | Sentinel `figma_link='__none__'` unblocks the user. Validation surfaces as **warning** (not major), so doesn't block Validate. |
| 3 | **[SPEC-DECISION] non-blocking** | AI picks `recommended_index` and authors the spec coherently against that pick. Open decisions are **warnings**. User confirms / overrides / dismisses later. |
| 4 | **Section omission allowed when justified** | Backend-only spec omits §1; pure UI-aggregation omits §2 + §3; stateless omits §3. AI must write a one-line justification in `narrative`. Validator only complains when module interfaces indicate the section *should* exist (e.g., module has `interface_kind='ui_surface'` but spec has 0 screens). |
| 5 | **Per-row locking everywhere** | The Lock checkbox on `FrsRowEditDialog` toggles the row's `is_locked`. Locking a spec preserves the spec metadata; locking a sub-row (scenario/FR/endpoint/entity) preserves that sub-row. Both kinds of locks survive regeneration. |
| 6 | **Per-spec regeneration preserves locked sub-rows** | Orchestrator gathers `locked_specs` JSON + each spec's locked sub-rows; passes to LLM as input AND post-applies them in `_persist_design_module_result` so a misbehaving LLM can't blow them away. |
| 7 | **Traceability is replace-all per regeneration** | `frs_traceability` has no `VersionedRowMixin`. On regen, the helper deletes existing rows for the source then bulk-inserts the new set. Versioning would create row explosion with no UX benefit. |
| 8 | **`completeness ≥ 90` is the AI's quality floor** | Below 90 surfaces as a **minor** finding pointing the user at `narrative` / `open_questions` to address gaps. Confidence + completeness together drive UI signal density. |

### 2.3 Rugged backend invariants (non-negotiable — inherited from Stage A)

Every implementation step in §3 must satisfy:

1. **Atomicity per row table**: `upsert_frs_rows()` uses `db.begin_nested()` per row;
   a single bad LLM-emitted row never poisons the whole spec persistence.
2. **JSONB `unit_status` merge is atomic**: every progress update uses
   `SET unit_status = COALESCE(unit_status,'{}'::jsonb) || CAST(:patch AS jsonb)`.
   Concurrent module designs can write `design_mod_<mod_key>` keys without clobbering.
3. **Idempotency**: re-running `design_module` with no input changes produces 0 new
   versions. Diff detection in `_row_unchanged` enforces this.
4. **Lock semantics**: rows with `is_locked=True` are preserved verbatim AND the
   orchestrator post-applies the lock state after the LLM call to guard against
   the AI ignoring the `locked_specs` input.
5. **Soft delete only**: never `DELETE FROM frs_*` in code paths; `status='removed'`.
   Hard delete is a `platform_admin`-only `POST /destroy` endpoint (out of v1 scope).
6. **Per-Celery-task session**: every Stage-B Celery task goes through `_run_async()`
   which `engine.dispose()`s after — prevents "Future attached to different loop".
7. **Per-module concurrency cap**: `asyncio.Semaphore(3)` in `generate_frs_all`
   caps Vertex calls to 3 modules in flight. Each module gets its own
   `AsyncSessionLocal()` (not the parent's session) to avoid event-loop binding.
8. **Mock-first**: `_is_mock()` short-circuit returns the fixture before any
   network call. CI/tests stay green with zero Vertex.
9. **Optimistic concurrency**: every Stage B `editRow` accepts `expected_version`;
   409 on conflict.
10. **Traceability replace-all is transactional**: `_upsert_frs_traceability` runs
    in `db.begin_nested()` — partial replaces never leave the source half-traced.
11. **Audit-light**: every key transition logs a structured event:
    `frs.design_module.start`, `frs.design_module.complete`,
    `frs.design_module.timeout`, `frs.spec.regenerate`, `frs.figma_link.set`,
    `frs.decision.resolve`, `frs.validate.run`, `frs.validate.commit`,
    `frs.export.zip`.

### 2.4 Brilliant UI principles (UX north stars — extended for Stage B)

1. **Provenance is the product**: every spec shows trace chips for BR / NFR /
   discover-Q / app-fact / doc-section. Click → popover with source context.
2. **Every artifact row Edit/Lock/Delete on hover** — the user's explicit
   requirement. Each sub-row gets the same three-icon cluster (Pencil / Lock /
   Trash) revealed on hover, powered by the generic `FrsRowEditDialog`.
3. **Hierarchy via Layer is obvious**: spec cards inherit module Layer accent
   (foundation amber / vertical emerald / cross-cutting sky).
4. **State is felt**: two-phase generation viz shows Phase A ✓ + Phase B as
   stacked module bars filling in parallel.
5. **Editing is frictionless**: every textarea field uses `FrsRowEditDialog` with
   schema; every list-of-rows section gets `[+ Add]` inline + per-row
   `[Edit] [Lock] [Trash]`.
6. **Locks are reassuring**: 🔒 + amber ring; tooltip "Locked — preserved on regenerate".
7. **Findings are actionable**: each finding has `[Accept fix]` (mechanical),
   `[Jump to row →]` (smooth-scroll + 600ms amber pulse), or `[Edit manually]`.
8. **Density is calm**: default-collapsed sections except Intent + Acceptance
   Scenarios (the two most-read sections). User-collapsed state persists in
   sessionStorage per spec key.
9. **Coverage galaxy is the truth view**: BR↔FRS bezier graph; uncovered
   must-priority BRs glow red. Single click from header's `✦ Coverage`.
10. **Motion is purposeful**: same 280/180/220 ms vocabulary as Stage A. All
    motion gated by `useReducedMotion()`.

---

## 3. Backend implementation (file by file)

### 3.1 Manifest extension

**File**: `backend/app/services/artifacts/manifest/frs.py` (EXTEND)

Add the Stage B unit spec and append to the manifest list:

```python
FRS_STAGE_B_UNIT = FrsUnitSpec(
    unit_key="design_module",
    phase="B",
    label="Design module FRSes",
    writes=[
        "frs_specs",                       # full form
        "frs_screens", "frs_ui_components",
        "frs_endpoints",
        "frs_data_entities",
        "frs_business_rules",
        "frs_acceptance_scenarios",
        "frs_functional_requirements",
        "frs_spec_decisions",              # spec-scoped
        "frs_traceability",                # replace-all
    ],
    depends_on=["modularize"],
    discover_question_keys=["frs_4a", "frs_5a", "frs_6a", "frs_6b", "frs_7a", "frs_8a"],
    timeout_seconds=120,                   # per module, not per spec
)

FRS_MANIFEST: list[FrsUnitSpec] = [FRS_STAGE_A_UNIT, FRS_STAGE_B_UNIT]
```

No changes needed to `FRS_TABLE_MAP` or `FRS_TYPED_COLS` — Stage A already wired
all 8 Stage B tables.

### 3.2 DSPy signature + fixture

**File**: `backend/app/services/skills/dspy_frs.py` (EXTEND)

Add the Pydantic schema (as specified in PRD §6.2 verbatim) and the runner. Key
structural points:

```python
class FrsSpecFullOutput(BaseModel):
    row_key: str                       # matches the backlog stub's row_key
    title: str
    priority: Literal["P0","P1","P2","P3"]
    layer: Literal["foundation","vertical","cross_cutting"]
    br_refs: list[str]
    nfr_refs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    narrative: str
    screens: list[FrsScreenRow] = Field(default_factory=list)
    ui_components: list[FrsUiComponentRow] = Field(default_factory=list)
    endpoints: list[FrsEndpointRow] = Field(default_factory=list)
    data_entities: list[FrsDataEntityRow] = Field(default_factory=list)
    business_rules: list[FrsBusinessRuleRow] = Field(default_factory=list)
    acceptance_scenarios: list[FrsAcceptanceScenarioRow] = Field(..., min_length=6)
    functional_requirements: list[FrsFunctionalRequirementRow] = Field(..., min_length=1)
    spec_decisions: list[FrsSpecDecisionRow] = Field(default_factory=list)
    traceability: list[FrsTraceabilityRow]
    independent_test: str
    data_and_validation: str
    errors_and_edge_cases: str
    observability: str
    implementation_tasks: list[dict] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high","medium","low"]
    ui_blocked_reason: str | None = None    # "figma_link_required" if UI omitted

class FrsDesignModuleOutput(BaseModel):
    specs: list[FrsSpecFullOutput]
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high","medium","low"]


class FrsDesignModuleSignature(dspy.Signature):
    """[Verbatim docstring from PRD §6.2 — HARD RULES, FIGMA-LINK GATE,
    [SPEC-DECISION] AMBIGUITY, DEPENDS_ON, TRACEABILITY, SECTION-OMISSION RULE]"""
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    module_row_key: str = dspy.InputField()
    module_context: str = dspy.InputField()
    other_modules_summary: str = dspy.InputField()
    brd_context: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    source_sections: str = dspy.InputField()
    qa_pairs: str = dspy.InputField()
    current_specs: str = dspy.InputField()
    locked_specs: str = dspy.InputField()
    resolved_decisions: str = dspy.InputField()
    result: FrsDesignModuleOutput = dspy.OutputField()


class FrsDesignModuleModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(FrsDesignModuleSignature)
    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_design_module(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("frs_design_module")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: FrsDesignModuleModule()(**kwargs))
```

### 3.3 Mock fixture

**File**: `backend/app/services/llm/fixtures/frs_design_module.json` (NEW)

Hand-written fixture covering **one module's worth of specs** (3 specs typical) so
the mock test suite exercises every code path:

- 1 spec with full UI (screens + components + Figma link)
- 1 spec UI-blocked (`ui_blocked_reason='figma_link_required'`)
- 1 spec pure-backend (omit §1)
- 1 spec with 1 open `spec_decision`
- All specs have **≥6 acceptance_scenarios with ≥2 negative**
- All specs have **≥1 functional_requirement**
- All scenarios → FR refs, all FRs → scenario refs
- All specs have ≥1 traceability row to a BR
- One spec has `depends_on=["M000-FRS001"]` (cross-cutting)
- `completeness: 92`, `confidence: "high"`

Use the claims-chatbot BR row_keys (`BR-001`..`BR-008`) for trace targets so the
fixture works against the existing seeded project.

### 3.4 Orchestrator extensions

**File**: `backend/app/services/artifacts/frs_orchestrator.py` (EXTEND)

Five new public functions plus internal helpers:

```python
async def generate_frs_all(project, db) -> dict:
    """Full pipeline: Stage A then Stage B (parallel, cap 3)."""
    doc = await _ensure_frs_document(project.id, db)
    doc.unit_status = {}; doc.status = "generating"; await db.commit()

    bundle = await gather_project_context(project.id, db,
                                          artifact_document_id=doc.id,
                                          artifact_type="frs")

    # Stage A
    await generate_frs_modularize(project, doc, bundle, db)
    await db.commit()

    modules = await _current_frs_modules(doc.id, db)

    # Stage B — parallel
    sem = asyncio.Semaphore(3)
    async def _design(mod):
        async with sem:
            async with AsyncSessionLocal() as unit_db:
                unit_doc = await unit_db.get(ArtifactDocument, doc.id)
                await generate_frs_design_module(
                    project, mod.row_key, unit_doc, bundle, unit_db)
                await unit_db.commit()
    await asyncio.gather(*[_design(m) for m in modules])

    # Finalize
    async with AsyncSessionLocal() as fin_db:
        fdoc = await fin_db.get(ArtifactDocument, doc.id)
        fdoc.status = "in_interview"
        await fin_db.commit()
    return await get_frs_detail(project.id, db)


async def generate_frs_design_module(
    project, module_row_key, doc, bundle, db,
    *, target_spec_row_key: str | None = None, ui_only: bool = False,
) -> dict:
    """One module's worth of specs. Returns the DSPy output dict.

    target_spec_row_key: if set, only persist that spec (single-spec regen).
    ui_only: if True, only update screens + ui_components (for figma-link flow).
    """
    # 1. set _current_unit to design_mod_<key> so the theater knows
    # 2. serialize the module context (children + cross-module summary)
    # 3. pull current_specs, locked_specs, resolved_decisions
    # 4. depth_search the project docs for this module
    # 5. await asyncio.wait_for(run_design_module(...), timeout=120)
    # 6. filter to target_spec_row_key if set
    # 7. persist via _persist_design_module_result OR _persist_ui_only_result
    # 8. emit messages for ui_blocked + open spec_decisions
    # 9. atomic JSONB merge: design_mod_<key> = {completeness, confidence}
    # 10. clear _current_unit


async def _persist_design_module_result(document_id, specs, db):
    """Route each spec's content to the 9 spec-level tables.

    For each spec:
      1. upsert_frs_rows('frs_specs', ...)   # promote stub → full
      2. if not ui_blocked: upsert screens + ui_components (scoped delete)
      3. upsert endpoints (scoped delete by spec_row_key)
      4. upsert data_entities (scoped delete by spec_row_key)
      5. upsert business_rules (scoped delete)
      6. upsert acceptance_scenarios (scoped delete)
      7. upsert functional_requirements (scoped delete)
      8. upsert spec_decisions (spec-scoped)
      9. _upsert_frs_traceability(...)        # replace-all per source
    """


async def _persist_ui_only_result(document_id, specs, db):
    """Used by the figma-link handler: only touch screens + ui_components for the
    target spec. Leaves endpoints/entities/scenarios/etc. untouched.
    """


async def regenerate_frs_spec(project, spec_row_key, db) -> dict:
    """Re-run design_module narrowed to one spec.

    Internally calls generate_frs_design_module with target_spec_row_key set.
    Used by the [Regenerate] button on the spec panel header.
    """


async def set_figma_link(project, spec_row_key, link: str, user_id, db) -> dict:
    """Set figma_link on every screen of a spec, or sentinel '__none__' to skip.

    Flow (per PRD §6.4):
      - if link == "__none__": set sentinel on each screen; no regen
      - if no screens yet: create one placeholder screen with the link
      - else: edit each existing screen to set the link
      - trigger UI-only regen via generate_frs_design_module(... ui_only=True)
    """
```

**New helper for traceability replace-all**:

```python
async def _upsert_frs_traceability(
    document_id, source_table: str, source_row_key: str,
    rows: list[dict], db: AsyncSession,
):
    """Delete existing traceability for (source_table, source_row_key), then bulk
    insert the new set. Atomic via db.begin_nested(). Skips empty rows.
    """
    async with db.begin_nested():
        await db.execute(sa_text(
            "DELETE FROM frs_traceability "
            "WHERE document_id = :doc AND source_table = :st AND source_row_key = :sk"
        ), {"doc": str(document_id), "st": source_table, "sk": source_row_key})
        for r in rows:
            if not r.get("target_ref"):
                continue
            db.add(FrsTraceability(
                id=uuid.uuid4(), document_id=document_id,
                source_table=source_table, source_row_key=source_row_key,
                target_kind=r["target_kind"], target_ref=r["target_ref"],
                target_label=r.get("target_label", ""),
                confidence=r.get("confidence", "medium"),
            ))
```

**New helper for cycle detection** (used by validator):

```python
def _has_depends_on_cycle(specs: list[FrsSpec]) -> bool:
    """DFS on the depends_on graph. Returns True if any cycle exists."""
    graph = {s.row_key: set(s.depends_on or []) for s in specs}
    WHITE, GREY, BLACK = 0, 1, 2
    color = {k: WHITE for k in graph}
    def dfs(n):
        if color[n] == GREY: return True
        if color[n] == BLACK: return False
        color[n] = GREY
        for nb in graph.get(n, ()):
            if nb in color and dfs(nb): return True
        color[n] = BLACK
        return False
    return any(dfs(n) for n in list(graph) if color[n] == WHITE)
```

### 3.5 Validator — Stage B rules

**File**: `backend/app/services/artifacts/validators/frs.py` (EXTEND)

Add `_validate_stage_b` and call it from the existing entrypoint after Stage A
rules. Severity per PRD §6.6:

| Severity | check_id | Trigger |
|---|---|---|
| critical | `module_empty` | Module has 0 specs after Stage B |
| critical | `depends_on_cycle` | Cyclic `depends_on` graph |
| major | `spec_no_br_trace` | Spec has no `frs_traceability` row with `target_kind='brd_business_requirement'` |
| major | `figma_link_missing` | Module has `interface_kind='ui_surface'` but no screen with a real (non-sentinel) figma_link |
| major | `too_few_scenarios` | <6 acceptance scenarios |
| major | `too_few_negative_scenarios` | <2 negative scenarios |
| major | `fr_no_scenario` | FR has 0 `scenario_refs` matching existing scenarios |
| major | `scenario_no_fr` | Scenario has 0 `fr_refs` matching existing FRs |
| major | `depends_on_missing` | Spec lists a depends_on row_key that doesn't exist |
| minor | `spec_completeness` | `completeness < 90` |
| coverage | `br_uncovered_in_frs` | A BR row_key has no traceability from any spec (priority='must' is reported strongly; others informational) |
| warnings | `open_spec_decision` | A `frs_spec_decisions` row with `resolution_status='open'` |
| warnings | `under_decomposed_module` | A module has only 1 spec |
| warnings | `figma_link_skipped` | `figma_link='__none__'` (informational) |

`POST /validate` commits only when critical + major = 0. The
`platform_admin`-only override path bypasses this for emergencies.

### 3.6 API endpoints

**File**: `backend/app/api/frs.py` (EXTEND)

Add Stage-B routes (the generic row CRUD endpoints from Stage A handle every
sub-row table; no per-table routes needed):

```
POST   /artifacts/frs/modules/{mod_row_key}/design            # re-run module design
POST   /artifacts/frs/specs/{spec_row_key}/regenerate         # re-run one spec
                                                              #   body: {scope: 'full'|'ui_only'}
POST   /artifacts/frs/specs/{spec_row_key}/figma-link         # set link; UI-only regen
                                                              #   body: {link: str}
                                                              #     link='__none__' = skip
POST   /artifacts/frs/decisions/{dec_row_key}/resolve         # spec or module-scoped
                                                              #   body: {user_chosen_index, action}
GET    /artifacts/frs/validate                                # findings (read-only)
POST   /artifacts/frs/validate                                # commit (locks, status=validated)
GET    /artifacts/frs/coverage                                # BR↔FRS coverage map
GET    /artifacts/frs/export                                  # markdown zip
```

All POST mutations return the full FRS detail (mirror of Stage A pattern) so the
client doesn't need a second GET.

**Generic CRUD endpoints (already exist from Stage A) handle**:
- `POST .../{table}/{row_id}/edit` — works for every Stage B sub-row table via FRS_TABLE_MAP
- `POST .../{table}/{row_id}/delete` — soft delete
- `POST .../{table}/{row_id}/unlock`
- `POST .../{table}/{row_id}/restore`
- `GET  .../{table}/{row_id}/history`

This is the architectural reason the user's "every row editable + deletable"
requirement is essentially free.

### 3.7 Exporter

**File**: `backend/app/services/artifacts/exporters/frs.py` (NEW)

```python
async def build_frs_export_zip(project_id, db) -> bytes:
    """Build the markdown bundle (zip) per PRD §6.7.

    Layout:
      README.md                                # overview + counts + traceability summary
      modules/<NN>-<slug>.md                   # rendered from module-template.md
      specs/<row_key_lower>-<slug>.md          # rendered from frs-template.md
      traceability/
        br-to-frs.md
        nfr-to-frs.md
        module-to-frs.md
        matrix.csv                             # flat dump of frs_traceability
    """
```

The renderer follows `reference_mds/skills/frs-builder/templates/frs-template.md`
exactly. JSONB fields (request_spec, response_spec, columns, etc.) are flattened
to bulleted lists for readability.

**Endpoint**:
```python
@router.get("/projects/{project_id}/artifacts/frs/export")
async def export_frs(...):
    zip_bytes = await build_frs_export_zip(project_id, db)
    return Response(
        zip_bytes, media_type="application/zip",
        headers={"Content-Disposition":
                 f'attachment; filename="frs-export-{project_id}-{ts}.zip"'},
    )
```

### 3.8 Celery tasks

**File**: `backend/workers/tasks.py` (EXTEND)

Three new tasks (mirroring Stage A's `generate_frs` pattern, all going through
`_run_async`):

```python
@celery_app.task(name="workers.tasks.regenerate_frs_module", bind=True, max_retries=2)
def regenerate_frs_module(self, project_id, module_row_key):
    return _run_async(_regenerate_frs_module(project_id, module_row_key))

@celery_app.task(name="workers.tasks.regenerate_frs_spec", bind=True, max_retries=2)
def regenerate_frs_spec(self, project_id, spec_row_key):
    return _run_async(_regenerate_frs_spec(project_id, spec_row_key))

@celery_app.task(name="workers.tasks.incorporate_frs_answer", bind=True, max_retries=2)
def incorporate_frs_answer(self, project_id, target_spec_row_key=None):
    return _run_async(_incorporate_frs_answer(project_id, target_spec_row_key))
```

Each `_xxx` async helper opens its own `AsyncSessionLocal()`, loads the project,
calls the orchestrator, handles failure by resetting `status='generating'` → `in_interview`
(same recovery pattern as `_generate_frs`).

**File**: `backend/workers/dispatch.py` (EXTEND)

Register the three new task names.

### 3.9 Backend tests

**File**: `backend/tests/test_frs_design_module.py` (NEW)

```python
async def test_design_module_smoke():
    """Full pipeline against fixture: counts match expectations."""

async def test_design_module_is_idempotent():
    """2nd call with same input → 0 new versions."""

async def test_design_module_preserves_locked_spec():
    """Lock a spec, regenerate; spec preserved verbatim."""

async def test_design_module_preserves_locked_scenarios():
    """Lock 2 scenarios, regenerate; those 2 preserved exactly."""

async def test_figma_link_unblocks_ui_section():
    """Spec with ui_blocked_reason; POST figma-link triggers UI-only regen;
    screens + ui_components populated; other sub-rows unchanged."""

async def test_figma_link_skip_sentinel():
    """POST figma-link with '__none__'; figma_link sentinel set on screens;
    warning visible, validate still possible."""

async def test_spec_decision_resolve_overridden_triggers_regen():
    """Resolve decision with action='overridden' → regen scheduled."""

async def test_traceability_replace_all_semantics():
    """Regenerate a spec; old traceability rows for that source gone, new ones present."""

async def test_validate_gate_refuses_with_blocking_finding():
    """Inject a major finding; POST /validate → 409; status stays in_interview."""

async def test_validate_commit_locks_all_rows():
    """0 blocking findings; POST /validate → all current rows is_locked=True;
    doc.status='validated'."""

async def test_export_zip_structure():
    """GET /export returns zip with README + modules/ + specs/ + traceability/."""

async def test_parallel_module_design_atomicity():
    """3 concurrent design_module calls on different modules → no row corruption."""

async def test_per_celery_task_session_engine_disposed():
    """Run regenerate_frs_spec twice in same process; second succeeds without
    event-loop binding error."""
```

**File**: `backend/tests/test_frs_validator_stage_b.py` (NEW)

One test per rule listed in §3.5 (~14 tests), each constructing a minimal FRS
state and asserting the expected finding appears with correct severity.

### 3.10 Observability events

Append to existing FRS audit channels:

| Event | Fields | Triggered |
|---|---|---|
| `frs.design_module.start` | doc_id, module_row_key, locked_spec_count | Before LLM call |
| `frs.design_module.complete` | doc_id, module_row_key, spec_count, completeness, confidence | After persist |
| `frs.design_module.timeout` | doc_id, module_row_key | LLM exceeded 120s |
| `frs.spec.regenerate` | doc_id, spec_row_key, scope (full/ui_only) | regenerate_frs_spec called |
| `frs.figma_link.set` | doc_id, spec_row_key, link_type (real/skip) | set_figma_link called |
| `frs.decision.resolve` | doc_id, decision_row_key, action, chosen_index | resolve called |
| `frs.validate.run` | doc_id, finding_counts | GET /validate |
| `frs.validate.commit` | doc_id, locked_row_count | POST /validate succeeds |
| `frs.export.zip` | doc_id, byte_size, spec_count | GET /export |

---

## 4. Frontend implementation (file by file)

### 4.1 Visual tokens (extensions to Stage A)

**File**: `frontend/app/globals.css` (EXTEND `:root`)

```css
:root {
  /* HTTP method colour codes (FrsEndpointCard) */
  --frs-method-get:    #16A34A;  /* green-600 */
  --frs-method-post:   #2563EB;  /* blue-600 */
  --frs-method-put:    #D97706;  /* amber-600 */
  --frs-method-patch:  #7C3AED;  /* violet-600 */
  --frs-method-delete: #DC2626;  /* red-600 */

  /* Trace chip extensions (new target_kind values) */
  --frs-trace-nfr-bg:        #FEF3C7; --frs-trace-nfr:        #B45309; --frs-trace-nfr-border:        #FCD34D;
  --frs-trace-app-bg:        #DBEAFE; --frs-trace-app:        #1E40AF; --frs-trace-app-border:        #93C5FD;
  --frs-trace-doc-bg:        #E0F2FE; --frs-trace-doc:        #0369A1; --frs-trace-doc-border:        #7DD3FC;
  --frs-trace-qa-bg:         #EDE9FE; --frs-trace-qa:         #6D28D9; --frs-trace-qa-border:         #C4B5FD;
  --frs-trace-within-bg:     #F3E8FF; --frs-trace-within:     #6B21A8; --frs-trace-within-border:     #D8B4FE;

  /* Coverage galaxy */
  --frs-coverage-covered:    var(--accent);
  --frs-coverage-uncovered:  #DC2626;
  --frs-coverage-uncovered-glow: rgba(220, 38, 38, 0.40);

  /* Two-phase generation viz */
  --frs-phase-a-bg:    var(--accent-subtle);
  --frs-phase-a-bar:   var(--accent);
  --frs-phase-b-bg:    #DBEAFE;
  --frs-phase-b-bar:   #2563EB;
  --frs-phase-b-done:  var(--accent);
}
```

### 4.2 Types

**File**: `frontend/lib/types.ts` (EXTEND)

Add row types for the 8 Stage B sub-tables (mirroring backend Pydantic shapes):
`FrsScreenRow`, `FrsUiComponentRow`, `FrsEndpointRow`, `FrsDataEntityRow`,
`FrsBusinessRuleRow`, `FrsAcceptanceScenarioRow`, `FrsFunctionalRequirementRow`,
`FrsTraceabilityRow`, plus `FrsSpecHydrated` (spec + all sub-rows inline) and
`FrsCoverage` (for the galaxy modal).

Each row type extends `FrsRowBase` (id, document_id, row_key, version,
is_current, is_locked, status, source, created_by, created_at) — already
defined in Stage A.

### 4.3 Manifest extensions

**File**: `frontend/lib/frs-manifest.ts` (EXTEND)

```ts
export const FRS_HTTP_METHOD_STYLES: Record<string, {color: string; bg: string}> = {
  GET:    { color: 'var(--frs-method-get)',    bg: '#DCFCE7' },
  POST:   { color: 'var(--frs-method-post)',   bg: '#DBEAFE' },
  PUT:    { color: 'var(--frs-method-put)',    bg: '#FEF3C7' },
  PATCH:  { color: 'var(--frs-method-patch)',  bg: '#EDE9FE' },
  DELETE: { color: 'var(--frs-method-delete)', bg: '#FEE2E2' },
}

// Extend FRS_TRACE_KIND_STYLES with the new target_kinds (nfr_driver, app_fact,
// doc_section, discover_qa, within_frs) using the CSS tokens defined in §4.1.
```

### 4.4 API client

**File**: `frontend/lib/api.ts` (EXTEND `api.frs.*`)

```ts
api.frs.designModule = (projectId, moduleRowKey) =>
  apiFetch(`/api/projects/${projectId}/artifacts/frs/modules/${moduleRowKey}/design`,
           { method: 'POST' })

api.frs.regenerateSpec = (projectId, specRowKey, scope: 'full'|'ui_only' = 'full') =>
  apiFetch(`/api/projects/${projectId}/artifacts/frs/specs/${specRowKey}/regenerate`,
           { method: 'POST', body: JSON.stringify({ scope }) })

api.frs.setFigmaLink = (projectId, specRowKey, body: { link: string }) =>
  apiFetch(`/api/projects/${projectId}/artifacts/frs/specs/${specRowKey}/figma-link`,
           { method: 'POST', body: JSON.stringify(body) })

api.frs.coverage = (projectId) =>
  apiFetch<FrsCoverage>(`/api/projects/${projectId}/artifacts/frs/coverage`)

api.frs.export = (projectId) =>
  authedFetch(`/api/projects/${projectId}/artifacts/frs/export`).then(r => r.blob())
```

`api.frs.validate` (GET=findings read-only, POST=commit) already in Stage A's
surface; reused.

### 4.5 The new frontend surfaces

#### S6 — Two-phase generation theater

**File**: `frontend/app/components/frs/FrsTwoPhaseGenerationViz.tsx` (NEW)

Replaces `FrsConstructionTheater` when the full pipeline runs. Reuses Stage A
theater for the Phase A summary, then adds Phase B as parallel module bars:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Phase A — Modularization                              ✓ Complete    │
│  5 modules · 18 backlog stubs · 14 BRs covered                       │
│  ───────────────────────────────────────────────────────────────     │
│                                                                       │
│  Phase B — Per-module design               (3 of 5 modules running)  │
│                                                                       │
│   ▰▰▰▰▰▰▰▰▱▱  MOD-001 User Onboarding     · 2 of 3 specs · ◐ designing │
│   ▰▰▰▰▰▰▰▰▰▰  MOD-002 Authentication     · 3 of 3 specs · ✓          │
│   ▰▰▰▰▰▱▱▱▱▱  MOD-003 Notifications      · 2 of 4 specs · ◐ designing │
│   ▱▱▱▱▱▱▱▱▱▱  MOD-004 Reporting          · waiting…                  │
│   ▱▱▱▱▱▱▱▱▱▱  MOD-000 Cross-cutting       · waiting…                  │
│                                                                       │
│  est. 5–12 minutes total · runs 3 modules in parallel                │
│                                                                       │
│                  [ Resume from here ]   ← always visible             │
└─────────────────────────────────────────────────────────────────────┘
```

State driven by SWR polling `api.frs.get(projectId)` every 2s; module bars read
`document.unit_status.design_mod_<mod_row_key>.completeness` and translate to
a 10-segment bar. "in flight" detection: `_current_unit == 'design_mod_<mod_row_key>'`.

Recovery: "Resume from here" calls `api.frs.resetGenerating(projectId)`
(already wired and tested in Stage A).

#### S7 — Spec panel (the big view)

**File**: `frontend/app/components/frs/FrsSpecPanel.tsx` (NEW)

The centerpiece. Wireframe is in PRD §7.2 (lines 1208–1295). Structure:

```
FrsSpecPanel
├── FrsSpecHeader               ← row_key + priority + Layer + dep chips + Edit/Regen/Lock/History
├── FrsSpecDecisionBanner       ← if open decisions
├── Section: Intent / Narrative ← edit pencil; opens FrsRowEditDialog (frs_specs row)
├── Section: § 1 UI Specification
│   ├── FigmaLinkPrompt         ← if no figma_link
│   ├── FrsScreensSection
│   │   └── FrsScreenCard[]     ← each with hover [Edit][Lock][Trash]
│   ├── FrsUiComponentsSection
│   │   └── FrsUiComponentCard[]← each with hover [Edit][Lock][Trash]
│   └── FrsUiDataMappingSection (text via FrsRowEditDialog)
├── Section: § 2 Backend Service Specification
│   ├── Service Overview text (edit)
│   ├── FrsEndpointsSection
│   │   └── FrsEndpointCard[]   ← each with hover [Edit][Lock][Trash]
│   └── Integration text (edit)
├── Section: § 3 Data / Storage / Cache
│   ├── Data Store Overview text (edit)
│   ├── FrsDataEntitiesSection
│   │   └── FrsDataEntityCard[] ← each with hover [Edit][Lock][Trash]
│   ├── SQL/Data Access Logic text (edit)
│   └── Cache Spec sub-card (edit, or N/A)
├── Section: § 4 Cross-Cutting
│   ├── FrsBusinessRulesTable   ← rows with hover [Edit][Lock][Trash]; [+ Add]
│   └── Security spec text (edit)
├── Section: Independent Test (edit textarea)
├── Section: Acceptance Scenarios  ← count counter "6/6 · 2/2 negatives ✓"
│   └── FrsScenariosList
│       └── ScenarioRow[]       ← hover [Edit][Lock][Trash]; [+ Add]
├── Section: Functional Requirements
│   └── FrsFunctionalRequirementsList
│       └── FRRow[]             ← hover [Edit][Lock][Trash]; [+ Add]
├── Section: Data & Validation (edit)
├── Section: Errors & Edge Cases (edit)
├── Section: Observability (edit)
├── Section: Implementation Tasks (edit; optional)
└── Section: Traceability summary  ← read-only summary + trace chips
```

**Section behaviour** (mirrors Stage A's `FrsModulePanel`):
- Each section is a `<Section>` shell with chevron, count, edit pencil
- Default expanded: Intent + Acceptance Scenarios + Functional Requirements
- Collapse state persisted per spec in sessionStorage
- Every text field opens `FrsRowEditDialog` for the parent `frs_specs` row
  scoped to that field
- Every list-of-rows section has `[+ Add row]` at the header → opens a fresh
  edit dialog with an empty schema → on Save the orchestrator's
  `upsert_frs_rows` auto-creates v1

#### S7.1 — FrsScreenCard

**File**: `frontend/app/components/frs/FrsScreenCard.tsx` (NEW)

```
┌─ Screen: Customer Registration                              [🔗][🔒][✏][🗑] ─┐
│ Figma · https://figma.com/file/xyz/...     [Replace link] [Skip→TBD]         │
│                                                                                │
│ Purpose          Business purpose narrative…                                   │
│ User roles       Customer, Guest                                              │
│ Layout           [▾] Responsive layout details…                                │
│ Navigation       [▾] Menu / breadcrumb behavior…                               │
│ Interactive      [▾] Loading states, dynamic refresh…                          │
└──────────────────────────────────────────────────────────────────────────────┘
```

Edit pencil opens `FrsRowEditDialog` on `frs_screens` with the 8-field schema
(screen_name, figma_link, purpose, user_roles tags, layout textarea, navigation
textarea, interactive_behavior textarea). Lock/Trash via the generic API.

If `figma_link == '__none__'`: yellow chip "UI design TBD"; clicking "Replace
link" reopens `FigmaLinkPrompt` and clears the sentinel on save.

#### S7.2 — FrsUiComponentCard

**File**: `frontend/app/components/frs/FrsUiComponentCard.tsx` (NEW)

Compact row + expandable detail:

```
○ Email Input         input    mandatory          on screen: Customer Reg  [✏][🔒][🗑]
   ▾ Definition       { position: 'top', mandatory: true, placeholder: '...' }
   ▾ Behavior         { change: 'live validate', dependencies: [...] }
   ▾ Validation       { format: 'email', server_side: true, message: '...' }
   ▾ Actions          [{button: 'Submit', enabled_when: 'form-valid'}]
   ▾ Data mapping     { ui_field: 'email' → api_param: 'user.email' }
```

Edit dialog with a hybrid schema:
- text fields for `component_name`, `component_type`
- JSON-textarea field type for `definition`, `behavior`, `validation`,
  `data_mapping` (pre-populated with prettified JSON; Save parses + validates;
  rejects malformed JSON with inline error)
- tags for `actions` (each action is a sub-dialog with its own mini-schema, or
  edited inline as JSON)

#### S7.3 — FrsEndpointCard

**File**: `frontend/app/components/frs/FrsEndpointCard.tsx` (NEW)

```
┌─ POST  /api/customers/register                              [✏][🔒][🗑] ─┐
│ Customer Onboarding Service   ·  sync  ·  idempotent: no  ·  ⚙ rate-limited│
│                                                                            │
│ ▾ Request   { headers, query, body, validation, example }                  │
│ ▾ Response  { structure, fields, example, pagination }                     │
│ ▾ Errors    400, 409, 500 — retry { …}                                    │
│ ▾ Security  Bearer JWT — roles: [customer, admin] — masking: [...]         │
│ ▾ Operational  rate-limit 100/min · timeout 5s · max payload 1MB           │
│                                                                            │
│ Integration target: (none)                                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

Method chip uses `FRS_HTTP_METHOD_STYLES`. The 5 sub-blobs render as hidable
JSON tables. Edit dialog with the 14-field schema (method enum, sync_async
enum, idempotent bool, and 6 JSON-textareas).

#### S7.4 — FrsDataEntityCard

**File**: `frontend/app/components/frs/FrsDataEntityCard.tsx` (NEW)

```
┌─ customer_profile (RDBMS)                                  [✏][🔒][🗑] ─┐
│ Expected volume: ~10k rows/day · ~5M total                                  │
│                                                                              │
│ ▾ Columns (12)                                                              │
│   id           uuid        PK     not null    [✏]                            │
│   email        varchar(255)       not null    sensitivity: PII  [✏]          │
│   …                                                                          │
│ ▾ Keys & constraints   primary: [id]   unique: [[email]]                    │
│ ▾ Indexes (3)          ix_customer_email  on (email)  unique                │
│ ▾ Relationships        1:N customer_addresses  cascade: SET NULL            │
│ ▾ Access logic         (text)                                               │
│ ▾ Cache spec           (JSON or "N/A")                                      │
│ ▾ Retention            7 years (compliance)                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

Edit dialog. Inside the dialog, `columns` is a nested editable list (mini-table
with per-column [✏][🗑] icons that pop sub-dialogs for the column JSON). Same
for `indexes` and `relationships`. `keys_constraints` and `cache_spec` are
JSON-textareas. Nested array edits update the parent row's JSONB field (so the
version-bump is at the entity level, not per column — which is correct).

#### S7.5 — FrsBusinessRulesTable

**File**: `frontend/app/components/frs/FrsBusinessRulesTable.tsx` (NEW)

```
Rule ID | Description           | Applies to       | Logic            | actions
BR-1    | Email must be unique  | Registration form| Reject if exists | [✏][🔒][🗑]
BR-2    | Password ≥ 12 chars   | Registration form| Block submit     | [✏][🔒][🗑]
                                                              [+ Add rule]
```

Edit dialog: 4 text/textarea fields. Same `FrsRowEditDialog`.

#### S7.6 — FrsScenariosList

**File**: `frontend/app/components/frs/FrsScenariosList.tsx` (NEW)

```
Acceptance Scenarios     6/6 scenarios · 2/2 negatives ✓                  [+ Add]

1. Given a new user
   When they submit valid email + password
   Then 201 Created and verification email sent
   → FR-1                                                       [✏][🔒][🗑]

2. ✘ Given duplicate email                                      [negative]
   When user submits registration
   Then 409 Conflict returned with code DUPLICATE_EMAIL
   → FR-2                                                       [✏][🔒][🗑]

3. …
```

Counter shows live scenario + negative counts. Green when ≥6 / ≥2; amber when
below. Below 6 or below 2 also surfaces in the findings drawer as a major.
Each scenario edit dialog: given (textarea), when (textarea), then (textarea),
is_negative (bool), fr_refs (tags). `scenario_index` auto-increments on add.

#### S7.7 — FrsFunctionalRequirementsList

**File**: `frontend/app/components/frs/FrsFunctionalRequirementsList.tsx` (NEW)

```
Functional Requirements                                                 [+ Add]

FR-1   System must accept new email/password registration               [✏][🔒][🗑]
       Validated by scenarios 1, 3, 4

FR-2   System must reject duplicate email registrations                 [✏][🔒][🗑]
       Validated by scenario 2

…
```

Edit dialog: fr_id (text), requirement_text (textarea), scenario_refs (tags).
Bidirectional FR↔scenario integrity is enforced by the validator, not by the UI
(so a user can break and fix mid-edit without modal blocking).

#### S7.8 — FigmaLinkPrompt

**File**: `frontend/app/components/frs/FigmaLinkPrompt.tsx` (NEW)

Amber-bordered banner per PRD §7.3 (verbatim from PRD). Inputs:
- URL input
- `[Add link]` → POST `setFigmaLink(spec_row_key, {link})` → triggers UI-only
  regen; toast "Regenerating UI spec…"
- `[Skip — UI TBD]` → POST `setFigmaLink(spec_row_key, {link: '__none__'})` →
  toast "Skipped — UI spec marked TBD"

#### S7.9 — FrsSpecDecisionPrompt

**File**: `frontend/app/components/frs/FrsSpecDecisionPrompt.tsx` (NEW)

Modal/popover per PRD §7.4 wireframe. Shows the question, AI's recommended
option with a ⭐, 2–4 option cards, and four resolution buttons:
- `[Accept AI recommendation]` → resolve with `accepted_ai`, no regen
- `[Override → Option B]` etc. → resolve with `overridden`, triggers
  `regenerate_frs_spec`
- `[Dismiss — not relevant]` → resolve with `dismissed`, no regen

Wires through `api.frs.resolveDecision`.

#### S7.10 — FrsFindingsDrawer

**File**: `frontend/app/components/frs/FrsFindingsDrawer.tsx` (NEW)

Full-height right-slide drawer (480px). 5-group hierarchy from
`FRS_FINDING_GROUPS`. Per finding card:

```
☐  M001-FRS001 has UI surfaces but no Figma link
   suggested fix: Provide a Figma URL via FigmaLinkPrompt, or click 'Skip — UI design TBD'.
   [Accept fix — open FigmaLinkPrompt]   [Jump to spec →]
```

`[Accept fix]` opens the relevant prompt inline; `[Jump to row →]`
smooth-scrolls + 600ms amber pulse on the target row.

Footer: `[ Validate FRS ]` enabled only when critical + major == 0. Tooltip on
disabled state explains the count. `platform_admin`-only `[Override blocking]`
at the bottom with double-confirm.

#### S7.11 — FrsCoverageGalaxy

**File**: `frontend/app/components/frs/FrsCoverageGalaxy.tsx` (NEW)

Modal opened from header `✦ Coverage`. ~120 LOC SVG:
- Two columns: BRs left, FRSes right
- Vertical position = priority order (P0 top, P3 bottom)
- Cubic bezier curves connect traced BRs → FRSes
- Hover BR → outgoing edges + target FRSes highlight
- Hover FRS → incoming edges + source BRs highlight
- Uncovered must-priority BRs render in `--frs-coverage-uncovered` with a
  pulsing glow halo (`--frs-coverage-uncovered-glow`)
- Footer: "17 of 18 BRs covered. 1 must-priority uncovered." with click-to-jump

Driven by `api.frs.coverage(projectId)` returning `FrsCoverage`.

#### S7.12 — Module Rail extension (nested specs)

**File**: `frontend/app/components/frs/FrsModuleRail.tsx` (EXTEND)

Stage A showed module + stub count. Stage B nests each spec:

```
▼ MOD-001 User Onboarding         3 specs                       (expanded)
   ● M001-FRS001  User Registration            ✓ 92%   [editable]
   ● M001-FRS002  Login                        ✓ 88%   [editable]
   ◐ M001-FRS003  Wizard                       (regenerating)

▶ MOD-002 Authentication          2 specs                       (collapsed)
▶ MOD-003 Notifications           4 specs
▶ MOD-000 Cross-cutting           2 specs
```

- Each module is collapsible
- Spec rows show completeness % + status icon (✓ done, ◐ generating, ⚠ has
  blocking finding, 🔒 locked)
- Click spec → loads `FrsSpecPanel`
- Right-click spec → context menu (Open / Regenerate / Lock / Delete / Copy link)

#### S7.13 — Header extensions

**File**: `frontend/app/components/frs/FrsBuilderView.tsx` (EXTEND header)

Add to existing Restart + Check & Validate:

```
[← Back]  Functional Specifications  [Draft · Stage 2 ready]   [✦ Coverage] [⤓ Export ▾] [Restart] [✓ Check & Validate]
```

`✦ Coverage` → opens `FrsCoverageGalaxy`.
`⤓ Export` → dropdown:
```
[ Markdown bundle (.zip) ← primary ]
  DOCX (coming soon — disabled)
  Copy public link (coming soon — disabled)
```

Click → `api.frs.export(projectId)` → browser saves zip.

#### S7.14 — Spec panel mounting

**File**: `frontend/app/components/frs/FrsBuilderView.tsx` (EXTEND state machine)

```ts
// State: activeSpecRowKey is set → render FrsSpecPanel instead of FrsModulePanel
const activeSpec = useMemo(
  () => activeModule?.backlog.find(s => s.row_key === activeSpecRowKey) ?? null,
  [activeModule, activeSpecRowKey],
)

// Routing logic:
if (activeSpec) {
  return <FrsSpecPanel projectId={projectId} spec={activeSpec} module={activeModule} onMutate={mutate}/>
} else if (activeModule) {
  return <FrsModulePanel ... />          // Stage A view
}
```

#### S7.15 — Validated state

When `doc.status === 'validated'`:
- All edit pencils on every row gray out + tooltip "Validated — unlock the spec
  to edit"
- Header shows `Stage 2 Validated ✓` (emerald badge)
- Continue / Restart buttons collapse to `Unlock for changes`
- Export button stays enabled
- Bottom banner: `Test Cases artifact is now unlocked` (when E5/Test Cases ships)

### 4.6 The user's "every artifact role editable + deletable" requirement — explicit map

This is achieved by **architectural reuse**:

| Stage B sub-row | Edit | Delete | Lock | Restore | Implementation |
|---|---|---|---|---|---|
| `frs_specs` (full form) | ✓ | ✓ | ✓ | ✓ | Header Edit pencil opens dialog for narrative + metadata; module rail row delete |
| `frs_screens` | ✓ | ✓ | ✓ | ✓ | FrsScreenCard hover cluster |
| `frs_ui_components` | ✓ | ✓ | ✓ | ✓ | FrsUiComponentCard hover cluster |
| `frs_endpoints` | ✓ | ✓ | ✓ | ✓ | FrsEndpointCard hover cluster |
| `frs_data_entities` | ✓ | ✓ | ✓ | ✓ | FrsDataEntityCard hover cluster |
| `frs_data_entities.columns[]` | ✓ | ✓ | — | — | Nested per-column action in entity edit dialog |
| `frs_data_entities.indexes[]` | ✓ | ✓ | — | — | Nested |
| `frs_data_entities.relationships[]` | ✓ | ✓ | — | — | Nested |
| `frs_business_rules` | ✓ | ✓ | ✓ | ✓ | FrsBusinessRulesTable per-row cluster |
| `frs_acceptance_scenarios` | ✓ | ✓ | ✓ | ✓ | FrsScenariosList per-row cluster |
| `frs_functional_requirements` | ✓ | ✓ | ✓ | ✓ | FrsFunctionalRequirementsList per-row cluster |
| `frs_spec_decisions` (spec-scoped) | ✓ | ✓ | ✓ | ✓ | Inline edit; delete = dismiss |
| `frs_traceability` | ✓ | ✓ | n/a (not versioned) | n/a | Edit via section's trace chips popover; delete removes chip |
| Stage A rows (modules, actors, etc.) | ✓ | ✓ | ✓ | ✓ | Already shipped — no work needed |

For every versioned row above, implementation is:
1. The row component renders the hover cluster `<Pencil>` / `<Lock>` / `<Trash2>`
2. `<Pencil>` → opens `FrsRowEditDialog` with the row type's field schema
3. `<Lock>` → calls `api.frs.editRow(... {lock: true})` or `api.frs.unlockRow(...)`
4. `<Trash2>` → confirms then calls `api.frs.deleteRow(...)`
5. Dialog Save → `api.frs.editRow(...)`; on success the parent's `onMutate`
   triggers SWR re-fetch
6. Restore via row history modal (already shipped from Stage A)

**Nested editable arrays** (`columns[]`, `indexes[]`, `relationships[]` in
`frs_data_entities`; `actions[]` in `frs_ui_components`) are JSONB on the parent
row, so editing goes through the parent's dialog with a multi-row sub-table UI.
Adding/removing a sub-item triggers an edit of the parent row (version bump),
which is correct semantically.

### 4.7 Animation catalog (extensions to Stage A)

All animations gated by `useReducedMotion()`. New entries:

| Where | Motion | Duration / curve |
|---|---|---|
| Spec panel section expand/collapse | height auto + opacity | 220ms ease-out (Radix Accordion) |
| Coverage galaxy node hover | stroke-width 1.5 → 2.5, edge highlight | 180ms ease-out |
| Coverage galaxy uncovered glow | radial fill pulse 0.4 → 0.7 → 0.4 | 2000ms ease-in-out infinite |
| Module rail spec row generating | ◐ rotation | 1200ms linear infinite |
| Two-phase viz bar fill | width 0 → N% | 600ms ease-out |
| Two-phase viz module bar appears | translate-y + opacity | 220ms ease-out, 50ms stagger |
| Findings drawer slide | translate-x-full → 0 | 280ms ease-out |
| Finding accept-fix card collapse | height auto → 0 + opacity | 220ms ease-out |
| Spec panel "Validated ✓" badge | scale 0.95 → 1.05 → 1 | 240ms ease-out, single |
| Confetti on POST /validate | reused BrdConfettiBurst | 600ms |

### 4.8 Keyboard shortcuts (extensions to Stage A)

| Key | Action | Context |
|---|---|---|
| `n` | Next spec in rail | Spec panel open |
| `p` | Previous spec | Spec panel open |
| `f` | Open `✦ Coverage` modal | Anywhere in builder |
| `v` | Trigger `Check & Validate` | Anywhere in builder |
| `e` | Open the active row's edit dialog | Hovering a row |
| `Esc` | Close dialog / drawer / modal | Anywhere |

### 4.9 Accessibility

- `FrsSpecPanel` uses `<section>` per template section with `<h3>` titles
- Findings drawer announces finding count via `aria-live="polite"`
- Coverage galaxy edges have `<title>` children describing the BR → FRS link
- Method chips in endpoint cards have `aria-label` describing the verb + path
- Every action button has explicit `aria-label`

### 4.10 Responsive

- **≥ lg (1024px+)**: 2-column layout (rail + spec panel)
- **md (768–1023px)**: module rail collapses to fly-out drawer
- **< md (mobile)**: tab switcher `Modules · Active Spec · Thread`

---

## 5. File-by-file inventory

### 5.1 Backend (mostly extensions)

| Path | Status | Purpose |
|---|---|---|
| `backend/app/services/artifacts/manifest/frs.py` | extend | Add `FRS_STAGE_B_UNIT` |
| `backend/app/services/skills/dspy_frs.py` | extend | 7 sub-row Pydantic schemas + `FrsDesignModuleSignature` + `run_design_module` |
| `backend/app/services/llm/fixtures/frs_design_module.json` | new | Hand-written fixture for one module (3 specs covering all code paths) |
| `backend/app/services/artifacts/frs_orchestrator.py` | extend | `generate_frs_all`, `generate_frs_design_module`, `_persist_design_module_result`, `_persist_ui_only_result`, `regenerate_frs_spec`, `set_figma_link`, `_upsert_frs_traceability`, `_has_depends_on_cycle` |
| `backend/app/services/artifacts/validators/frs.py` | extend | `_validate_stage_b` (14 checks) |
| `backend/app/api/frs.py` | extend | 6 new routes |
| `backend/app/services/artifacts/exporters/frs.py` | new | Markdown export bundle (zip) |
| `backend/workers/tasks.py` | extend | `regenerate_frs_module`, `regenerate_frs_spec`, `incorporate_frs_answer` |
| `backend/workers/dispatch.py` | extend | Register 3 new tasks |
| `backend/tests/test_frs_design_module.py` | new | ~12 orchestration tests |
| `backend/tests/test_frs_validator_stage_b.py` | new | ~14 validator tests |
| `backend/tests/test_frs_exporter.py` | new | Zip structure + template rendering |

**No new model files. No new migrations. No new enums.**

### 5.2 Frontend

| Path | Status | Purpose |
|---|---|---|
| `frontend/lib/types.ts` | extend | 8 Stage B row types + `FrsSpecHydrated` + `FrsCoverage` |
| `frontend/lib/frs-manifest.ts` | extend | `FRS_HTTP_METHOD_STYLES`, extended `FRS_TRACE_KIND_STYLES` |
| `frontend/lib/api.ts` | extend | 5 new methods on `api.frs.*` |
| `frontend/app/globals.css` | extend | Stage B tokens (methods, trace kinds, coverage, phases) |
| `frontend/app/components/frs/FrsBuilderView.tsx` | extend | Stage B state machine routing + header buttons |
| `frontend/app/components/frs/FrsModuleRail.tsx` | extend | Nested spec rows + context menu |
| `frontend/app/components/frs/FrsConstructionTheater.tsx` | extend | Hand off to TwoPhaseGenerationViz |
| `frontend/app/components/frs/FrsTwoPhaseGenerationViz.tsx` | new | Phase A + Phase B parallel bars |
| `frontend/app/components/frs/FrsSpecPanel.tsx` | new | The big view — 12+ sections |
| `frontend/app/components/frs/FrsSpecHeader.tsx` | new | Top of spec panel |
| `frontend/app/components/frs/FrsScreenCard.tsx` | new | §1.1 |
| `frontend/app/components/frs/FrsUiComponentCard.tsx` | new | §1.2 |
| `frontend/app/components/frs/FrsEndpointCard.tsx` | new | §2.2 |
| `frontend/app/components/frs/FrsDataEntityCard.tsx` | new | §3.2 |
| `frontend/app/components/frs/FrsBusinessRulesTable.tsx` | new | §4.1 |
| `frontend/app/components/frs/FrsScenariosList.tsx` | new | Acceptance scenarios w/ counter |
| `frontend/app/components/frs/FrsFunctionalRequirementsList.tsx` | new | FR list |
| `frontend/app/components/frs/FigmaLinkPrompt.tsx` | new | Inline blocker banner |
| `frontend/app/components/frs/FrsSpecDecisionPrompt.tsx` | new | MCQ Radix popover |
| `frontend/app/components/frs/FrsFindingsDrawer.tsx` | new | Full findings drawer (right slide) |
| `frontend/app/components/frs/FrsCoverageGalaxy.tsx` | new | BR↔FRS bezier modal |
| `frontend/app/components/frs/FrsExportMenu.tsx` | new | Header dropdown |
| `frontend/app/components/frs/FrsTraceChip.tsx` | extend | New target_kind palette entries |
| `frontend/app/components/frs/FrsRowEditDialog.tsx` | extend | JSON-textarea field type for endpoint/entity blobs |

---

## 6. Implementation phases (with critical path)

### Phase B-A — Backend foundations (parallel-safe, ~3 days)
1. Manifest extension (`FRS_STAGE_B_UNIT`)
2. DSPy schemas + signature + runner + fixture
3. Orchestrator skeletons (`generate_frs_design_module` returning fixture)

### Phase B-B — Backend orchestration (depends on B-A, ~4 days)
4. `_persist_design_module_result` + `_persist_ui_only_result`
5. `_upsert_frs_traceability` (replace-all)
6. `set_figma_link` handler
7. `generate_frs_all` (Stage A → Stage B, parallel with semaphore)
8. `regenerate_frs_spec`

### Phase B-C — Backend validation + API + exporter (depends on B-B, ~3 days)
9. `_validate_stage_b` rules + cycle detector
10. Stage-B API routes (design, regenerate, figma-link, coverage, export, validate commit)
11. Markdown exporter
12. Celery tasks + dispatch registration

### Phase B-D — Frontend foundations (parallel with B-A/B/C, ~3 days)
13. Types + manifest + API client extensions
14. CSS tokens
15. `FrsTwoPhaseGenerationViz`
16. `FrsModuleRail` nested-spec extension

### Phase B-E — Frontend atomic cards (depends on B-D, ~5 days)
17. `FrsScreenCard`, `FigmaLinkPrompt`
18. `FrsUiComponentCard`
19. `FrsEndpointCard`
20. `FrsDataEntityCard`
21. `FrsBusinessRulesTable`
22. `FrsScenariosList`
23. `FrsFunctionalRequirementsList`
24. `FrsSpecDecisionPrompt`
25. `FrsTraceChip` extensions

### Phase B-F — Frontend hero surfaces (depends on B-E + B-C, ~3 days)
26. `FrsSpecPanel` (the orchestrator)
27. `FrsFindingsDrawer`
28. `FrsCoverageGalaxy`
29. `FrsExportMenu` + header wiring
30. `FrsRowEditDialog` JSON-textarea field type
31. `FrsBuilderView` integration (Stage B state machine)

### Phase B-G — Verification & polish (depends on everything, ~3 days)
32. Backend test suite (12 + 14 + zipper tests)
33. Mock-mode E2E walkthrough (every UI surface)
34. Real-mode sanity (Vertex pipeline — 1 small module)
35. Reduced-motion + a11y + responsive
36. Visual regression via dev-browser

**Total**: ~24 calendar days (BE + FE in parallel ≈ 15 days)

---

## 7. Verification

### 7.1 Mock-mode E2E (the gold path)

Prerequisites: Stage A is shipped + mocked correctly; `LLM_PROVIDER=mock`;
claims chatbot project with validated BRD and Stage A done.

**Step 1 — handoff**
1. Open builder for claims chatbot. Stage A done; "Continue to Stage 2 →" banner.
2. Click Continue → `FrsTwoPhaseGenerationViz` mounts. Phase A shows ✓. Phase B
   shows module bars filling in parallel (3 at a time).
3. Bars complete in cascade within ~2s (mock). Transition to builder body.

**Step 2 — module rail**
4. Rail now shows specs nested under each module. Each spec row shows
   completeness % + ✓.
5. Click a spec → `FrsSpecPanel` renders the full template structure.

**Step 3 — spec panel**
6. Intent section: edit pencil → `FrsRowEditDialog` for `frs_specs`. Save →
   toast, version bumps.
7. §1 UI Spec: if `ui_blocked_reason`, FigmaLinkPrompt renders. `[Add link]` →
   POST → "Regenerating UI spec…" → 2s later, screens + ui_components populated.
8. Click `[Skip — UI TBD]` on a different spec → sentinel set; yellow chip
   appears; no regen.
9. §2 Backend: endpoint cards visible; hover → action cluster. Edit pencil →
   endpoint dialog with method enum + URL + JSON-textareas. Save → toast.
10. §3 Data: entity card; expand Columns; per-column edit; save updates
    parent's `columns` JSONB.
11. §4 Cross-Cutting: business rule table; `[+ Add rule]` → empty dialog; save
    creates new row.
12. Acceptance Scenarios: counter shows "6/6 · 2/2 negatives". Edit a scenario.
13. Functional Requirements: same; add scenario refs as tags.

**Step 4 — decisions**
14. Open decision banner → MCQ popover. Pick "Override → Option B" → POST →
    spec regenerates (theater overlay ~2s) → updated narrative reflects choice.

**Step 5 — findings**
15. `✓ Check & Validate` → drawer slides in. Shows 0 critical, 0 major, 1
    warning.
16. Validate FRS enabled (0 blocking).
17. Inject a fault: delete a scenario → drawer refresh shows
    `too_few_scenarios` major. Validate disables. `[Accept fix]` → regen →
    drawer refresh shows 0 blocking.
18. Click `Validate FRS` → confetti → status → `validated` → every row
    `is_locked=True` → header shows `Stage 2 Validated ✓`.

**Step 6 — coverage**
19. `✦ Coverage` → galaxy opens. Hover BR → FRSes highlight. Hover FRS → BRs
    highlight.
20. (Optional) Uncovered must-priority node glows red.

**Step 7 — export**
21. `⤓ Export → Markdown bundle` → browser downloads zip.
22. Unzip → README + modules/ + specs/ + traceability/ → spot-check a spec
    file matches template.

**Step 8 — unlock + re-edit**
23. Header shows `Unlock for changes`. Click → status reverts to in_interview.
24. Edit a row → save → new version.
25. Re-validate → drawer + commit → status back to validated.

### 7.2 Real-mode sanity (Vertex)

- Run `LLM_PROVIDER=gemini` against one small module (force MOD-000 Cross-cutting).
- Verify the AI:
  - Produces specs with all sections per template
  - Generates ≥6 acceptance scenarios with ≥2 negative
  - Generates ≥1 FR per spec
  - Traces every FR to ≥1 scenario AND vice versa
  - Omits §1 UI when module has no `ui_surface` interfaces
  - Asks for a Figma link when module HAS `ui_surface`
  - Produces traceability rows tracing each spec to ≥1 BR
  - Surfaces a [SPEC-DECISION] when ambiguity exists
- Verify the orchestrator:
  - Caps Vertex calls at 3 concurrent (timing: 5 modules ~5min not 15min)
  - Each module's session is independent (no event-loop binding errors)
  - Reset endpoint recovers from a killed worker mid-design

### 7.3 Critical invariants — code-side verification

```bash
make test-be       # all FRS Stage B tests pass
make typecheck     # TypeScript clean
make lint          # Next lint clean
```

Must-pass test names:
- `test_design_module_smoke`
- `test_design_module_is_idempotent`
- `test_design_module_preserves_locked_spec`
- `test_design_module_preserves_locked_scenarios`
- `test_figma_link_unblocks_ui_section`
- `test_figma_link_skip_sentinel`
- `test_spec_decision_resolve_overridden_triggers_regen`
- `test_traceability_replace_all_semantics`
- `test_validate_gate_refuses_with_blocking_finding`
- `test_validate_commit_locks_all_rows`
- `test_export_zip_structure`
- `test_parallel_module_design_atomicity`

### 7.4 Performance budgets

- Spec panel TTI (1 spec with 6 scenarios + 2 endpoints + 1 entity): ≤ 1.5s
- Module rail expand: ≤ 16ms / frame
- Coverage galaxy initial render (18 BRs × ~20 specs): ≤ 800ms
- `gather_project_context` (validated BRD + 5 modules + ~20 stubs): ≤ 1.2s
- `generate_frs_design_module` (mock): ≤ 1s per module
- `generate_frs_design_module` (Vertex): 60–150s per module
- 5-module full pipeline (Vertex, semaphore=3): 5–12 minutes

### 7.5 Accessibility

- Tab through spec panel → every interactive element reachable in logical order
- VoiceOver: spec panel reads as "FRS Spec M001-FRS001, User Registration, Priority P0, …"
- Reduced motion: all new animations have static fallback
- WCAG AA contrast on every text/bg pair

### 7.6 Security

- All Stage-B endpoints require `Depends(get_current_user)` + `get_project_or_404`
- Edit accepts `expected_version` (409 on conflict)
- No PII handling
- `figma_link` is a plain URL — no fetch in v1 → no SSRF risk
- Export bundle generated server-side from existing rows — no template injection
- `platform_admin` override of blocking findings logged in audit

---

## 8. Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| LLM produces fewer than 6 scenarios | medium | medium | `min_length=6` Pydantic constraint forces retry at Signature level; validator catches at FRS-level |
| LLM produces orphan FR/scenario refs | medium | medium | Validator's `fr_no_scenario` and `scenario_no_fr` checks; user can [Accept fix] |
| LLM hallucinates BR row_keys | low | high | Stage A passes verbatim BR list in `brd_context`; orchestrator post-validates `target_ref` against actual BR keys; drops invalid traces with warning |
| Vertex parallel calls cost spike | medium | medium | Semaphore(3); mock-first keeps CI free; observability tracks per-module Vertex token usage |
| Theater feels frozen when Vertex slow (>120s per module) | medium | medium | Module bar pulses indefinitely; "Resume from here" always visible; 150s timeout aborts cleanly |
| User edits row mid-regen → conflict | low | medium | `expected_version`; UI shows "Row was modified — refresh" toast |
| Cycle in `depends_on` (LLM mistake) | medium | high | Validator's `_has_depends_on_cycle` DFS; finding includes cycle path; UI suggests extracting shared logic to MOD-000 |
| Markdown export bundle too large (>50 specs) | low | low | Per-spec files ~5–10 KB; 50 specs ~500 KB; stream-zip via stdlib |
| Mock fixture drifts from real DSPy schema | medium | high | Pydantic validation on fixture load; schema-pinned via DSPy Signature; CI guard |
| Locked sub-row dropped during regen | low | high | Orchestrator post-applies locks after LLM call (defense in depth on top of `upsert_frs_rows`'s lock-skip) |
| User accidentally clicks Restart | medium | high | Confirmation dialog (already shipped Stage A); locked rows survive Restart; row history restore available |
| Confidence ⇄ completeness inconsistency in fixtures | low | low | Test asserts completeness < 90 implies confidence ≠ high; fixture authoring guideline in tests |

---

## 9. Out of scope (deferred to v2+)

Per PRD §12 and §13:
- Figma MCP fetch (link-only in v1; field reserved for future)
- DOCX export (markdown only in v1)
- Public shareable links
- Inline AI single-sentence rewrite
- Multi-user real-time editing
- Component-library mapping (downstream coding agent's job)
- BR/FRS rename refactor (user must regenerate to apply)
- Cross-FRS auto-merge / split
- Dependency graph viz beyond simple coverage galaxy
- Approval workflow (sign-off rows)
- Test cases artifact (E5)
- Tightly-coupled NFR builder (NFR refs from project docs only in v1)

---

## 10. Appendix · Quick reference component map (Stage B additions)

```
FrsBuilderView (Stage A + B state machine)
├── … (Stage A surfaces)
└── activeSpecRowKey set → FrsSpecPanel
    ├── FrsSpecHeader (Edit metadata / Regenerate / Lock / History)
    ├── FrsSpecDecisionBanner (if open)
    ├── Intent / Narrative section
    ├── § 1 UI Spec
    │   ├── FigmaLinkPrompt (if blocked)
    │   ├── FrsScreenCard[]    ← per-row [Edit] [Lock] [Trash]
    │   ├── FrsUiComponentCard[]← per-row [Edit] [Lock] [Trash]
    │   └── UI Data Mapping text
    ├── § 2 Backend Spec
    │   ├── Service Overview text
    │   ├── FrsEndpointCard[]  ← per-row [Edit] [Lock] [Trash]
    │   └── Integration text
    ├── § 3 Data Spec
    │   ├── Data Store Overview text
    │   ├── FrsDataEntityCard[]← per-row [Edit] [Lock] [Trash]
    │   ├── SQL/Access logic text
    │   └── Cache Spec sub-card
    ├── § 4 Cross-Cutting
    │   ├── FrsBusinessRulesTable ← per-row [Edit] [Lock] [Trash]
    │   └── Security text
    ├── Independent Test
    ├── FrsScenariosList         ← per-row [Edit] [Lock] [Trash], counter, [+ Add]
    ├── FrsFunctionalRequirementsList ← per-row, counter, [+ Add]
    ├── Data & Validation, Errors, Observability, Implementation Tasks
    └── Traceability summary (read-only chips)

Overlays:
  - FrsFindingsDrawer (right slide)
  - FrsCoverageGalaxy (centered modal)
  - FrsSpecDecisionPrompt (Radix popover)
  - FrsRowEditDialog (universal editor — extended for JSON fields)
  - FrsExportMenu (header dropdown)

Theater wrapper (when Stage A + Stage B full pipeline runs):
  FrsTwoPhaseGenerationViz
    ├── Phase A summary strip
    └── Phase B parallel module bars
```

---

## 11. Cross-check against `reference_mds/skills/frs-builder/`

Verified against `SKILL.md`, `guidelines/functional-design.md`,
`guidelines/modularization.md`, `templates/frs-template.md`, `templates/module-template.md`.

### 11.1 Workflow coverage

| SKILL.md step | Where covered |
|---|---|
| Step 1 — Preparation (read BRD + NFR + Architecture) | `bundle = gather_project_context(artifact_type='frs')` builds App + Docs + CB + BRD layers; NFR/Arch docs surface via the depth-search inside `source_sections` |
| Step 2 — Module decomposition | Stage A (already shipped) |
| Step 3 — FRS backlog | Stage A (stub rows in `frs_specs`, `completeness=0`) |
| Step 4 — FRS authoring | Stage B's `generate_frs_design_module` (§3.4) — Figma gate + ambiguity elimination via `[SPEC-DECISION]` + replace-all traceability |
| Step 5 — Consistency + traceability | `_validate_stage_b` + `FrsFindingsDrawer` + `FrsCoverageGalaxy` + exporter |

### 11.2 Context bundle handoff — explicit confirmation

The `design_module` DSPy call (§3.4) receives ALL of:

| Bucket | Field passed to DSPy | Source |
|---|---|---|
| Project meta | `project_name`, `business_unit` | `project` row |
| App Brain | `app_brain` | `bundle.apps.formatted_context` |
| Documents (incl. NFR + Architecture if uploaded) | `source_sections` | `depth_search(...)` on project docs |
| Concept Brief | `cb_context` | `bundle.cb.formatted_context` |
| BRD (all 21 tables) | `brd_context` | `bundle.brd.formatted_context` |
| Module shell (this one) | `module_context` | `_serialize_module_with_children(...)` |
| Module shells (siblings) | `other_modules_summary` | `_summarize_other_modules(exclude=...)` |
| Discover Q&A | `qa_pairs` | `_gather_frs_unit_qa(unit_key="design_module")` |
| Idempotency state | `current_specs` | active specs for this module |
| Lock state | `locked_specs` | filtered subset of `current_specs` |
| User overrides | `resolved_decisions` | resolved `frs_spec_decisions` rows |

### 11.3 Coverage of the 12-section frs-template.md

| Template section | Column / Table | Notes |
|---|---|---|
| Metadata (priority, layer, module, BR refs, NFR refs, depends_on) | `frs_specs` columns | ✓ |
| Intent / Narrative | `frs_specs.narrative` | ✓ |
| §1.1 Screens | `frs_screens` | ✓ |
| §1.2 UI Components | `frs_ui_components` | ✓ |
| §1.3 UI Data Mapping | `frs_ui_components.data_mapping` JSONB + free-text on `frs_specs.data_and_validation` | ✓ |
| §2.1 Service Overview | (no dedicated column) | **Folded into `narrative` + per-endpoint `service_name`** — see §11.4 gap 2 |
| §2.2 Service Endpoints | `frs_endpoints` | ✓ |
| §2.3 Integration | `frs_endpoints.integration_target` per-endpoint | ✓ |
| §3.1 Data Store Overview | (no dedicated column) | **Folded into per-entity `description` + `retention_policy`** — see §11.4 gap 2 |
| §3.2 Table / Entity Definition | `frs_data_entities` (columns, keys, indexes, relationships) | ✓ |
| §3.3 SQL / Data Access Logic | `frs_data_entities.access_logic` | ✓ |
| §3.4 Cache Spec | `frs_data_entities.cache_spec` (nullable) | ✓ |
| §4.1 Business Rules | `frs_business_rules` | ✓ |
| §4.2 Security Specification | (no dedicated column) | **Falls back to per-endpoint `security` JSONB + free-text in `narrative`** — see §11.4 gap 1 |
| Independent Test | `frs_specs.independent_test` | ✓ |
| Acceptance Scenarios (≥6, ≥2 neg) | `frs_acceptance_scenarios` | ✓ — Pydantic + validator enforce |
| Functional Requirements | `frs_functional_requirements` | ✓ — bidirectional FR↔scenario enforced |
| Data and Validation | `frs_specs.data_and_validation` | ✓ |
| Errors and Edge Cases | `frs_specs.errors_and_edge_cases` | ✓ |
| Observability | `frs_specs.observability` | ✓ |
| Implementation Tasks | `frs_specs.implementation_tasks` JSONB | ✓ |
| Traceability | `frs_traceability` (replace-all) | ✓ |

### 11.4 Gaps identified + fixes baked into the plan

**Gap 1 — `§4.2 Security Specification` has no dedicated column.**
Resolution chosen for v1: spec-level security narrative folds into
`frs_specs.narrative` ("Security follows Cross-cutting Standards MOD-000 unless
noted; specific overrides below…") with per-endpoint detail in
`frs_endpoints.security` JSONB. If experience shows this is too cramped, v2
adds a `security_spec` column to `frs_specs` — small schema change, no data
migration required because new column is nullable.

**Gap 2 — `§2.1 Service Overview` and `§3.1 Data Store Overview`** are
template sub-sections without dedicated columns. Resolution: the exporter
(§3.7) synthesises these sections by aggregating per-endpoint `service_name` +
per-entity `description` + `retention_policy` into the corresponding markdown
sections at export time. UI does not surface them as separate sections — the
relevant detail lives on the per-row cards.

**Gap 3 — NFR coverage validator rule missing.** SKILL.md step 5 mandates
"NFR coverage is complete". The plan added BR coverage (`br_uncovered_in_frs`)
but no equivalent for NFRs. **Adding to validator §3.5**:

| Severity | check_id | Trigger |
|---|---|---|
| coverage | `nfr_uncovered_in_frs` | An NFR driver row (when NFR builder ships) has no `frs_traceability` row from any spec |

In v1 (no NFR builder yet), NFR drivers are inferred from depth-searched
project docs. The rule fires only when `bundle.docs.outline_text` contains
NFR-tagged sections that are not referenced by any spec's `nfr_refs`. This
remains a non-blocking coverage warning (consistent with BR coverage).

**Gap 4 — Architecture-exclusion rule.** SKILL.md (line 76) requires:
"Do not create modules or FRS for deployment, runtime packaging, CI/CD,
infrastructure provisioning, or environment setup." Stage A's DSPy prompt
should already include this; Stage B's `FrsDesignModuleSignature` docstring
must also include this hard rule:

> "ARCHITECTURE EXCLUSION: never author FRS sections for deployment, CI/CD,
> infrastructure provisioning, runtime packaging, or environment setup. If a
> backlog stub appears to require such content, set its completeness=0 and
> emit an open_question pointing the user at the project's Architecture Design
> doc."

### 11.5 Modularization rules inherited (no new work — Stage A already enforces)

| Rule from `guidelines/modularization.md` | Where Stage B relies on it |
|---|---|
| Module names use capability/role language (no "API", "DB", "Service", "Lambda") | Stage A validator's `module_tech_name` rule (already shipped) catches violations before Stage B runs |
| Cross-cutting standards in Layer 0 | Stage A hoists MOD-000; Stage B specs reference via `depends_on=["M000-FRS001"]` (covered in DSPy prompt §3.2) |
| High cohesion / low coupling boundaries | Reflected in `FrsContractGraph` + cycle detection in validator |
| Sizing: ≤10–15 FRS per module | Stage A `under_decomposed_module` (≤1) and `over_loaded` (>15) warnings; Stage B inherits these counts |
| Technology-agnostic module names | Stage A enforces; Stage B preserves by NOT renaming modules during design |

### 11.6 Confirmation answer to the user's question

**Q: Are we carrying the project, brain, BRD, and module context here?**

**A: Yes — and more.** The Stage B `design_module` DSPy call gets:
- Project meta (name, business unit)
- App Brain (full, formatted)
- BRD (full validated BRD via BrdLayer — every BR, objective, KPI, risk, scope item, etc.)
- Module context (the active module + all child rows + sibling modules' summary for cross-module awareness)
- Plus: Concept Brief + project docs (incl. NFR/Architecture sections) + discover Q&A
- Plus persistence state: current_specs, locked_specs, resolved_decisions

This satisfies the SKILL.md authoritative-inputs requirement (BRD + NFR + Architecture)
AND adds the extra grounding (CB, App Brain, Discover Q&A) that the SpecForge
platform makes available beyond what the standalone skill expects.
