# E4c · Part 1 — FRS Modularization PRD

> **Stage A** of the FRS Builder pipeline (RU → CB → BRD → **FRS = Modularization + Functional Design**).
> This PRD covers the **first of two skills** in `reference_mds/skills/frs-builder/`:
> `guidelines/modularization.md` + `templates/module-template.md`. The second skill
> (Functional Design) is documented in `prd-e4c-frs-functional-design.md` and depends on this one.
>
> **Goal of this stage**: decompose the validated BRD into 5–12 business-capability **modules**
> using Domain-Driven Design (DDD), with explicit cross-module contracts and a per-module FRS
> backlog. The output is the foundation for Stage B, which fills in each backlog stub with a
> full FRS spec.
>
> **Out of scope for this PRD** (covered in `prd-e4c-frs-functional-design.md`):
> - Full FRS spec authoring (UI / Backend / Data / Scenarios / FRs)
> - Figma link prompts on individual screens
> - The full validation drawer for spec-level findings
> - Per-spec sub-row tables (screens, components, endpoints, entities, business rules,
>   scenarios, functional requirements, traceability) — Stage B owns those

---

## 1. Context & purpose

The validated BRD produces ~10–30 business requirements scattered across 22 typed tables
(objectives, BRs, KPIs, risks, stakeholders, scope items, etc.). A downstream coding agent
cannot directly consume those — it needs **bounded, implementable modules** with clear ownership,
explicit interfaces, and dependency-aware contracts.

**Stage A — Modularization** is the bridge between "raw business requirements" and "actionable
functional specifications". It answers:

- *What business capabilities live in this initiative?* (modules)
- *Who owns each capability — primary actors, dependencies, external systems?* (actors)
- *What does each module do?* (responsibilities — each maps to ≥1 FRS)
- *How do modules interact?* (cross-module contracts — sync APIs or async events)
- *What data is owned where?* (entities at conceptual level — no schema yet)
- *Which functional slices need to be designed in detail?* (FRS backlog stubs)

The skill is strict on **DDD principles** — modules are business capabilities, not technical
layers. The orchestrator enforces this via the LLM Signature instruction; the validator catches
violations.

**Why this stage matters strategically**:
- Without modules, Stage B would produce an unstructured pile of FRS files with no clear ownership.
- The cross-module contract inventory becomes the foundation of architectural review.
- The Cross-cutting Standards module (Layer 0) prevents rule duplication across feature FRSes.
- The FRS backlog is the **deliverable** of this stage — once approved, Stage B can run.

---

## 2. The skill — what we implement (verbatim from `modularization.md`)

This PRD implements the **Modularization Guideline (DDD-first)** at
`reference_mds/skills/frs-builder/guidelines/modularization.md` and the **Module template** at
`reference_mds/skills/frs-builder/templates/module-template.md`.

### 2.1 Core principle (non-negotiable)

> Module files describe **what the business capability does**, not how it is implemented.
> All names, actors, and interface descriptions MUST use capability/role language. Technology
> choices (runtime, database, cloud service) are recorded in architecture docs only and must
> not appear in module files.

The DSPy Signature must instruct the LLM in these exact terms. The validator must reject any
module whose name contains tech-specific tokens (`API`, `DB`, `Service`, `Lambda`, `Kafka`,
`Postgres`, etc.).

### 2.2 The 5-step extraction process (the LLM must follow)

1. **Identify bounded contexts** — group requirements by *what the business does*, using these
   signals: rules/invariants differ, terminology differs, data ownership differs, actors differ,
   change cadence differs.
2. **Validate boundaries** — high cohesion (shared core data and rules) + low coupling (few
   dependencies). Split if: conflicting terminology, two sources of truth in one module, many
   dependencies on another capability's data. Merge if: they always change together, share core
   entities/invariants.
3. **Apply sizing rules** — secondary check after domain boundaries. Split if: multiple
   independent sub-capabilities, > ~3 major end-to-end flows, > ~5 primary aggregates, > ~2
   external integrations, would produce 10–15 FRS for one module. Do not split if: breaks a
   single business invariant, would introduce heavy synchronous chatter.
4. **Make cross-module dependencies explicit** — record contracts at two levels: module file =
   inventory level (interface name, direction, type, counterpart, link to FRS); the full
   contract details (schema/errors/auth) live in the FRS owned by the source module. **Modules
   do NOT integrate via shared internal data models or shared databases.**
5. **Capture system-view constraints inside each module** — data persistence/validation
   constraints, external integrations, security/privacy/audit, performance/availability —
   recorded but NOT used to define modules.

### 2.3 Cross-cutting / common capabilities rule

Common items (shared constants/reference data, common error/response envelope, RBAC base) are
documented as **FRS in a dedicated Layer-0 module called "Cross-cutting Standards"**. Feature
modules' FRS reference these via the `depends_on` field of the FRS spec. The orchestrator
hoists these automatically when ≥2 modules share a rule.

### 2.4 Anti-patterns the validator must catch

- Layer-based modules ("UI", "API", "DB") as primary decomposition
- Shared database as the integration mechanism between modules
- "Platform" module that absorbs unrelated business rules
- Modules named after technologies (Auth API, Notification Service, Postgres Layer)
- Modules with zero backlog stubs (under-defined)
- Modules with >15 backlog stubs (under-decomposed; the LLM should have split it)

### 2.5 Module file template (what the LLM produces, per `module-template.md`)

Every module produced by Stage A maps 1-to-1 to a future markdown file. The data model below
captures every field of the template:

```markdown
# Module – <Title>

## Scope
### In scope
- <capability or responsibility that belongs to this module>
### Out of scope
- <neighbouring concern explicitly excluded, with a note on which module owns it>

## Actors and Dependencies
| Actor / System | Relationship | Notes |

## Responsibilities
- <responsibility 1 — maps to ≥1 FRS>
- <responsibility 2>

## Interfaces
### UI Surfaces
| Surface | User Role | Purpose | FRS |

### APIs
| Direction | Type | Counterpart | Purpose | FRS |

### Events
| Direction | Event Name | Counterpart | Purpose | FRS |

## Data
| Entity | Business Purpose | Source of Truth |

## FRS in this module
| FRS ID | Title | Priority | Status |
```

---

## 3. Inputs (what Stage A consumes)

The skill's authoritative inputs are listed in `SKILL.md` as **BRD + NFR + Architecture
Design**. In v1 of SpecForge:

- **Validated BRD** is the primary structured input — all 22 typed tables (objectives,
  stakeholders, actors, scope items, BRs, KPIs, risks, etc.). The `BrdLayer` of the context
  bundle formats this for LLM consumption.
- **NFR** and **Architecture Design** are **optional** for v1. They live as PageIndex-indexed
  project documents (filename patterns `nfr*`, `architecture*`, `technical-design*`). If
  present, they ground the modularization. If absent, the validator emits a non-blocking
  "NFR coverage unknown" warning.
- **App Brain facts** — every in-scope app's facts.
- **Validated Concept Brief** — for the WHY behind decisions.
- **FRS discover Q&A** — 12 questions across 6 categories (see §6.4).
- **User brief** — optional textarea on the Stage A empty state ("MVP for claims chatbot —
  focus on intake + triage flows").

### Context Bundle additions (compared to BRD generation)

The `ProjectContextBundle` (defined in `backend/app/services/context/project_context.py`) gains
a **4th layer** for FRS generation:

```python
@dataclass
class BrdLayer:
    brd_document_id: str | None
    brd_status: str | None       # must be "validated" for FRS readiness
    brd_validated_at: str | None
    brd_snapshot_key: str | None

    # All current, active rows from the validated BRD, formatted as dicts:
    text_blocks: list[dict]       # business_context, problem_statement
    objectives: list[dict]
    stakeholders: list[dict]
    actors: list[dict]
    scope_items: list[dict]
    process_steps: list[dict]     # asis + tobe
    business_requirements: list[dict]  # the KEYSTONE
    data_entities: list[dict]
    report_requirements: list[dict]
    assumptions: list[dict]
    constraints: list[dict]
    dependencies: list[dict]
    risks: list[dict]
    phases: list[dict]
    milestones: list[dict]
    kpis: list[dict]
    open_questions: list[dict]
    decisions: list[dict]
    references: list[dict]
    glossary_entries: list[dict]
    traceability: list[dict]       # all BrdTraceability rows for outward back-references

    formatted_context: str         # full BRD projection ready for prompt injection


# ProjectContextBundle is extended:
@dataclass
class ProjectContextBundle:
    project_id: str
    project_name: str
    business_unit: str
    apps: AppLayer
    docs: DocsLayer
    cb: CbLayer
    brd: BrdLayer | None          # NEW — required when artifact_type == "frs"
    readiness: BundleReadiness
    snapshot_timestamp: str
```

`BundleReadiness._compute_readiness()` gains:

```python
brd_ready = (artifact_type != "frs") or (brd is not None and brd.brd_status == "validated")
can_generate = docs_all_ready and cb_ready and brd_ready
```

`gather_project_context(project_id, db, artifact_document_id, artifact_type='brd' or 'frs')`
loads BrdLayer in parallel with the existing layers when `artifact_type == 'frs'`.

---

## 4. Outputs (what Stage A produces)

### 4.1 Modules (~5–12 typically)

Each module is a row in `frs_modules` plus its child rows in actor/responsibility/interface/
data-entity tables. The full schema is in §5.

**Module row_key convention**:
- `MOD-001`, `MOD-002`, … for feature modules (Layer = `vertical` or `cross_cutting`)
- `MOD-000` reserved for the auto-created **Cross-cutting Standards** module (Layer = `foundation`)
- The LLM may produce up to 14 modules in v1 (the validator emits a Warning beyond that)

### 4.2 FRS backlog stubs (~3–15 per module)

Each backlog stub is a row in `frs_specs` with **stub-level** content only:
- `row_key`: `M001-FRS001`, `M001-FRS002`, … (zero-padded, module-prefixed)
- `title`: a concise human-readable name
- `priority`: P0 | P1 | P2 | P3
- `br_refs`: JSONB list of BR row_keys this stub will trace to
- `module_row_key`: the owning module
- All section-content fields (narrative, screens, endpoints, etc.) = empty
- `completeness`: 0

Stage B (in `prd-e4c-frs-functional-design.md`) fills in the rest.

### 4.3 Cross-module contracts

Recorded as `frs_module_interfaces` rows with `direction = inbound | outbound`. The validator
checks that for every `outbound` interface in module A targeting module B, there is a
corresponding `inbound` interface in module B from A (symmetry). Mutual `inbound` /
`outbound` loops between two modules are a critical finding (cycle in cross-module contracts).

### 4.4 [SPEC-DECISION] questions

Decision-grade ambiguities about module boundaries are emitted as `frs_spec_decisions` rows
with `module_row_key` set and `spec_row_key = NULL`. Each has:
- `question`: e.g., "Should email verification be part of User Onboarding or split into a separate Email module?"
- `options`: JSONB list of 2–4 `{label, description, implications}` objects
- `recommended_index`: AI's pick (0-based)
- `recommended_rationale`: why
- `resolution_status`: `open` until user confirms / overrides / dismisses

These are **non-blocking** by default — the AI picks `recommended_index` and proceeds. Open
decisions become warnings at validate time (not majors).

---

## 5. Data model (tables Stage A owns)

All tables use the existing `VersionedRowMixin` (shared columns `id`, `document_id`, `row_key`,
`version`, `is_current`, `is_locked`, `status` enum `active|removed`, `source` enum `ai|human`,
`created_by`, `created_at`).

### 5.1 `frs_modules`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `MOD-001`; `MOD-000` reserved for Cross-cutting Standards |
| `name` | Text | "User Onboarding" — must be capability/role language |
| `slug` | Text | URL-safe `user-onboarding` |
| `layer` | enum `frs_module_layer` | `foundation | vertical | cross_cutting` |
| `scope_in` | Text | bullet narrative; what this module owns |
| `scope_out` | Text | bullet narrative; neighbouring concerns explicitly excluded |
| `summary` | Text | 2–3 sentences describing the module |
| `figma_root_link` | Text \| NULL | optional module-level Figma file URL (Stage B uses per-screen `figma_link` instead) |
| `completeness` | Int | 0–100 (AI confidence in the decomposition) |
| `confidence` | Text | `high | medium | low` |

### 5.2 `frs_module_actors`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `MOD-001-ACT-1` |
| `module_row_key` | Text | FK to `frs_modules.row_key` (same document_id) |
| `actor_name` | Text | "Customer", "Auth Module", "Email Service" — capability/role language only |
| `relationship` | enum `frs_actor_relationship` | `primary_user | dependency | external_system | downstream_consumer` |
| `notes` | Text | one-line context, e.g. "Initiates registration" |

### 5.3 `frs_module_responsibilities`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `MOD-001-R-1` |
| `module_row_key` | Text | FK |
| `responsibility` | Text | business-language statement, e.g. "Validate uniqueness of email address" |
| `frs_refs` | JSONB list[Text] | FRS backlog stub row_keys this responsibility maps to |

### 5.4 `frs_module_interfaces`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `MOD-001-IF-1` |
| `module_row_key` | Text | FK |
| `interface_kind` | enum `frs_interface_kind` | `ui_surface | api | event` |
| `direction` | enum `frs_interface_direction` \| NULL | `inbound | outbound`; NULL for `ui_surface` |
| `transport` | Text \| NULL | `rest | grpc | mq | webhook | event_bus`; NULL for `ui_surface` |
| `name` | Text | "Registration page", "Validate Email API", "customer_registered event" |
| `counterpart` | Text \| NULL | which module/system on the other side (NULL for `ui_surface` if external-only) |
| `user_role` | Text \| NULL | for `ui_surface` only |
| `purpose` | Text | one-line |
| `frs_ref` | Text \| NULL | the FRS spec row_key (Stage B's) that owns the full contract |

### 5.5 `frs_module_data_entities`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `MOD-001-E-1` |
| `module_row_key` | Text | FK |
| `entity_name` | Text | "customer_profile" — conceptual name, not table name |
| `business_purpose` | Text | "Stores onboarding completion state per customer" |
| `source_of_truth` | Text | which module/system owns the canonical copy |

### 5.6 `frs_specs` (stub form only — full form in Stage B)

| Column | Type | Notes (Stage A populates only) |
|--------|------|--------------------------------|
| (versioning) | — | row_key e.g. `M001-FRS001` |
| `module_row_key` | Text | FK to `frs_modules.row_key` |
| `title` | Text | "User Registration" |
| `priority` | enum `frs_priority` | `P0 | P1 | P2 | P3` |
| `layer` | enum `frs_module_layer` | mirrors owning module's layer |
| `br_refs` | JSONB list[Text] | BR row_keys this stub will trace to |
| `nfr_refs` | JSONB list[Text] | empty in Stage A (Stage B may fill) |
| `depends_on` | JSONB list[Text] | empty in Stage A (Stage B may fill) |
| `narrative` | Text | empty in Stage A |
| `independent_test` | Text | empty in Stage A |
| `data_and_validation` | Text | empty in Stage A |
| `errors_and_edge_cases` | Text | empty in Stage A |
| `observability` | Text | empty in Stage A |
| `implementation_tasks` | JSONB | empty in Stage A |
| `completeness` | Int | 0 in Stage A (Stage B updates) |
| `confidence` | Text | `low` in Stage A |

### 5.7 `frs_spec_decisions` (module-scoped only in Stage A)

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `MOD-001-DEC-1` |
| `spec_row_key` | Text \| NULL | NULL when module-scoped (Stage A); set in Stage B |
| `module_row_key` | Text \| NULL | set when module-scoped (Stage A); NULL when spec-scoped |
| `question` | Text | "Should email verification be part of User Onboarding or split out?" |
| `options` | JSONB list[{label, description, implications}] | 2–4 choices |
| `recommended_index` | Int | AI's pick (0-based) |
| `recommended_rationale` | Text | why AI picks this |
| `user_chosen_index` | Int \| NULL | NULL until user resolves |
| `resolution_status` | enum `frs_decision_status` | `open | accepted_ai | overridden | dismissed` |

### 5.8 New enums (in migration `0019_frs_artifact.py`)

- `frs_module_layer` (`foundation`, `vertical`, `cross_cutting`)
- `frs_actor_relationship` (`primary_user`, `dependency`, `external_system`, `downstream_consumer`)
- `frs_interface_kind` (`ui_surface`, `api`, `event`)
- `frs_interface_direction` (`inbound`, `outbound`)
- `frs_priority` (`P0`, `P1`, `P2`, `P3`)
- `frs_decision_status` (`open`, `accepted_ai`, `overridden`, `dismissed`)

The remaining enums (`frs_http_method`, `frs_trace_kind`) are created in the same migration but
used only by Stage B.

### 5.9 Why use the versioned-row mixin

Modules and their sub-rows are user-editable, lockable, and history-visible. Mirrors the BRD
pattern: when a user edits a module's scope statement, a new version is created with old set
to `is_current=False`. Locked modules are preserved verbatim when "Re-modularize all" runs.

---

## 6. Backend implementation

### 6.1 Files (all under `backend/app/`)

| Path | Purpose | New / Extend |
|------|---------|--------------|
| `models/frs.py` | All FRS models — but Stage A uses only the 6 tables above + `FrsSpecDecision` (module-scope) | new (full file with all 14 tables for both stages) |
| `alembic/versions/0019_frs_artifact.py` | Creates all 14 tables + enums | new |
| `services/context/brd_layer.py` | Builds `BrdLayer` (reads validated BRD, formats prompt context) | new (mirrors `cb_layer.py`) |
| `services/context/project_context.py` | Add `BrdLayer`; update `gather_project_context` and `_compute_readiness` | extend |
| `services/context/projection.py` | Add `project_for_unit("frs", "modularize", …)` projection | extend |
| `services/artifacts/manifest/frs.py` | `FrsUnitSpec` for `"modularize"`; `FRS_TABLE_MAP`; `FRS_UNIT_DISCOVER_MAP` | new |
| `services/skills/dspy_frs.py` | `FrsModularizeSignature` + `FrsModularizeModule` + `run_modularize`. (Stage B also lives here but separate Signature) | new |
| `services/llm/fixtures/frs_modularize.json` | Mock fixture for Stage A | new (hand-written) |
| `services/artifacts/frs_orchestrator.py` | `generate_frs_modularize()`, `_ensure_frs_document()`, persistence helpers; Stage B's `generate_frs_design_module` is in same file (separate concern) | new (cloned from `brd_orchestrator.py` shape) |
| `services/artifacts/validators/frs.py` | Stage-A rules (zero modules, sizing warnings, BR coverage by backlog) + Stage-B rules (see other PRD) | new (full file covers both stages) |
| `services/artifacts/discover_catalog.py` | Add `FRS_DISCOVER_QUESTIONS` (12 Qs) and `FRS_UNIT_DISCOVER_MAP` | extend |
| `api/frs.py` | API routes (Stage-A subset listed below + Stage-B routes from other PRD) | new (covers both stages) |
| `workers/tasks.py` | Add `generate_frs` Celery task (dispatches to `generate_frs_all`) | extend |
| `workers/dispatch.py` | Register `generate_frs` | extend |
| `main.py` | Mount `api/frs.py` router | extend (one line) |

### 6.2 The `FrsModularizeSignature` (DSPy)

```python
# backend/app/services/skills/dspy_frs.py

class FrsActorRow(BaseModel):
    actor_name: str
    relationship: Literal["primary_user", "dependency", "external_system", "downstream_consumer"]
    notes: str = ""

class FrsResponsibilityRow(BaseModel):
    responsibility: str
    frs_refs: list[str] = Field(default_factory=list, description="FRS backlog stub row_keys this maps to")

class FrsInterfaceRow(BaseModel):
    interface_kind: Literal["ui_surface", "api", "event"]
    direction: Literal["inbound", "outbound"] | None = None  # None for ui_surface
    transport: Literal["rest", "grpc", "mq", "webhook", "event_bus"] | None = None
    name: str
    counterpart: str | None = None
    user_role: str | None = None
    purpose: str
    frs_ref: str | None = None  # set after backlog stubs are generated

class FrsModuleDataRow(BaseModel):
    entity_name: str
    business_purpose: str
    source_of_truth: str

class FrsBacklogStub(BaseModel):
    row_key: str           # "M001-FRS001"
    title: str
    priority: Literal["P0", "P1", "P2", "P3"]
    br_refs: list[str]     # BR row_keys this stub will trace to (≥1 required)
    description: str       # 1–2 sentence stub description; Stage B expands

class FrsModuleInventoryRow(BaseModel):
    row_key: str           # "MOD-001"
    name: str
    slug: str
    layer: Literal["foundation", "vertical", "cross_cutting"]
    scope_in: str
    scope_out: str
    summary: str
    actors: list[FrsActorRow]
    responsibilities: list[FrsResponsibilityRow]
    interfaces: list[FrsInterfaceRow]
    data_entities: list[FrsModuleDataRow]
    frs_backlog: list[FrsBacklogStub]  # 2–15 stubs; validator warns outside this range

class FrsSpecDecisionRow(BaseModel):
    row_key: str           # "MOD-001-DEC-1"
    question: str
    options: list[dict]    # [{label, description, implications}]
    recommended_index: int
    recommended_rationale: str

class FrsOpenQuestion(BaseModel):
    question: str
    field: str
    why: str
    example: str = ""

class FrsModularizeOutput(BaseModel):
    modules: list[FrsModuleInventoryRow]
    spec_decisions: list[FrsSpecDecisionRow] = Field(default_factory=list)
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class FrsModularizeSignature(dspy.Signature):
    """Run Steps 1+2+3 of the FRS-Builder skill: decompose the validated BRD into business-
    capability modules using DDD bounded contexts. Apply the modularization guideline exactly:
    cohesion vs coupling, sizing rules, explicit cross-module contracts, capability/role
    language only.

    HARD RULES:
    - Module names MUST use capability/role language. NEVER use tech-specific names
      (no "API", "DB", "Service", "Lambda", "Kafka", "Postgres", "Microservice", etc.)
    - Modules do NOT integrate via shared internal data models or shared databases. Every
      cross-module dependency MUST appear in BOTH source and target modules' `interfaces`
      (source = outbound, target = inbound, both with the same `name` and `transport`).
    - Do NOT create modules for deployment, CI/CD, infrastructure, environment setup —
      those are architecture concerns, not business capabilities.

    CROSS-CUTTING STANDARDS:
    If you detect ≥2 modules sharing common rules (error envelope, reference data, RBAC base,
    common date/timezone handling, etc.), hoist those rules into a Layer-0 module called
    'Cross-cutting Standards' with `row_key = MOD-000`. Feature modules will reference its
    FRS via `depends_on` in Stage B.

    BACKLOG STUBS:
    For each module, produce a backlog list of 3–15 FRS slices. Each slice must:
    - Have a stub `row_key` of form M001-FRS001, M001-FRS002, … (module-prefixed, zero-padded)
    - Trace to ≥1 BR row_key from the validated BRD (br_refs)
    - Have a 1–2 sentence description that Stage B will expand into full FRS content
    Do NOT write full FRS spec content here — that's Stage B.

    AMBIGUITY:
    For any module boundary you are uncertain about (e.g., should X be its own module or fold
    into Y?), emit a `FrsSpecDecisionRow` with 2–4 MCQ options. Pick `recommended_index`
    based on the simpler/lower-coupling option and proceed; the user can override later.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    brief: str = dspy.InputField(desc="Optional user brief; may be empty")
    brd_context: str = dspy.InputField(desc="Full validated BRD: every row from every BRD table, formatted")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    source_sections: str = dspy.InputField(desc="Retrieved NFR / Architecture doc sections (if uploaded), else empty")
    qa_pairs: str = dspy.InputField(desc="FRS discover Q&A answers")
    current_modules: str = dspy.InputField(desc="JSON of existing modules for idempotent regen; empty on first run")
    locked_modules: str = dspy.InputField(desc="JSON of locked modules to preserve verbatim")
    result: FrsModularizeOutput = dspy.OutputField()


class FrsModularizeModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.ChainOfThought(FrsModularizeSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_modularize(**kwargs) -> dict:
    if _is_mock():
        return _load_fixture("frs_modularize")
    _configure()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: FrsModularizeModule()(**kwargs))
```

### 6.3 The orchestrator's modularize flow

```python
# backend/app/services/artifacts/frs_orchestrator.py

async def generate_frs_modularize(
    project: Project,
    doc: ArtifactDocument,
    bundle: ProjectContextBundle,
    db: AsyncSession,
) -> dict:
    """Phase A: decompose BRD into modules + backlog stubs."""
    # Project context for the modularize unit
    unit_ctx = project_for_unit(bundle, "frs", "modularize")

    # Gather discover Q&A for FRS questions only
    qa_pairs = await _gather_frs_unit_qa(doc.id, "modularize", db)

    # Current + locked rows (for idempotent regen)
    current_modules = await _current_frs_modules_with_children(doc.id, db)
    locked_modules = [m for m in current_modules if m.get("is_locked")]

    result = await run_modularize(
        project_name=project.name,
        business_unit=project.business_unit or "—",
        brief=await _read_frs_brief(doc.id, db),  # from artifact_messages with meta.is_initial_brief
        brd_context=bundle.brd.formatted_context if bundle.brd else "(no BRD)",
        cb_context=bundle.cb.formatted_context,
        app_brain=bundle.apps.formatted_context,
        source_sections=unit_ctx.doc_sections,  # NFR/Architecture-filtered doc sections
        qa_pairs=qa_pairs,
        current_modules=json.dumps(current_modules),
        locked_modules=json.dumps(locked_modules),
    )

    # Persist modules + child rows + backlog stubs
    await _persist_modularize_result(doc.id, result, db)

    # Atomic unit_status merge
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) || CAST(:patch AS jsonb), "
        "    updated_at = NOW() WHERE id = :doc_id"
    ), {
        "patch": json.dumps({"modularize": {
            "completeness": result.get("completeness", 0),
            "confidence": result.get("confidence", "low"),
        }}),
        "doc_id": str(doc.id),
    })

    # Emit messages for any open SpecDecisions and OpenQuestions
    await _emit_module_decision_messages(doc, result, db)
    return result


async def _persist_modularize_result(document_id, result, db):
    """Route output to the 6 Stage-A tables in transactional order."""
    for module in result.get("modules", []):
        # 1. Upsert module row
        await upsert_frs_rows("frs_modules", document_id, [{
            "row_key": module["row_key"],
            "name": module["name"],
            "slug": module["slug"],
            "layer": module["layer"],
            "scope_in": module["scope_in"],
            "scope_out": module["scope_out"],
            "summary": module["summary"],
            "completeness": result.get("completeness", 0),
            "confidence": result.get("confidence", "low"),
        }], "ai", db)

        # 2. Actors
        actor_rows = []
        for i, a in enumerate(module.get("actors", []), 1):
            actor_rows.append({
                "row_key": f"{module['row_key']}-ACT-{i}",
                "module_row_key": module["row_key"],
                **a,
            })
        await upsert_frs_rows("frs_module_actors", document_id, actor_rows, "ai", db)

        # 3. Responsibilities, 4. Interfaces, 5. Data entities — same pattern

        # 6. Backlog stubs in frs_specs (stub form)
        spec_stubs = []
        for stub in module.get("frs_backlog", []):
            spec_stubs.append({
                "row_key": stub["row_key"],
                "module_row_key": module["row_key"],
                "title": stub["title"],
                "priority": stub["priority"],
                "layer": module["layer"],
                "br_refs": stub["br_refs"],
                "nfr_refs": [],
                "depends_on": [],
                "narrative": "",  # Stage B fills
                "completeness": 0,
                "confidence": "low",
            })
        await upsert_frs_rows("frs_specs", document_id, spec_stubs, "ai", db)

    # SpecDecisions (module-scoped)
    decisions = []
    for i, d in enumerate(result.get("spec_decisions", []), 1):
        decisions.append({
            "row_key": d.get("row_key", f"MOD-DEC-{i}"),
            "module_row_key": d.get("module_row_key"),  # set by AI; module-scoped here
            "spec_row_key": None,
            "question": d["question"],
            "options": d["options"],
            "recommended_index": d["recommended_index"],
            "recommended_rationale": d["recommended_rationale"],
            "user_chosen_index": None,
            "resolution_status": "open",
        })
    await upsert_frs_rows("frs_spec_decisions", document_id, decisions, "ai", db)
```

### 6.4 Discover catalog additions (the 12 FRS questions)

Added to `backend/app/services/artifacts/discover_catalog.py`:

```python
FRS_DISCOVER_CATEGORIES = [
    {"key": "scope",         "emoji": "🎯", "label": "Scope"},
    {"key": "personas",      "emoji": "👥", "label": "Personas"},
    {"key": "integrations",  "emoji": "🔄", "label": "Integrations"},
    {"key": "data",          "emoji": "📊", "label": "Data"},
    {"key": "nfrs",          "emoji": "⚡", "label": "NFRs"},
    {"key": "security",      "emoji": "🛡",  "label": "Security"},
    {"key": "errors",        "emoji": "⚠",  "label": "Errors"},
    {"key": "ui",            "emoji": "🎨", "label": "UI"},
    {"key": "delivery",      "emoji": "🚀", "label": "Delivery"},
]

FRS_DISCOVER_QUESTIONS = [
    # 🎯 Scope (2)
    {"key": "frs_1a", "category": "scope", "question": "What user workflows are P0 in this FRS bundle?", "why": "Drives module scope_in", "example": "Customer registration, claim submission, status check"},
    {"key": "frs_1b", "category": "scope", "question": "Any modules you'd like to be pre-defined?", "why": "Locks high-confidence boundaries", "example": "Notifications module should exist as its own unit"},
    # 👥 Personas (1)
    {"key": "frs_2a", "category": "personas", "question": "Who are the primary roles?", "why": "Drives actor decomposition", "example": "Customer, Claims Operator, Auditor, System (chatbot)"},
    # 🔄 Integrations (2)
    {"key": "frs_3a", "category": "integrations", "question": "Which external systems will the modules call?", "why": "Drives outbound API interfaces", "example": "Email service, CRM, payment gateway, KYC provider"},
    {"key": "frs_3b", "category": "integrations", "question": "Sync API or async events for cross-module communication?", "why": "Drives interface transport choice", "example": "Async events for notifications; sync REST for everything else"},
    # 📊 Data (1)
    {"key": "frs_4a", "category": "data", "question": "Source of truth for the main entities? Read vs write patterns?", "why": "Drives data ownership in modules", "example": "customer_profile owned by Customer module; read by all"},
    # ⚡ NFRs (1)
    {"key": "frs_5a", "category": "nfrs", "question": "Latency / availability / scalability targets you care about?", "why": "Drives system-view constraints", "example": "P99 < 500ms for claim status; 99.9% uptime"},
    # 🛡 Security (2)
    {"key": "frs_6a", "category": "security", "question": "Auth/RBAC model? Data sensitivity per entity?", "why": "Drives Cross-cutting Standards module", "example": "OAuth2; customer PII redacted in logs"},
    {"key": "frs_6b", "category": "security", "question": "Audit / compliance requirements that drive design?", "why": "Drives audit-trail responsibilities", "example": "All claim mutations logged for 7 years (SOX)"},
    # ⚠ Errors (1)
    {"key": "frs_7a", "category": "errors", "question": "Failure-handling strategy — retry, queue, fail-fast?", "why": "Drives Cross-cutting error envelope", "example": "Idempotent retry with exponential backoff for transient errors; fail-fast for validation"},
    # 🎨 UI (1)
    {"key": "frs_8a", "category": "ui", "question": "Will Figma designs be provided? Where?", "why": "Sets expectations for Stage B Figma gate", "example": "Yes, will share Figma links per screen during Stage B"},
    # 🚀 Delivery (1)
    {"key": "frs_9a", "category": "delivery", "question": "Phasing — which modules must ship first?", "why": "Influences priority ordering", "example": "Phase 1: customer registration + intake; Phase 2: triage; Phase 3: analytics"},
]

FRS_UNIT_DISCOVER_MAP = {
    "modularize": ["frs_1a", "frs_1b", "frs_2a", "frs_3a", "frs_3b", "frs_4a", "frs_9a"],
    # Stage B's "design_module" unit uses: ["frs_4a", "frs_5a", "frs_6a", "frs_6b", "frs_7a", "frs_8a"]
}
```

### 6.5 Validation rules (Stage A only)

In `backend/app/services/artifacts/validators/frs.py`, the Stage-A subset of `run_frs_validation`:

```python
async def _validate_stage_a(document_id, doc, db) -> list[dict]:
    findings = []

    modules = await _active_rows(FrsModule, document_id, db)

    # CRITICAL
    if len(modules) == 0:
        findings.append(_finding(
            check_id="zero_modules", group="critical",
            description="No modules generated. Stage A must produce ≥1 module before Stage B can run.",
            suggested_fix="Re-run Stage A modularization. If still empty, check that BRD is validated and discover Q&A is sufficient.",
        ))

    # Module-level checks
    for m in modules:
        # Capability-language enforcement (heuristic — flagged words)
        tech_tokens = ["api", "db", "service", "lambda", "kafka", "postgres", "redis", "microservice", "gateway"]
        if any(tok in m.name.lower() for tok in tech_tokens):
            findings.append(_finding(
                check_id="module_tech_name", group="major", row_key=m.row_key,
                description=f"Module '{m.name}' uses tech-specific language. Use capability/role names.",
                suggested_fix="Rename to a business capability (e.g., 'Authentication' not 'Auth API').",
            ))

        # Backlog stub count
        stubs = await _active_specs_for_module(document_id, m.row_key, db)
        if len(stubs) == 0:
            findings.append(_finding(
                check_id="module_zero_backlog", group="critical", row_key=m.row_key,
                description=f"Module {m.row_key} '{m.name}' has zero FRS backlog stubs. Cannot proceed to Stage B.",
                suggested_fix="Re-run modularize for this module, or manually add at least one FRS stub.",
            ))
        elif len(stubs) < 2:
            findings.append(_finding(
                check_id="module_under_decomposed", group="warnings", row_key=m.row_key,
                description=f"Module {m.row_key} has only {len(stubs)} stub. May indicate under-decomposition.",
                suggested_fix="Consider merging this module into another, or expanding its backlog.",
            ))
        elif len(stubs) > 15:
            findings.append(_finding(
                check_id="module_over_loaded", group="warnings", row_key=m.row_key,
                description=f"Module {m.row_key} has {len(stubs)} stubs. May indicate over-loading.",
                suggested_fix="Consider splitting this module by sub-capability or lifecycle stage.",
            ))

    # Cross-module contract symmetry (cycles)
    interfaces = await _all_interfaces(document_id, db)
    cycle = _detect_cross_module_cycle(interfaces)
    if cycle:
        findings.append(_finding(
            check_id="cross_module_cycle", group="critical",
            description=f"Cyclic dependency between modules detected: {' → '.join(cycle)}",
            suggested_fix="Decouple via async events or extract shared logic into a Cross-cutting Standards module.",
        ))

    # BR coverage (every Must-priority BR must be referenced by ≥1 backlog stub)
    must_brs = await _must_priority_brs_of_validated_brd(document_id, db)
    covered_brs = await _br_refs_referenced_by_any_stub(document_id, db)
    uncovered = set(must_brs) - covered_brs
    for br_key in uncovered:
        findings.append(_finding(
            check_id="br_uncovered_in_modules", group="coverage", target_ref=br_key,
            description=f"BR {br_key} (Must priority) is not referenced by any FRS backlog stub.",
            suggested_fix="Re-run modularize with an explicit hint, or manually add a stub referencing this BR.",
        ))

    # Open decisions
    decisions = await _active_rows_by_status(FrsSpecDecision, document_id, "open", db,
                                              filter_module_scoped=True)
    for d in decisions:
        findings.append(_finding(
            check_id="open_module_decision", group="warnings", row_key=d.row_key,
            description=f"Decision '{d.question[:80]}…' is unresolved. AI recommends option {d.recommended_index}.",
            suggested_fix="Confirm AI's recommendation or override via the Decision panel.",
        ))

    return findings
```

### 6.6 API endpoints (Stage-A subset)

In `backend/app/api/frs.py`:

```
GET    /projects/{id}/artifacts/frs                              → detail (modules + stubs + messages)
POST   /projects/{id}/artifacts/frs/readiness                    → BrdBundleReadiness (4 layers)
POST   /projects/{id}/artifacts/frs/generate                     → full pipeline; Stage A + Stage B
POST   /projects/{id}/artifacts/frs/modularize                   → Stage A only (re-run)
POST   /projects/{id}/artifacts/frs/reset-generating             → safety hatch

POST   /projects/{id}/artifacts/frs/decisions/{dec_row_key}/resolve  → resolve [SPEC-DECISION] (module-scoped here)

POST   /projects/{id}/artifacts/frs/answer                       → user free-text answer; dispatches incorporate_frs_answer Celery task
POST   /projects/{id}/artifacts/frs/discover/analyze
POST   /projects/{id}/artifacts/frs/discover/{q_key}/answer
POST   /projects/{id}/artifacts/frs/discover/enhance

# Generic row CRUD (works for any FRS table, including the 6 Stage-A tables)
POST   /projects/{id}/artifacts/frs/{table}/{row_id}/edit
POST   /projects/{id}/artifacts/frs/{table}/{row_id}/delete
POST   /projects/{id}/artifacts/frs/{table}/{row_id}/restore
POST   /projects/{id}/artifacts/frs/{table}/{row_id}/unlock
GET    /projects/{id}/artifacts/frs/{table}/{row_id}/history

GET    /projects/{id}/artifacts/frs/findings                     → returns Stage-A + Stage-B findings combined
```

The `/validate` endpoint commits the artifact as `validated` only after **both** stages pass.
For Stage A alone, the user can run `/findings` and see only Stage-A findings (the Stage-B
rules are skipped when no specs have been designed yet).

### 6.7 Celery task

```python
# backend/workers/tasks.py

@celery_app.task(name="generate_frs", bind=True)
def generate_frs(self, project_id: str):
    return _run_async(_generate_frs(uuid.UUID(project_id)))

async def _generate_frs(project_id: uuid.UUID):
    async with AsyncSessionLocal() as db:
        project = (await db.execute(
            select(Project).where(Project.id == project_id)
        )).scalar_one()
        await generate_frs_all(project, db)
```

`generate_frs_all` (defined in the orchestrator) runs Stage A and then Stage B in sequence.
This PRD's stage is the Stage-A portion; Stage B is in the other PRD.

---

## 7. Frontend implementation (Stage A)

### 7.1 Files (under `frontend/`)

| Path | Purpose | New / Extend |
|------|---------|--------------|
| `lib/types.ts` | `FrsModuleRow`, `FrsModuleActorRow`, `FrsModuleResponsibilityRow`, `FrsModuleInterfaceRow`, `FrsModuleDataEntityRow`, `FrsSpecRow` (stub form), `FrsSpecDecisionRow`, `FrsDetail`, `FrsBundleReadiness` | extend |
| `lib/frs-manifest.ts` | `FRS_DISCOVER_CATEGORIES`, `FRS_MODULE_LAYER_LABELS`, `FRS_PRIORITY_COLORS`, `FRS_INTERFACE_KIND_STYLES` | new |
| `lib/api.ts` | `api.frs.*` namespace (Stage-A subset listed above) | extend |
| `lib/hooks/useFrsReadiness.ts` | SWR hook polling readiness; checks BRD validated + docs ready | new |
| `app/components/frs/FrsBuilderView.tsx` | Root component; mounts Stage-A surfaces when no specs yet exist | new |
| `app/components/frs/FrsEmptyState.tsx` | Stage 1 (empty state) | new |
| `app/components/frs/FrsModularizeTheater.tsx` | Stage 3 — Stage-A-only generation theater (single-unit progress) | new |
| `app/components/frs/FrsModuleRail.tsx` | Module rail with expandable rows (Stage A only shows modules + stub count; Stage B adds individual spec rows) | new |
| `app/components/frs/FrsModulePanel.tsx` | Module panel with all 5 sections + backlog table | new |
| `app/components/frs/FrsBacklogTable.tsx` | The "FRS in this module" table — stubs with priority and BR refs; clickable but greys out content until Stage B | new |
| `app/components/frs/FrsBrdEchoStrip.tsx` | BRD essence row below SourceStrip | new |
| `app/components/frs/FrsModuleDecisionPrompt.tsx` | MCQ Radix popover for module-scoped [SPEC-DECISION] | new |
| `app/components/frs/FrsModularizeFindings.tsx` | Stage-A findings drawer (simpler version of Stage B's; only critical/major/warnings groups visible here) | new |
| `app/components/brd/SourceStrip.tsx` | Extend with optional 4th row for BRD layer | extend |
| `app/projects/[id]/artifacts/frs/page.tsx` | Thin route wrapper for `FrsBuilderView` | new |
| `app/projects/[id]/page.tsx` | Update FRS chip badge logic; gate on `brdValidated` | extend |

### 7.2 Workspace chip update

```tsx
// app/projects/[id]/page.tsx

const { data: brdDetail } = useSWR(`brd-detail-${projectId}`, () => api.brd.get(projectId), {revalidateOnFocus: false})
const { data: frsDetail } = useSWR(`frs-detail-${projectId}`, () => api.frs.get(projectId), {revalidateOnFocus: false})
const brdValidated = brdDetail?.document?.status === 'validated'
const frsStatus = frsDetail?.document?.status ?? null

function frsStatusBadge() {
  if (!frsStatus) return null
  if (frsStatus === 'generating') return <span className="...animate-pulse">Generating…</span>
  if (frsStatus === 'validated')  return <span className="text-emerald-700">Validated ✓</span>
  if (frsStatus === 'in_interview') return <span className="text-amber-700">Draft</span>
  return null
}

const frsSublabel = !frsStatus
  ? (brdValidated ? 'Functional Specifications' : 'Unlocks after BRD')
  : frsStatus === 'generating' ? 'Generating…'
  : frsStatus === 'validated' ? 'Validated'
  : 'Draft · in progress'

<NavItem
  label="FRS"
  sublabel={frsSublabel}
  icon={<Layers size={14} />}
  active={view === 'frs'}
  locked={!brdValidated}
  badge={frsStatusBadge()}
  onClick={brdValidated ? () => setView('frs') : undefined}
/>
```

### 7.3 Stage A — empty state UX

```
                          ✦
                Build the Functional Specifications

   Decompose the validated BRD into business-capability modules. Stage 1 of 2.
   (Stage 2 — per-module design — runs automatically after Stage 1 completes.)

   ⚡ Grounded in:  2 apps · 5 docs · CB v2 · BRD v1 (validated 2 days ago)

   ┌──────────────────────────────────────────────────────────────────────┐
   │ Optional brief — what's the focus of this FRS bundle?               │
   │ (e.g., "MVP for claims chatbot — focus on intake + triage flows")   │
   │                                                  [✦ AI Enhance]      │
   └──────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────────────────────────────────────────────────────┐
   │ ℹ  NFR / Architecture docs (optional but recommended):              │
   │    Upload any file named nfr*, architecture*, technical-design*      │
   │    currently detected: 0 files matching                              │
   │    [Upload now]                                                       │
   └──────────────────────────────────────────────────────────────────────┘

                       [  Discover & Continue →  ]
                       (disabled if BRD not validated OR docs pending)
```

`AI Enhance` is a one-shot button that calls `POST /artifacts/frs/discover/enhance` with the
current brief text + BRD context, returns an LLM-polished version. Same pattern as BRD.

### 7.4 Stage A — discover UX

Reuses the existing `DiscoverPhase` component. The catalog (12 questions across 9 categories)
is filtered to those mapped to `modularize` in `FRS_UNIT_DISCOVER_MAP` (~7 questions for
Stage A — scope, personas, integrations, data ownership, delivery).

The "Why this matters" tooltip per question explains which module field uses the answer:
- `frs_1a` → "Drives the scope_in of feature modules"
- `frs_3a` → "Drives outbound API interfaces in feature modules"
- etc.

### 7.5 Stage A — generation theater

A single-unit progress card (simpler than Stage B's parallel grid):

```
┌────────────────────────────────────────────────────────────────────────┐
│  Stage 1 of 2 — Modularizing your BRD…              est. 30–60 s       │
│                                                                         │
│  ◐ modularize  · grounded in: BRD (14 BRs) · 7 discover answers        │
│                                                                         │
│  Once complete, Stage 2 will design each module's FRS specs.           │
│  [Resume from here]  ← always visible safety hatch                     │
└────────────────────────────────────────────────────────────────────────┘
```

Polls `GET /artifacts/frs` every 2s. When `unit_status.modularize.completeness > 0`, the spinner
flips to ✓ and the screen transitions to the builder.

### 7.6 Stage A — module rail + module panel

The rail shows all modules with stub counts (Stage B will add nested individual spec rows):

```
┌────────────────────────────────┐
│ MODULES                        │
│                                │
│ ▶ MOD-001 User Onboarding (3)  │   ← 3 backlog stubs
│ ▶ MOD-002 Authentication (2)   │
│ ▶ MOD-003 Notifications (4)    │
│ ▶ MOD-000 Cross-cutting (2)    │   ← Layer 0 last
│                                │
│ [+ Add Module]                 │
└────────────────────────────────┘
```

Click a module → opens the **FrsModulePanel** in the right column:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ § MOD-001 · User Onboarding                  [Layer 1 · Vertical Feature]  │
│ Completeness 92% · Confidence high · v1                                     │
│ [Edit metadata] [Regenerate] [Re-modularize all] [🔒 Lock]                  │
│ ──────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│ ▾ Scope                                                                      │
│   In scope: …                                                                │
│   Out of scope: …                                                            │
│                                                                              │
│ ▾ Actors & Dependencies (3 rows)  [+ Add actor]                              │
│   Customer · primary_user · Initiates registration                           │
│   Auth Module · dependency · Validates email format and uniqueness           │
│   Email Service · external_system · Sends verification emails                │
│                                                                              │
│ ▾ Responsibilities (5 rows)  [+ Add]                                         │
│ ▾ UI Surfaces (2 rows)                                                       │
│ ▾ APIs (3 rows: 2 inbound, 1 outbound)                                       │
│ ▾ Events (1 row: customer_registered → Authentication)                       │
│ ▾ Owned Data (2 entities: customer_profile, registration_attempt)            │
│                                                                              │
│ ▾ FRS Backlog (3 stubs)                                                      │
│   ┌─ M001-FRS001 · User Registration  [P0]  br_refs: BR-007, BR-012  Draft  │
│   │  Status: Stub awaiting Stage 2 design                                   │
│   │  [Design now]  ← runs Stage B for this stub only                        │
│   └─ M001-FRS002 · Email Verification [P0]  …                                │
│   [+ Add FRS stub]                                                           │
│                                                                              │
│ ⚠ 1 [SPEC-DECISION] open — "Should email verification be its own module?"   │
│   [Review decision →]  (opens FrsModuleDecisionPrompt)                       │
└────────────────────────────────────────────────────────────────────────────┘
```

Every list section uses `EditableRows` (the same component used in BRD), giving inline
edit/lock/version/restore semantics. The backlog table is special — clicking "Design now"
on a stub triggers Stage B's per-spec generation; clicking the stub itself navigates to
that spec's view (handled by Stage B, see PRD 2).

### 7.7 Stage A — decision prompt

```
┌─ Decision MOD-001-DEC-1 ───────────────────────────── ✕ ─┐
│ Should email verification be part of User Onboarding,   │
│ or split into a separate Email module?                   │
│                                                          │
│ ✦ AI recommends: Option A                                │
│                                                          │
│ ⦿ Option A — Keep in User Onboarding                     │
│   Description: Email verification is a setup step,       │
│   tightly coupled to registration.                       │
│   Implications: Simpler module boundary; no cross-       │
│   module sync needed.                                    │
│                                                          │
│ ◯ Option B — Split into Email module                     │
│   Description: Email Verification + Email Notifications  │
│   share send infrastructure.                             │
│   Implications: Extra cross-module contract; more        │
│   change cost upfront.                                   │
│                                                          │
│ [Accept AI recommendation]  [Override → Option B]        │
│ [Dismiss — not relevant]                                 │
└──────────────────────────────────────────────────────────┘
```

`POST /artifacts/frs/decisions/{dec_row_key}/resolve` with body `{chosen_index, status: 'accepted_ai'|'overridden'|'dismissed'}` records the user choice. If `overridden`, the
orchestrator schedules a re-run of `modularize` so the alternative decomposition gets reflected.

### 7.8 Stage A — findings drawer (simplified)

Only the Stage-A finding groups are shown:

```
┌─ Stage 1 Findings ──────────────────────────────── ✕ ─┐
│ ▾ Critical (0)                                          │
│ ▾ Major (1)                                             │
│   • Module 'Auth API' uses tech-specific language       │
│     [Rename module] [Jump to MOD-002]                   │
│ ▾ Coverage (2)                                          │
│   • BR-014 not referenced by any backlog stub           │
│   • BR-020 not referenced by any backlog stub           │
│     [Re-run modularize with hint]                       │
│ ▾ Warnings (1)                                          │
│   • Decision MOD-001-DEC-1 still open                   │
│     [Review decision]                                   │
│                                                          │
│        [  Continue to Stage 2  ]                         │
│        (enabled when 0 critical/major)                   │
└──────────────────────────────────────────────────────────┘
```

Stage A is **gated** on critical + major findings — Stage B cannot start while any are open.
Coverage and warnings are non-blocking but visible.

---

## 8. Workflow stages (Stage A's user journey)

- **Stage A-0** — Workspace FRS chip lights up when BRD validated.
- **Stage A-1** — Empty state: 4-layer grounding badge + optional brief + NFR/Arch hint.
- **Stage A-2** — Discover phase: 7 questions feeding modularize (subset of all 12 FRS questions).
- **Stage A-3** — Modularize theater: single-unit progress; ~30–60s in real mode, ~2s in mock.
- **Stage A-4** — Builder body: module rail + module panel(s). User can edit, lock, regenerate
  per module or "Re-modularize all".
- **Stage A-5** — Stage-A findings: user resolves critical/major before Stage B can begin.
- **Stage A → Stage B handoff** — auto-cascade by default: after Stage A completes successfully
  (no critical/major findings), Stage B kicks off automatically. Or user can click "Continue to
  Stage 2" explicitly.

The handoff transfers:
- All `frs_modules` rows (with locked status preserved)
- All `frs_module_*` child rows
- All `frs_specs` stub rows (Stage B fills them in)
- All `frs_spec_decisions` rows (open ones become Stage-B warnings if still unresolved)

---

## 9. Defaults & scope decisions (baked in)

1. **Auto-cascade Stage A → Stage B**. First-run runs both back-to-back; user can interrupt the
   theater and re-modularize before Stage B if needed.
2. **[SPEC-DECISION] non-blocking**. AI picks `recommended_index`; user can confirm/override
   later; open decisions become warnings (not majors).
3. **Cross-cutting Standards module: AI-decided**. Auto-hoisted when ≥2 modules share rules.
4. **BR coverage: Must-priority required**. The validator coverage check only enforces that
   `priority='must'` BRs are referenced; Should/Could/Wont BRs are not required to map to any
   stub.
5. **NFR + Architecture: project docs only**. PageIndex-indexed `nfr*`, `architecture*`,
   `technical-design*` filenames feed the modularize unit's `source_sections` input. If absent,
   the validator emits a "NFR coverage unknown" warning (not blocking).

All five decisions are reversible — none requires a schema migration.

---

## 10. Implementation phases

### Phase A1 — Backend (~5 days)

| # | Task | Files |
|---|------|-------|
| A1.1 | Models + Alembic migration (all 14 tables for both stages; Stage A uses 6 + spec stubs) | `models/frs.py`, `alembic/versions/0019_frs_artifact.py` |
| A1.2 | Mock fixture for modularize | `services/llm/fixtures/frs_modularize.json` (3–5 sample modules with backlogs) |
| A1.3 | `BrdLayer` for context bundle | `services/context/brd_layer.py` + extend `project_context.py` |
| A1.4 | FRS discover catalog (12 questions) | extend `services/artifacts/discover_catalog.py` |
| A1.5 | FRS manifest (just `modularize` unit for Stage A) + projection | `services/artifacts/manifest/frs.py` + extend `projection.py` |
| A1.6 | DSPy: `FrsModularizeSignature`, `FrsModularizeModule`, `run_modularize` | `services/skills/dspy_frs.py` (Stage A section) |
| A1.7 | Orchestrator: `_ensure_frs_document`, `generate_frs_modularize`, `_persist_modularize_result` | `services/artifacts/frs_orchestrator.py` (Stage A section) |
| A1.8 | Validator: `_validate_stage_a` | `services/artifacts/validators/frs.py` (Stage A section) |
| A1.9 | API routes (Stage-A subset) | `api/frs.py` (Stage A endpoints), mount in `main.py` |
| A1.10 | Celery `generate_frs` task | extend `workers/tasks.py`, `workers/dispatch.py` |

### Phase A2 — Frontend (~4 days)

| # | Task | Files |
|---|------|-------|
| A2.1 | Types (Stage-A subset) | extend `lib/types.ts` |
| A2.2 | Manifest mirror | `lib/frs-manifest.ts` |
| A2.3 | API client (Stage A endpoints) | extend `lib/api.ts` |
| A2.4 | Readiness hook | `lib/hooks/useFrsReadiness.ts` |
| A2.5 | Empty state | `FrsEmptyState.tsx` |
| A2.6 | Modularize theater | `FrsModularizeTheater.tsx` |
| A2.7 | Module rail + module panel + backlog table | `FrsModuleRail.tsx`, `FrsModulePanel.tsx`, `FrsBacklogTable.tsx` |
| A2.8 | BRD echo strip | `FrsBrdEchoStrip.tsx` |
| A2.9 | Source strip extension (4th row) | extend `app/components/brd/SourceStrip.tsx` |
| A2.10 | Decision prompt | `FrsModuleDecisionPrompt.tsx` |
| A2.11 | Stage-A findings drawer | `FrsModularizeFindings.tsx` |
| A2.12 | Builder view + route | `FrsBuilderView.tsx`, `app/projects/[id]/artifacts/frs/page.tsx` |
| A2.13 | Workspace chip update | extend `app/projects/[id]/page.tsx` |

**Total Stage A**: ~9 calendar days (BE + FE in parallel).

---

## 11. Verification

### 11.1 Mock-mode E2E (no Vertex)

1. `LLM_PROVIDER=mock make dev-be && make dev-fe`. Login `admin@specforge.test`.
2. Use `claims chatbot` project (BRD already validated).
3. Click FRS chip → empty state. **Verify**:
   - Grounding badge: `2 apps · 5 docs · CB v2 · BRD v1`.
   - "NFR/Architecture project docs" hint visible (0 files matching → non-blocking warning).
4. Type optional brief: "MVP for claims intake". Click "Discover & Continue".
5. Discover phase: 7 questions (subset of FRS catalog mapped to `modularize`). Answer 4+.
6. Click "Generate" → modularize theater shows ◐ for ~1s, flips to ✓, transitions to builder.
7. **Verify** in module rail:
   - 4–6 modules with names like "Customer Intake", "Claims Triage", "Notifications", "Cross-cutting Standards".
   - Each module has 3–5 backlog stubs.
   - Cross-cutting Standards module is at Layer 0 (foundation).
8. Click each module → module panel renders all 5 sections + backlog table.
9. Edit one module's `scope_in` → row version bumps to v2.
10. Click "Re-modularize all" → theater re-runs; locked modules preserved verbatim.
11. Click "Check & Validate" (Stage A only) → FrsModularizeFindings drawer opens.
12. Trigger a critical finding manually: delete all backlog stubs from one module → "Module
    MOD-002 has zero backlog stubs" appears under Critical.
13. Trigger a coverage finding: delete a backlog stub that's the only one referencing BR-014 →
    "BR-014 not referenced by any backlog stub" appears under Coverage.
14. Resolve findings → "Continue to Stage 2" button activates (covered in PRD 2).

### 11.2 Real-mode sanity (with Vertex)

- Run steps 1–7 with `LLM_PROVIDER=vertex`. Stage A should complete in ~30–60s.
- Verify the AI:
  - Uses BR row_keys verbatim in `br_refs` of backlog stubs (no fabrications).
  - Hoists a Cross-cutting Standards module when ≥2 modules share rules (mock fixture has this baseline).
  - Produces module names in capability/role language (no tech tokens).
  - Module count is 4–8 typical (not 1, not 20).

### 11.3 Tests

- `LLM_PROVIDER=mock pytest backend/tests/test_frs_modularize.py`:
  - Smoke test calling `generate_frs_modularize` against fixture; asserts 5 modules created
    with non-zero `actors`, `responsibilities`, `interfaces`, `data_entities`, `frs_backlog`.
  - Idempotency test: 2nd call with no changes produces same rows (no v2 created).
  - Lock test: lock a module, re-run modularize, assert locked module is unchanged.
- `pytest backend/tests/test_frs_validator_stage_a.py`:
  - Test capability-language enforcement (module named "Auth API" → major finding).
  - Test BR coverage (Must BR not in any backlog → coverage finding).
  - Test cross-module cycle detection.
- `LLM_PROVIDER=vertex` test (manual, not in CI) — see §11.2.

### 11.4 Performance budget

- Builder TTI ≤ 1.5s on 6-module project.
- Module rail expand/collapse < 16ms/frame.
- Module panel section toggle < 16ms/frame.

### 11.5 Type / lint

- `make typecheck && make lint` green.

### 11.6 Accessibility

- Tab through module rail; every module/stub row is keyboard-reachable.
- VoiceOver reads module name + status correctly.
- Reduced-motion: modularize theater shows static "Generating module 1 of 1…" text instead of
  spinner.

---

## 12. Out of scope (deferred to Stage B / v2)

Covered in `prd-e4c-frs-functional-design.md`:
- Full FRS spec authoring (UI / Backend / Data / Cross-Cutting / Scenarios / FRs / etc.)
- Figma link prompts on individual screens
- Per-spec `frs_screens`, `frs_ui_components`, `frs_endpoints`, `frs_data_entities`,
  `frs_business_rules`, `frs_acceptance_scenarios`, `frs_functional_requirements`,
  `frs_traceability` tables — all owned by Stage B
- Spec-scoped `frs_spec_decisions` (module-scoped decisions are in Stage A)
- The full validation drawer (FRS-level findings: figma link, scenarios ≥6, FR coverage, etc.)
- Coverage galaxy (BR ↔ FRS spec ribbon viz)
- Export bundle (markdown files for modules + specs + traceability)

Permanently deferred (v2+):
- Figma API / MCP fetch (link only in v1)
- Formal NFR Builder artifact (NFRs live in project docs for v1)
- Formal Architecture Builder artifact (same — project docs only)
- Cross-FRS auto-refactor ("extract into Cross-cutting Standards")
- Inline AI single-sentence rewrite

---

## 13. Risks & open UX questions

- **Module count explosion**: If the AI produces 12+ modules, the rail becomes a long scroll.
  Mitigation: validator warning at >10 modules; allow user to merge.
- **Module name drift on re-run**: If user edits a module's `name` then re-modularizes, the AI
  may revert it. Mitigation: editing name should auto-lock the module; re-modularize preserves
  locked modules verbatim.
- **BR coverage gaps for Should/Could BRs**: Validator only enforces Must BRs by design. Mitigation:
  surface a non-blocking coverage report listing all uncovered BRs by priority.
- **Decision spam**: AI may emit too many [SPEC-DECISION] questions, overwhelming the user.
  Mitigation: cap at 5 module-scoped decisions per run; AI must pick `recommended_index`
  confidently.
- **Cross-module symmetry**: Hard to enforce when AI is autonomous. Mitigation: validator
  detects asymmetry as warning; UI shows a "Fix interface symmetry" button that uses an LLM
  follow-up to add the missing inbound/outbound pair.

---

## 14. Appendix · Stage A manifest sketch (`manifest/frs.py`)

```python
@dataclass(frozen=True)
class FrsUnitSpec:
    unit_key: str
    phase: Literal["A", "B"]
    label: str
    writes: list[str]
    depends_on: list[str]
    unit_instruction: str
    discover_question_keys: list[str]


FRS_STAGE_A_UNIT = FrsUnitSpec(
    unit_key="modularize",
    phase="A",
    label="Decompose BRD into modules",
    writes=[
        "frs_modules",
        "frs_module_actors",
        "frs_module_responsibilities",
        "frs_module_interfaces",
        "frs_module_data_entities",
        "frs_specs",            # backlog stubs only
        "frs_spec_decisions",   # module-scoped
    ],
    depends_on=[],
    unit_instruction=...,  # full docstring above
    discover_question_keys=["frs_1a", "frs_1b", "frs_2a", "frs_3a", "frs_3b", "frs_4a", "frs_9a"],
)


FRS_TABLE_MAP_STAGE_A: dict[str, type] = {
    "frs_modules":                 FrsModule,
    "frs_module_actors":           FrsModuleActor,
    "frs_module_responsibilities": FrsModuleResponsibility,
    "frs_module_interfaces":       FrsModuleInterface,
    "frs_module_data_entities":    FrsModuleDataEntity,
    "frs_specs":                   FrsSpec,
    "frs_spec_decisions":          FrsSpecDecision,
}
```

The full manifest including Stage B units lives in the same file; see
`prd-e4c-frs-functional-design.md` for the Stage B portion.
