# E5 — NFR (Non-Functional Requirements) Builder — Development Plan

**Status:** ready for development · **Companion PRD:** `.claude/prd/prd-e5-nfr.md`
**Engine cloned from:** FRS (`frs_orchestrator.py`, `dspy_frs.py`, `manifest/frs.py`, `validators/frs.py`, `frs_layer.py`, `api/frs.py`, `models/frs.py`, `frontend/app/components/frs/*`) · **Migration:** `0025` (head is `0024`).

This plan is **self-contained and line-anchored** to the real code (verified). Every shared-file edit is **additive** and proven non-breaking in §9 (Blast-radius). Follow the build order in §11.

---

## 0. What we're building (one paragraph)

A standalone **NFR Builder** that unlocks the moment the **BRD is validated** (parallel to FRS — both gate on the BRD, NFR never gates FRS). It generates, from the same full-corpus context FRS uses (App Brain + docs + validated CB + validated BRD), a set of **`NFR-nnn`** requirements across the template's **seven quality categories** (Performance · Security · Availability · Usability · Scalability · Maintainability · Portability), each a **testable, solution-agnostic** statement with a **measurement**, a **MoSCoW** priority, and **traceability to a BRD objective/requirement**, plus governance rows (risks, trade-offs, open questions, decisions, references, glossary). It reuses the proven artifact engine (row-versioning, locking, idempotent regen, `unit_status` progress, mock path) and ships a signature **Quality Radar** UI. When validated, NFRs **softly feed** FRS generation as `nfr_driver` context + traces — with **zero behavioral change** to FRS when NFR is absent.

---

## 1. Domain (source: `reference_mds/skills/nfr-builder/{nfr-template.md, SKILL.md}`)

**7 categories**, each a table of rows `{NFR Number, Attribute, Requirement, Priority}`. Requirement = testable + solution-agnostic; Priority = MoSCoW (`must/should/could/wont`).

| # | Category (enum value) | Template § |
|---|---|---|
| 1 | Performance & Efficiency (`performance`) | §2 |
| 2 | Availability, Reliability & Resilience (`availability`) | §3 |
| 3 | Security & Compliance (`security`) | §4 |
| 4 | Usability (`usability`) | §5 |
| 5 | Scalability & Capacity (`scalability`) | §6 |
| 6 | Maintainability & Supportability (`maintainability`) | §7 |
| 7 | Portability & Compatibility (`portability`) | §8 |

**Governance:** Risks (§9.1), Trade-offs (§9.2), Traceability→BRD (§10), Open Questions (§11.1), Pending Decisions (§11.2), References (§12.1), Glossary (§12.2), plus Overview/Objectives (§1–§2 prose).

**SKILL Phase-6 quality gate → validation checks:** BRD prerequisite referenced; all 7 categories populated or explicit N/A; sequential `NFR-nnn`, no gaps; valid MoSCoW; every requirement testable/unambiguous/solution-agnostic; traceability to a BRD objective/requirement; no duplicate/overlapping NFRs.

---

## 1.5 Detailed requirements — full row-level CRUD & Celery generation (MUST)

These are hard requirements that shape §5 (orchestrator), §7 (API/workers) and §8 (frontend). They are **non-negotiable** and apply uniformly to **every section** of the NFR document, not just the requirement tables.

### R-CRUD — every row, every section, fully editable / addable / deletable

**The 8 editable sections** (all versioned tables in `NFR_TABLE_MAP`; `nfr_traceability` is system-managed/replace-all and excluded from generic CRUD):

| Section (table) | Row-key scheme | Add-row fields (user-supplied) |
|---|---|---|
| Requirements (`nfr_requirements`) | global `NFR-001…` | category, attribute, requirement, measurement, priority(MoSCoW), rationale, brd_refs[] |
| Risks (`nfr_risks`) | `NFR-R-001…` | risk_id, description, affected_attribute, impact, likelihood, mitigation, owner, risk_status |
| Trade-offs (`nfr_tradeoffs`) | `NFR-TD-001…` | tradeoff, options_considered[], decision, rationale, decided_on, decision_maker |
| Open Questions (`nfr_open_questions`) | `NFR-OQ-001…` | question, owner, due_date, oq_status |
| Pending Decisions (`nfr_decisions`) | `NFR-PD-001…` | description, owner, target_date, decision_status |
| References (`nfr_references`) | `NFR-REF-001…` | ref_type, title, location, notes |
| Glossary (`nfr_glossary`) | `NFR-G-001…` | term, definition |
| Overview/Objectives (`nfr_text_blocks`) | `NFR-TB-*` | block_kind, content |

- **R-CRUD-1 — Edit anything.** Every field of every row in all 8 sections is user-editable via `POST …/nfr/{table}/{row_id}/edit`. Edits are **versioned** (new version, old flipped `is_current=false`), **lock-aware** (an edit sets `is_locked=true` so AI regeneration won't overwrite human content), and **optimistic-concurrency-safe** (`expected_version` → `409` on conflict). The full prior history is retrievable.
- **R-CRUD-2 — Add anywhere.** Every section supports adding a brand-new row via `POST …/nfr/{table}/add`. The server allocates the next row_key for that table's scheme (table-specific prefix; requirements use the next global `NFR-nnn`), inserts `version=1, source="human"`. For `nfr_requirements`, the body may include `brd_links[]` which are validated against active BRD rows (`422` otherwise) and persisted as both `brd_refs` and `nfr_traceability` rows. Manually added rows are **excluded from AI soft-delete scope** — they survive every regeneration.
- **R-CRUD-3 — Delete anything (soft).** Every row in all 8 sections is deletable via `POST …/nfr/{table}/{row_id}/delete` (soft: `status='removed'`, history preserved) and **restorable** from history (`/restore`). Soft-delete keeps the audit trail and lets a removed row be brought back.
- **R-CRUD-4 — Lock / unlock / history everywhere.** `/unlock` reopens a row to AI regeneration; `/history` returns every version of any row in any section. These generic routes are guarded by `VALID_NFR_TABLES = set(NFR_TABLE_MAP)` so all 8 sections are covered and `nfr_traceability` is rejected.
- **R-CRUD-5 — UI parity.** Every section in the builder UI (the 7 category requirement tables **and** the governance sections — risks, trade-offs, open questions, decisions, references, glossary, overview/objectives) renders an inline-editable table with a per-row hover menu (Edit · History · Lock · Delete) **and** a `[+ Add row]` affordance. No section is read-only. (§8.4 `NfrGovernancePanel`.)

### R-INTAKE — optional ad-hoc requirements on the landing page (with AI-enhance)

- **R-INTAKE-1 — Optional brief box.** The NFR landing page (`NfrEmptyState`, shown before any generation) presents an **optional** "Ad-hoc NFR requirements" multi-line text area where the user can type free-form quality requirements / constraints / standards to fold in (e.g. "must meet WCAG 2.2 AA; p99 < 800ms; SOC-2 audit logging"). Leaving it blank is fully supported — generation proceeds from the BRD/CB corpus alone.
- **R-INTAKE-2 — AI-enhance the text.** Next to the box, an **"✨ AI Enhance"** button rewrites/structures the user's draft into a cleaner, more complete brief via the existing shared `enhance_brief(project, "nfr", text, db)` service (`services/artifacts/discover.py:146` → `dspy_discover.run_enhance_brief`, fixture `artifact_discover_enhance_brief.json`) — **no new DSPy module or fixture**. The enhanced text replaces the box content with an **Undo** affordance; the user can edit it further before generating.
- **R-INTAKE-3 — Then the normal flow proceeds.** Clicking **"Generate NFRs"** passes the (optionally enhanced) text as the `brief` to `api.nfr.generate(projectId, { brief })`. The brief is persisted as the initial-brief `ArtifactMessage` and threaded into **every** generation unit's `brief` input (§4/§5), so the ad-hoc requirements ground all 9 units. After generation the normal builder/Quality-Radar flow runs unchanged.

### R-CELERY — core generation runs on Celery (MUST)

- **R-CELERY-1 — Celery is the production execution path.** All heavy LLM generation (full-document generate, and per-unit/per-category regenerate) executes in **Celery worker tasks**, never synchronously in the request thread on the real provider. The HTTP endpoint sets `status='generating'`, dispatches the task, and returns immediately; the client polls `GET …/nfr` (SWR `refreshInterval=1500ms` while generating) for live progress from `unit_status`.
- **R-CELERY-2 — Tasks.** Add `generate_nfr` (full document) and `regenerate_nfr_unit` (single unit/category) to `workers/tasks.py`, each cloning the `generate_frs` task shape (tasks.py:1539): `@celery_app.task(name="workers.tasks.generate_nfr", bind=True, max_retries=2, default_retry_delay=10)` wrapping the async body in **`_run_async()`** (disposes the engine after each task — the prefork event-loop gotcha).
- **R-CELERY-3 — Dispatch discipline.** Enqueue via `workers/dispatch.py::dispatch()` (TCP pre-flight so a down broker never hangs the request). If `dispatch()` returns `None` (broker unreachable), **reset the doc** `status` from `generating` back to `in_interview` and return `err("worker_unavailable", …, 503)` — never strand the document in `generating`.
- **R-CELERY-4 — Crash recovery.** On task exception, reset a stuck `nfr` doc from `generating` → `in_interview` (mirrors `_generate_frs`) so the user is never trapped; a `POST …/nfr/reset-generating` endpoint provides a manual escape hatch surfaced by the UI when a job stalls.
- **R-CELERY-5 — Mock stays synchronous & green.** Under `LLM_PROVIDER=mock`, generation runs in-process (no broker needed) so CI/tests are deterministic with zero Vertex/PageIndex/network calls. The mock-vs-Celery branch lives in the API handler exactly as in `api/frs.py:124`.
- **R-CELERY-6 — Sequential units inside the task.** Within the Celery task, `generate_nfr_all` walks `NFR_TOPO_ORDER` **sequentially** and commits per unit (live progress + a consistent global `NFR-nnn` counter — see §5). The task is the unit-of-work; units are not separately fanned out to sub-tasks.

---

## 2. Data model & migration `backend/alembic/versions/0025_nfr_artifact.py`

**Row-key contract:** **global sequential** `NFR-001, NFR-002, …` across all categories (`category` is a column). This is also the `target_ref` value FRS uses for `nfr_driver` traces (see §5). Governance prefixes: risk `NFR-R-001`, tradeoff `NFR-TD-001`, open-q `NFR-OQ-001`, pending-decision `NFR-PD-001`, reference `NFR-REF-001`, glossary `NFR-G-001`, text blocks `NFR-TB-overview` / `NFR-TB-objectives`.

> Note: `models/frs.py:554` comment illustrates `nfr_driver → "N-005"`. We standardize on `NFR-nnn`; update that comment to `"NFR-005"` (cosmetic, §9).

**Migration header** (mirror `0024`):
```python
revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None
```

**Step 1 — extend the enum (must be first, exact pattern from 0024:23):**
```python
op.execute("""
    DO $$ BEGIN
        ALTER TYPE artifact_type ADD VALUE IF NOT EXISTS 'nfr';
    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
""")
```

**Step 2 — three new enums (each guarded, pattern from 0024:30):**
```python
# nfr_category
CREATE TYPE nfr_category AS ENUM ('performance','security','availability','usability','scalability','maintainability','portability');
# nfr_priority (MoSCoW)
CREATE TYPE nfr_priority AS ENUM ('must','should','could','wont');
# nfr_trace_kind
CREATE TYPE nfr_trace_kind AS ENUM ('brd_objective','brd_business_requirement','brd_kpi','brd_risk','brd_text_block','app_fact','doc_section','discover_qa','within_nfr');
```

**Step 3 — versioned tables.** Every table starts with the **standard mixin DDL** (verbatim from `0024` test_suites, lines 61–84):
```sql
id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
row_key     TEXT NOT NULL,
version     INTEGER NOT NULL CHECK (version > 0),
is_current  BOOLEAN NOT NULL DEFAULT true,
is_locked   BOOLEAN NOT NULL DEFAULT false,
status      artifact_row_status NOT NULL DEFAULT 'active',
source      artifact_row_source NOT NULL,
created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
-- typed cols …,
UNIQUE (document_id, row_key, version)
```
…followed (each) by `CREATE INDEX IF NOT EXISTS idx_<t>_current ON <t>(document_id) WHERE is_current;`

Typed columns per table:

- **`nfr_requirements`** (the 7-category core): `category nfr_category NOT NULL`, `attribute TEXT NOT NULL`, `requirement TEXT NOT NULL`, `priority nfr_priority NOT NULL DEFAULT 'should'`, `rationale TEXT NOT NULL DEFAULT ''`, `measurement TEXT NOT NULL DEFAULT ''`, `brd_refs JSONB NOT NULL DEFAULT '[]'::jsonb`, `completeness INTEGER NOT NULL DEFAULT 0`, `confidence TEXT NOT NULL DEFAULT 'low'`, `na BOOLEAN NOT NULL DEFAULT false`. Extra index: `idx_nfr_requirements_category ON nfr_requirements(document_id, category) WHERE is_current`.
- **`nfr_risks`**: `risk_id TEXT`, `description TEXT`, `affected_attribute TEXT`, `impact TEXT`, `likelihood TEXT`, `mitigation TEXT`, `owner TEXT`, `risk_status TEXT DEFAULT 'open'`.
- **`nfr_tradeoffs`**: `tradeoff TEXT`, `options_considered JSONB DEFAULT '[]'`, `decision TEXT`, `rationale TEXT`, `decided_on TEXT`, `decision_maker TEXT`.
- **`nfr_open_questions`**: `question TEXT`, `owner TEXT`, `due_date TEXT`, `oq_status TEXT DEFAULT 'open'`.
- **`nfr_decisions`**: `description TEXT`, `owner TEXT`, `target_date TEXT`, `decision_status TEXT DEFAULT 'pending'`.
- **`nfr_references`**: `ref_type TEXT`, `title TEXT`, `location TEXT`, `notes TEXT`.
- **`nfr_glossary`**: `term TEXT`, `definition TEXT`.
- **`nfr_text_blocks`**: `block_kind TEXT NOT NULL` (`overview`|`objectives`), `content TEXT NOT NULL DEFAULT ''`.

**Step 4 — `nfr_traceability` (NOT versioned, replace-all; pattern from `FrsTraceability` models/frs.py:530 + 3 indexes):**
```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
document_id UUID NOT NULL REFERENCES artifact_documents(id) ON DELETE CASCADE,
source_table TEXT NOT NULL,        -- 'nfr_requirements'
source_row_key TEXT NOT NULL,      -- NFR-nnn
target_kind nfr_trace_kind NOT NULL,
target_ref TEXT NOT NULL,          -- BRD row_key (e.g. BR-001 / OBJ-001)
target_label TEXT NOT NULL DEFAULT '',
confidence TEXT NOT NULL DEFAULT 'high',
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
```
Indexes: `idx_nfr_traceability_doc(document_id)`, `idx_nfr_traceability_source(document_id, source_table, source_row_key)`, `idx_nfr_traceability_target(document_id, target_kind, target_ref)`.

**`downgrade()`** (pattern from 0024:182): drop the 9 tables (traceability first), then `DROP TYPE` the 3 enums; **leave `'nfr'` in `artifact_type`** (PG can't easily remove enum values — matches FRS/BRD/TC practice).

### Models `backend/app/models/nfr.py`
One SQLAlchemy class per table, copying the **`FrsModule` pattern** (models/frs.py:78 — `__table_args__` with `UniqueConstraint(document_id,row_key,version)`, partial `Index(... postgresql_where="is_current")`, `CheckConstraint("version > 0")`, the 10 mixin columns, then typed columns) and the **`FrsTraceability` pattern** (models/frs.py:530) for `NfrTraceability`. Classes: `NfrRequirement, NfrRisk, NfrTradeoff, NfrOpenQuestion, NfrDecision, NfrReference, NfrGlossary, NfrTextBlock, NfrTraceability`. Use `nfr_category`/`nfr_priority`/`nfr_trace_kind` as `Enum(..., create_type=False)` column types (declare them at top of file mirroring `FrsTraceKind` models/frs.py:63).

### Register
- `models/artifact.py:19` — add `'nfr'`: `ArtifactType = Enum("concept_brief","brd","frs","test_cases","nfr", name="artifact_type", create_type=False)`.
- `models/__init__.py` — add an import block + `__all__` entries mirroring the FRS/test_cases blocks (lines 40–50, 122–140) for the 9 NFR classes.

---

## 3. Manifest `backend/app/services/artifacts/manifest/nfr.py`

Single-phase (no FRS A/B). Dataclass mirrors `FrsUnitSpec` (manifest/frs.py:20) minus `phase`:
```python
@dataclass
class NfrUnitSpec:
    unit_key: str
    label: str
    writes: list[str]
    depends_on: list[str]
    unit_instruction: str
    discover_question_keys: list[str]
    timeout_seconds: int = 90
```

**9 units** (TOPO order):

| unit_key | writes | depends_on |
|---|---|---|
| `overview` | `nfr_text_blocks` | `[]` |
| `performance` | `nfr_requirements` (scope=category) | `[overview]` |
| `security` | `nfr_requirements` (scope=category) | `[overview]` |
| `availability` | `nfr_requirements` (scope=category) | `[overview]` |
| `usability` | `nfr_requirements` (scope=category) | `[overview]` |
| `scalability` | `nfr_requirements` (scope=category) | `[overview]` |
| `maintainability` | `nfr_requirements` (scope=category) | `[overview]` |
| `portability` | `nfr_requirements` (scope=category) | `[overview]` |
| `governance` | `nfr_risks, nfr_tradeoffs, nfr_open_questions, nfr_decisions, nfr_references, nfr_glossary, nfr_traceability` | the 7 categories |

`unit_instruction` per category (≈ FRS instruction style, manifest/frs.py:43) — e.g. performance:
> "You are a senior architect authoring the **Performance & Efficiency** NFRs (template §2). Derive testable, **solution-agnostic** quality requirements from the validated BRD objectives, KPIs and constraints. Every requirement MUST be measurable — put the metric + threshold in `measurement` (e.g. 'p95 API latency < 300 ms @ 200 concurrent users'); MUST NOT name a technology/product ('use Redis' is forbidden); MUST carry a MoSCoW `priority`. Continue the **global** `NFR-nnn` numbering from `current_nfrs` (never renumber or alter `locked_nfrs` — reproduce them verbatim). Trace each requirement to ≥1 BRD objective/business-requirement via `brd_refs` AND emit a matching `traceability` row. If this category is genuinely not applicable to the initiative, emit ONE row with `na=true` and a one-line rationale. Produce ≤8 requirements; merge overlaps."

`discover_question_keys` (3–5 per unit, from SKILL Phase-4): perf `[nfr_perf_latency,nfr_perf_throughput,nfr_perf_budget]`; security `[nfr_sec_confidentiality,nfr_sec_integrity,nfr_sec_compliance,nfr_sec_audit]`; availability `[nfr_avail_uptime,nfr_avail_failure,nfr_avail_rto_rpo]`; usability `[nfr_use_accessibility,nfr_use_ux,nfr_use_i18n]`; scalability `[nfr_scale_peak,nfr_scale_growth,nfr_scale_data]`; maintainability `[nfr_maint_support,nfr_maint_observability,nfr_maint_change]`; portability `[nfr_port_env,nfr_port_interop,nfr_port_browser]`; overview `[nfr_ctx_initiative,nfr_ctx_boundary,nfr_ctx_goals]`; governance `[nfr_risk_top,nfr_risk_tradeoff]`.

**Module constants** (mirror manifest/frs.py:222–331):
```python
NFR_MANIFEST: list[NfrUnitSpec] = [OVERVIEW, PERFORMANCE, SECURITY, AVAILABILITY, USABILITY, SCALABILITY, MAINTAINABILITY, PORTABILITY, GOVERNANCE]
NFR_MANIFEST_BY_KEY = {u.unit_key: u for u in NFR_MANIFEST}
NFR_TOPO_ORDER = ["overview","performance","security","availability","usability","scalability","maintainability","portability","governance"]
NFR_CATEGORY_UNITS = ["performance","security","availability","usability","scalability","maintainability","portability"]

from app.models.nfr import (NfrRequirement, NfrRisk, NfrTradeoff, NfrOpenQuestion, NfrDecision, NfrReference, NfrGlossary, NfrTextBlock)
NFR_TABLE_MAP = {  # frs_traceability-equivalent excluded (bespoke replace-all)
  "nfr_requirements": NfrRequirement, "nfr_risks": NfrRisk, "nfr_tradeoffs": NfrTradeoff,
  "nfr_open_questions": NfrOpenQuestion, "nfr_decisions": NfrDecision,
  "nfr_references": NfrReference, "nfr_glossary": NfrGlossary, "nfr_text_blocks": NfrTextBlock,
}
NFR_TYPED_COLS = { ... per-table editable column whitelist (matches DDL §2) ... }
NFR_INT_COLS = {"nfr_requirements": {"completeness"}}
```

**`NFR_VALIDATION_CHECKS`** (consumed by the validator; same finding `group` vocabulary as FRS): drives the 7 SKILL checks — `brd_prerequisite`(critical), `valid_moscow`(critical), `all_categories_covered`(major), `sequential_numbering`(major), `traceability_present`(major), `testable_statements`(minor), `no_duplicate_overlap`(minor).

---

## 4. DSPy `backend/app/services/skills/dspy_nfr.py`

Reuse the FRS plumbing **verbatim** (dspy_frs.py:25–42): `_FIXTURE_DIR = Path(__file__).parent.parent / "llm" / "fixtures"`, `_configure()`, `_is_mock()`, `_load_fixture(name)`. **Fixtures are auto-loaded by filename — no registry change** (`mock_provider.py` `_SKILL_FIXTURE_MAP` is bypassed by DSPy modules).

```python
MoSCoW = Literal["must","should","could","wont"]
Confidence = Literal["high","medium","low"]

class NfrRequirementRow(BaseModel):
    row_key: str                      # global NFR-001…, no gaps
    category: Literal["performance","security","availability","usability","scalability","maintainability","portability"]
    attribute: str
    requirement: str                  # testable, unambiguous, SOLUTION-AGNOSTIC
    priority: MoSCoW
    rationale: str = ""
    measurement: str                  # metric + threshold (testability proof)
    brd_refs: list[str] = Field(default_factory=list)
    na: bool = False

class NfrTraceabilityRow(BaseModel):  # shape == FrsTraceabilityRow (dspy_frs.py:363)
    source_table: Literal["nfr_requirements"]
    source_row_key: str
    target_kind: Literal["brd_objective","brd_business_requirement","brd_kpi","brd_risk","brd_text_block","app_fact","doc_section","discover_qa","within_nfr"]
    target_ref: str
    target_label: str = ""
    confidence: Confidence = "high"
# + NfrRiskRow, NfrTradeoffRow, NfrOpenQuestionRow, NfrDecisionRow, NfrReferenceRow, NfrGlossaryRow, NfrTextBlockRow, NfrOpenQuestion(question, field, why, example)
```

**Shared inputs** (define once, spread into each signature; mirrors FRS): `project_name, business_unit, brief, cb_context, brd_context, app_brain, source_sections, qa_pairs, current_nfrs` (JSON of all existing NFR rows for idempotent global numbering), `locked_nfrs` (JSON to reproduce verbatim).

**Signatures/Modules/runners** (one per unit; the 7 category units share `NfrCategorySignature` with a pinned `category` input + the per-category `unit_instruction` injected):
```python
class NfrCategoryOutput(BaseModel):
    requirements: list[NfrRequirementRow]
    traceability: list[NfrTraceabilityRow]
    open_questions: list[NfrOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100); confidence: Confidence

class NfrCategorySignature(dspy.Signature):
    """Author the NFRs for ONE quality category. Requirements MUST be testable,
    unambiguous, SOLUTION-AGNOSTIC (no technology/product names), each with a MoSCoW
    priority and a `measurement` (metric + threshold). Continue GLOBAL NFR-nnn numbering
    from current_nfrs; reproduce locked_nfrs verbatim. Emit a traceability row for every
    requirement linking it to ≥1 BRD objective/business requirement. For every
    open_question provide a concrete example; if qa_pairs already answers it partially,
    begin with 'You said \"…\" — '."""
    # <shared inputs> + category: str = dspy.InputField()
    result: NfrCategoryOutput = dspy.OutputField()

class NfrCategoryModule(dspy.Module):
    def __init__(self): super().__init__(); self.predict = dspy.ChainOfThought(NfrCategorySignature)
    def forward(self, **kw): return self.predict(**kw).result.model_dump()

async def run_unit(unit_key: str, **kwargs) -> dict:        # the dispatcher
    if _is_mock():
        return _load_fixture(f"nfr_{unit_key}")
    _configure()
    loop = asyncio.get_running_loop()
    mod = {"overview": NfrOverviewModule, "governance": NfrGovernanceModule}.get(unit_key, NfrCategoryModule)()
    if unit_key in NFR_CATEGORY_UNITS: kwargs["category"] = unit_key
    return await loop.run_in_executor(None, lambda: mod(**kwargs))
```
`NfrOverviewSignature → NfrOverviewOutput{text_blocks, completeness, confidence}`. `NfrGovernanceSignature → NfrGovernanceOutput{risks, tradeoffs, open_questions, decisions, references, glossary, traceability}` (governance receives all category requirements as context and emits the **document-wide replace-all** traceability set).

**Mock fixtures (9)** in `backend/app/services/llm/fixtures/`: `nfr_overview.json`, `nfr_{performance,security,availability,usability,scalability,maintainability,portability}.json`, `nfr_governance.json`. Author with **globally unique, gap-free NFR-nnn ranges** (perf 001–003, security 004–007, availability 008–009, …) so a full mock run passes all 7 validation checks. Add a second **broken** fixture set under test control (gap in numbering / missing category / missing trace / empty measurement) to assert each gate fires.

---

## 5. Orchestrator `backend/app/services/artifacts/nfr_orchestrator.py`

Clone `frs_orchestrator.py` (2502 lines) selectively — NFR is single-phase, so it's much smaller. Preserve **exact** versioning/locking/soft-delete semantics.

**Versioning core (verbatim semantics from frs_orchestrator.py:46):**
```python
async def upsert_nfr_rows(table_name, document_id, output_rows, source, db, *, user_id=None, scope_keys=None) -> int:
    # lookup current rows; insert v1 if absent; skip if is_locked; bump version+1 if any
    # NFR_TYPED_COLS[table] changed; soft-delete (status='removed') rows not in output_keys
    # AND (scope_keys is None or row_key in scope_keys) and not is_locked AND source != "human".
    # (source!="human" protects manually-added rows from AI regeneration — R-CRUD-2.)
```
`_upsert_nfr_traceability(document_id, source_table, source_row_key, rows, db)` — delete-then-insert inside `async with db.begin_nested()` (verbatim from :899) against `nfr_traceability`.

**Scope discipline (critical for "don't disturb other categories"):** each category unit calls `upsert_nfr_rows("nfr_requirements", ..., scope_keys=<current NFR row_keys whose category == this unit>)`. So regenerating `security` can only soft-delete security rows. Helper `_category_scope_keys(document_id, category, db)` mirrors FRS's `_module_child_existing_keys` (:_module_child_existing_keys).

**Generation — SEQUENTIAL (design decision, differs from FRS):**
```python
async def generate_nfr_all(project, db, *, brief=None) -> dict:
    doc = await _ensure_nfr_document(project.id, db)         # auto-enrolls project docs as sources
    doc.unit_status = {}; doc.status = "generating"; await db.commit()
    bundle = await gather_project_context(project.id, db, artifact_type="nfr")
    for unit_key in NFR_TOPO_ORDER:                           # overview → 7 categories → governance, IN ORDER
        await _set_current_unit(doc.id, unit_key, db)
        await generate_nfr_unit(project, unit_key, doc, bundle, db)
        await db.commit()                                     # commit per unit → live progress + global counter consistent
    await _set_current_unit(doc.id, None, db)
    doc.status = "in_interview"; await db.commit()
    return await get_nfr_detail(project.id, db)
```
> **Why sequential, not parallel:** all 7 category units write the *same* `nfr_requirements` table and share the **global** `NFR-nnn` counter. FRS Stage B parallelizes because each module writes module-scoped rows; here parallel sessions would race the counter and produce gaps/dupes (failing `sequential_numbering`). Sequential is 9 LLM calls — acceptable, deterministic, and keeps `current_nfrs` accurate for each subsequent unit. **Do not copy FRS's `asyncio.Semaphore` per-module fan-out.**

`generate_nfr_unit(project, unit_key, doc, bundle, db)` — read the persisted ad-hoc brief via `_read_initial_brief(doc.id, db)` (FRS helper: the latest `ArtifactMessage` with `meta.is_initial_brief`), gather `qa_pairs` via `_gather_nfr_unit_qa`, project context via `project_for_unit(bundle, "nfr", unit_key)`, serialize `current_nfrs`/`locked_nfrs`, call `run_unit(..., brief=<ad-hoc brief>)` (the `brief` shared input — so every unit is grounded in the user's ad-hoc requirements, R-INTAKE-3), then `_persist_unit_result` routes `writes` tables through `upsert_nfr_rows` (categories pass `scope_keys`) and routes the governance `traceability` array through `_upsert_nfr_traceability`; merge `unit_status[unit_key] = {completeness, confidence}` via atomic JSONB merge (`_set_current_unit` pattern); emit synthesis + open-question `ArtifactMessage`s.

**Validation:** `validators/nfr.py::run_nfr_validation(document_id, doc, db) -> list[dict]` (clone validators/frs.py: same `_finding(check_id, description, group, row_key=None, suggested_fix="", target_ref=None)` shape). `validate_nfr(project, db, user_id)` in the orchestrator runs it, computes `blocking = [f for f in findings if f["group"] in ("critical","major")]`; if blocking → return `{ok:False, findings}`; else set `status="validated"`, `validated_at/by`, `validated_snapshot_key`, bulk-lock current rows, **and run the soft feeds-FRS advisory** (§5.1) → `{ok:True, findings}`.

**CRUD — generic across ALL 8 sections (R-CRUD; verbatim signatures, frs_orchestrator.py:2050–2223):** `edit_nfr_row(document_id, table_name, row_id, fields, db, *, user_id, lock=True, expected_version=None)`, `delete_nfr_row`, `unlock_nfr_row`, `restore_nfr_row`, `get_nfr_row_history`. All five are **table-agnostic** — they operate on any table in `NFR_TABLE_MAP` (requirements + all 6 governance tables + text blocks), so every row in every section is editable/deletable/lockable/restorable with full history. `VALID_NFR_TABLES = set(NFR_TABLE_MAP)` guards the generic routes; `nfr_traceability` is excluded (system-managed). Edits default `lock=True` (human content protected from regen).

**Add a row to ANY section (R-CRUD-2):** `add_nfr_row(document_id, table_name, fields, db, *, user_id, brd_links=None)` — works for **every** versioned NFR table:
- Validate `table_name ∈ VALID_NFR_TABLES`; coerce `fields` to that table's `NFR_TYPED_COLS` (drop unknown keys; `NFR_INT_COLS` coercion).
- Allocate the next `row_key` via `_next_nfr_row_key(document_id, table_name, db)` — for `nfr_requirements` the next **global** `NFR-nnn` (`_next_global_nfr_number`); for governance tables the next number under that table's prefix (`NFR-R-`, `NFR-TD-`, `NFR-OQ-`, `NFR-PD-`, `NFR-REF-`, `NFR-G-`); text blocks use fixed keys.
- Insert `version=1, source="human", is_locked=False`.
- If `table_name == "nfr_requirements"` and `brd_links` given: validate each link resolves to an active BRD objective/business-requirement row (`422` otherwise), set `brd_refs`, and persist one `nfr_traceability` row per link.
- Manually added rows (`source="human"`) are **excluded from AI soft-delete scope** in `upsert_nfr_rows` (survive every regeneration).

**Detail + Radar:** `get_nfr_detail(project_id, db)` returns (shape mirrors frs get_frs_detail:2454):
```python
{ "document": {...}, "requirements_by_category": {<cat>: [rows]}, "risks": [...], "tradeoffs": [...],
  "open_questions": [...], "decisions": [...], "references": [...], "glossary": [...],
  "text_blocks": [...], "traceability": [...], "messages": [...], "sources": [...],
  "radar": _radar_summary(rows) }
```
`_radar_summary(rows)` → 7 axes `[{category, count, weighted, by_priority:{must,should,could,wont}}]` where `weighted = Σ priority weights (must=4, should=3, could=2, wont=1)`. **Computed, never stored** — reflects manual edits immediately.

Helpers to clone (signatures from frs_orchestrator.py): `_ensure_nfr_document` (:200, get-or-create + auto-enroll sources + IntegrityError race-safe), `_next_nfr_seq` (message seq), `_set_current_unit` (:atomic JSONB merge), `_gather_nfr_unit_qa` (:discover Q&A), `_nfr_row_to_dict`/`_coerce_int_cols` (NFR_INT_COLS), `_current_nfr_rows_for`/`_locked_nfr_rows_for`, `_category_scope_keys(document_id, category, db)`, `_next_global_nfr_number(document_id, db)` (max NFR-nnn across all categories + 1), and **`_next_nfr_row_key(document_id, table_name, db)`** — returns the next key for any table: global `NFR-nnn` for `nfr_requirements`, else `{prefix}-{n+1}` where prefix ∈ {`NFR-R`,`NFR-TD`,`NFR-OQ`,`NFR-PD`,`NFR-REF`,`NFR-G`} (computed from max existing across current+removed versions so deletions don't recycle keys).

**Imports:** from `app.models.nfr`, `app.services.artifacts.manifest.nfr`, `app.services.context.project_context` (`ProjectContextBundle, gather_project_context`), `app.services.context.projection` (`project_for_unit`), `app.services.skills.dspy_nfr` (`run_unit`). No Celery import (dispatch lives in the API layer, per FRS).

### 5.1 Feeds-FRS (soft) — see §6 (projection) + §9. Advisory hook
In `validate_nfr` success path: if a validated FRS doc exists for the project AND it has zero `frs_traceability` rows with `target_kind='nfr_driver'`, emit an advisory `ArtifactMessage` on the FRS doc and let the FRS validator surface a **minor** finding `nfr_drivers_missing`. If an existing `nfr_driver` trace's `target_ref` is no longer a current NFR row_key → **minor** `nfr_drivers_stale`. Both **non-blocking**; cleared by re-genning the affected FRS module (its replace-all traceability refreshes). **Never auto-mutate a validated FRS.**

---

## 6. Context wiring (the surgical, additive diff)

### `context/nfr_layer.py` (new — clone `frs_layer.py`)
```python
@dataclass
class NfrLayer:
    nfr_document_id: str | None
    nfr_status: str | None            # in_interview | validated | None
    nfr_validated_at: str | None
    nfr_snapshot_key: str | None
    requirements: list[dict]; risks: list[dict]; tradeoffs: list[dict]
    open_questions: list[dict]; decisions: list[dict]; references: list[dict]
    glossary: list[dict]; text_blocks: list[dict]; traceability: list[dict]
    formatted_context: str

async def build_nfr_layer(project_id, db) -> NfrLayer:
    # returns empty layer (nfr_status=None) when no NFR doc; uses the generic _load(model, cols)
    # pattern from frs_layer.py:50; _format_nfr_context groups validated requirements by category.
```
`_format_nfr_context` header `=== Validated NFRs (quality drivers) ===`, each line: `[NFR-nnn][category][priority] requirement — measurement ⇒ brd_refs`.

### `context/project_context.py` (additive edits — exact lines)
1. **:172** — add field to `ProjectContextBundle`: `nfr: "NfrLayer | None"`.
2. **:156** — add to `BundleReadiness`: `nfr_ready: bool`, `nfr_status: str | None`.
3. **BRD-layer load (:220)** — change condition to include `"nfr"` so NFR generation gets BRD+CB context and `brd_ready` is computable:
   ```python
   if artifact_type in ("frs", "test_cases", "nfr"):   # was ("frs","test_cases")
       brd_layer = await build_brd_layer(project_id, db)
   ```
4. **After FRS-layer load (:227)** — add the **separate** NFR-layer load for the feeds-FRS path (NFR itself does NOT load its own layer):
   ```python
   nfr_layer: "NfrLayer | None" = None
   if artifact_type in ("frs", "test_cases"):
       from app.services.context.nfr_layer import build_nfr_layer
       nfr_layer = await build_nfr_layer(project_id, db)
   ```
5. **`_compute_readiness` (:254/:261)** — add `nfr` param; extend the BRD gate tuple with `"nfr"`; add a tracked-but-non-blocking `nfr_ready`:
   ```python
   brd_ready = (artifact_type not in ("frs","test_cases","nfr")) or (brd is not None and brd.brd_status == "validated")
   nfr_ready = (artifact_type not in ("frs","test_cases")) or (nfr is not None and nfr.nfr_status == "validated")
   ```
   **Do NOT add `elif not nfr_ready` to the blocking chain. Do NOT add `nfr_ready` to `can_generate`.** Return `nfr_ready` + `nfr_status` (after :291). Pass `nfr=nfr_layer` from `gather_project_context`.
   - Result: **NFR gates on BRD** (`brd_ready` now includes nfr); **FRS stays gated on BRD only** (unchanged); **NFR never blocks FRS** (`nfr_ready` is informational).

### `context/projection.py` (additive edits — exact lines)
1. **:18** — `UnitContext`: add `nfr_context: str = ""`.
2. **Artifact branches (:59–77)** — add an `nfr` branch (full CB + BRD context, like FRS):
   ```python
   elif artifact_type == "nfr":
       cb_context = bundle.cb.formatted_context
       brd_context = bundle.brd.formatted_context if bundle.brd else "(no BRD)"
   ```
3. **After the branches (before :78)** — compute the soft NFR-driver block (guarded):
   ```python
   nfr_context = ""
   if artifact_type in ("frs", "test_cases"):
       nfr = getattr(bundle, "nfr", None)
       if nfr and nfr.nfr_status == "validated" and nfr.requirements:
           nfr_context = "=== Validated NFR Drivers (optional) ===\n" + nfr.formatted_context
   ```
4. **combined_parts (after the FRS append :94)** — `if nfr_context: combined_parts.append(nfr_context)`.
5. **return (after :105)** — `nfr_context=nfr_context`.

> Guard `if nfr and nfr.nfr_status == "validated" and nfr.requirements` ⇒ when NFR is absent/unvalidated, `nfr_context` is `""`, nothing is appended, and FRS prompts are **byte-identical** to today (proven by snapshot test §10).

### `skills/dspy_frs.py` (one sentence, additive)
Append to the `FrsDesignModuleSignature` docstring's TRACEABILITY block (after dpsy_frs.py:501 `- Optionally: spec → app_fact, doc_section, discover_qa, nfr_driver`):
> "If a `=== Validated NFR Drivers ===` block is present in the context, for each FRS spec whose design is shaped by a specific NFR (a latency/availability/security/etc. driver) emit a traceability row with `target_kind='nfr_driver'` and `target_ref=<the NFR-nnn row_key>`. If that block is absent, do not emit `nfr_driver` traces — never fabricate them."

No FRS schema change (`nfr_driver` already in `FrsTraceKind` models/frs.py:65 and `FrsTraceabilityRow` dspy_frs.py:372).

---

## 7. API `backend/app/api/nfr.py` + `main.py`

`router = APIRouter(tags=["nfr"])`. Use the `ok(...)`/`err(...)` envelope (schemas/envelope.py:21). Every route on a path that mutates/reads NFR is **gated on BRD** via `Depends(require_artifact_validated("brd"))` (deps.py:80) — this is the standalone-gates-on-BRD rule.

**Generation = Celery (R-CELERY).** Both `/generate` (full doc) and `/units/{unit_key}/regenerate` (single unit/category) follow the FRS generate handler (api/frs.py:124):
```python
settings = get_settings()
if settings.llm_provider == "mock":
    return ok(await generate_nfr_all(project, db, brief=body.brief))   # in-process, deterministic
# production: persist brief, mark generating, hand off to Celery
doc = await _ensure_nfr_document(project_id, db)
doc.unit_status = {}; doc.status = "generating"; await db.commit()
from workers.dispatch import dispatch
from workers.tasks import generate_nfr
task = dispatch(generate_nfr, str(project_id), body.brief)
if task is None:                       # broker unreachable — never strand in 'generating'
    doc.status = "in_interview"; await db.commit()
    err("worker_unavailable", "Generation worker is not reachable. Start the Celery worker and retry.", 503)
return ok(await get_nfr_detail(project_id, db))
```
`/units/{unit_key}/regenerate` does the same but dispatches `regenerate_nfr_unit(project_id, unit_key)` (mock → in-process `generate_nfr_unit`). Readiness is checked first via `gather_project_context(artifact_type="nfr")` → `bundle.readiness.can_generate` (BRD-gated) → `409 nfr_not_ready` if blocked.

Routes (mirror api/frs.py set):
```
GET  /projects/{project_id}/artifacts/nfr                              → get_nfr_detail
POST /projects/{project_id}/artifacts/nfr/readiness                    → bundle.readiness (artifact_type="nfr")
POST /projects/{project_id}/artifacts/nfr/reset-generating
POST /projects/{project_id}/artifacts/nfr/enhance                      → enhance_brief(project,"nfr",body.brief_text,db) → {enhanced}  (504 enhance_timeout / 500 enhance_failed, mirrors brd.py:423)
POST /projects/{project_id}/artifacts/nfr/generate                     → generate_nfr_all  (gated brd; body.brief = ad-hoc text)
POST /projects/{project_id}/artifacts/nfr/units/{unit_key}/regenerate  → generate_nfr_unit
POST /projects/{project_id}/artifacts/nfr/answer
POST /projects/{project_id}/artifacts/nfr/validate                     → validate_nfr → {ok, findings}
GET  /projects/{project_id}/artifacts/nfr/findings                     → run_nfr_validation (read-only)
POST /projects/{project_id}/artifacts/nfr/{table}/add                  → add_nfr_row (+ BRD links → traceability)
POST /projects/{project_id}/artifacts/nfr/{table}/{row_id}/edit | /delete | /unlock | /restore
GET  /projects/{project_id}/artifacts/nfr/{table}/{row_id}/history
GET  /projects/{project_id}/artifacts/nfr/export                       → build_nfr_export_zip (blob)
```

**Exporter `backend/app/services/artifacts/exporters/nfr.py::build_nfr_export_zip(project_id, doc, db) -> bytes`** (clone exporters/frs.py:48) — render `nfr-template.md` exactly: front-matter, §1 Document Control, §1.x Context (overview/objectives + the fixed Category-Framework table), §2–§8 one markdown table per category (`| NFR Number | Attribute | Requirement | Priority |`, priority rendered `Must/Should/Could/Won't`), §9 Risks + Trade-offs, §10 Traceability to BRD (join `nfr_traceability`), §11 Open Questions + Pending Decisions, §12 References + Glossary.

**`workers/tasks.py`** — add **two** Celery tasks cloning the `generate_frs` task (tasks.py:1539), each wrapping its async body in `_run_async()` (engine-dispose per task):
```python
@celery_app.task(name="workers.tasks.generate_nfr", bind=True, max_retries=2, default_retry_delay=10)
def generate_nfr(self, project_id: str, brief: str | None = None) -> dict:
    return _run_async(_generate_nfr(project_id, brief))

@celery_app.task(name="workers.tasks.regenerate_nfr_unit", bind=True, max_retries=2, default_retry_delay=10)
def regenerate_nfr_unit(self, project_id: str, unit_key: str) -> dict:
    return _run_async(_regenerate_nfr_unit(project_id, unit_key))
```
Both async bodies open `AsyncSessionLocal()`, load the `Project`, call `generate_nfr_all` / `generate_nfr_unit`, and on exception **reset a stuck `nfr` doc** from `generating` → `in_interview` (verbatim from `_generate_frs` tasks.py:1547) before re-raising.

**`main.py`** — add `nfr` to the `from app.api import (...)` block (:98) and `app.include_router(nfr.router, prefix="/api")` next to the FRS line (:118).

---

## 8. Frontend — a *wonderful* NFR Builder

Stack & idioms reused: SWR polling (refreshInterval 1500ms while generating), `sonner` toasts, `cn()`, lucide icons, framer-motion (`useReducedMotion`), the CSS-var design language, and the **`FrsCoverageGalaxy` SVG idiom** (a `computeLayout` returning node coordinates + cubic-bezier edges, hover/selection dimming) as the template for the radar.

### 8.1 `lib/types.ts` (add)
`NfrPriority='must'|'should'|'could'|'wont'`, `NfrCategory` (7), `NfrTraceKind`, `NfrRequirementRow`, `NfrRadarAxis {category; count; weighted; by_priority:Record<NfrPriority,number>}`, `NfrDocument {status:'in_interview'|'generating'|'validated'; unit_status; validated_*; …}` (clone FrsDocument types.ts:1011), `NfrDetail {document; requirements_by_category:Record<NfrCategory,NfrRequirementRow[]>; radar:NfrRadarAxis[]; risks; tradeoffs; open_questions; decisions; references; glossary; text_blocks; traceability; messages; sources}`, `NfrFinding`/`NfrFindingsResponse` (clone FrsFinding types.ts:1042 with groups `critical|major|minor|warning`).

### 8.2 `lib/api.ts` — `nfr:` object (clone the `frs:` block api.ts:492)
`get, readiness, enhance(body:{brief_text}), generate(body:{brief?}), resetGenerating, regenerateUnit(unitKey), answer, validate, findings, addRow(table, body), editRow(table,rowId,fields,opts), deleteRow, unlockRow, restoreRow, rowHistory, exportBundle` — same `apiFetch`/`authedFetch` shapes. (`enhance` → `apiFetch<{ enhanced_brief: string; doc_count: number; app_count: number }>('…/nfr/enhance', {method:'POST', body:{brief_text}})` — the shared `enhance_brief` service returns the rewritten text under **`enhanced_brief`** (verified), not `enhanced`. The landing page reads `data.enhanced_brief`.)

### 8.3 `lib/nfr-manifest.ts` (new)
```ts
export const NFR_CATEGORIES = [
  {key:'performance',    emoji:'⚡', label:'Performance & Efficiency',         color:'amber'},
  {key:'security',       emoji:'🛡', label:'Security & Compliance',            color:'rose'},
  {key:'availability',   emoji:'🟢', label:'Availability & Resilience',        color:'emerald'},
  {key:'usability',      emoji:'🎨', label:'Usability',                        color:'pink'},
  {key:'scalability',    emoji:'📈', label:'Scalability & Capacity',           color:'violet'},
  {key:'maintainability',emoji:'🔧', label:'Maintainability & Supportability', color:'sky'},
  {key:'portability',    emoji:'🔌', label:'Portability & Compatibility',      color:'blue'},
] as const
export const NFR_PRIORITY_STYLES = {  // weight powers the radar
  must:{label:'Must',weight:4,bg:'bg-red-50',text:'text-red-700',border:'border-red-200',dot:'var(--nfr-must)'},
  should:{label:'Should',weight:3,bg:'bg-amber-50',text:'text-amber-700',border:'border-amber-200',dot:'var(--nfr-should)'},
  could:{label:'Could',weight:2,bg:'bg-blue-50',text:'text-blue-700',border:'border-blue-200',dot:'var(--nfr-could)'},
  wont:{label:"Won't",weight:1,bg:'bg-gray-50',text:'text-gray-500',border:'border-gray-200',dot:'var(--nfr-wont)'},
} as const
export const NFR_TRACE_KIND_STYLES = {  // clone FRS trace palette (frs-manifest.ts:93); nfr→brd direction
  brd_business_requirement:{bg:'bg-pink-50',text:'text-pink-700',border:'border-l-2 border-pink-500',label:'BR'},
  brd_objective:{...,label:'OBJ'}, brd_kpi:{...,label:'KPI'}, brd_risk:{...,label:'RSK'}, brd_text_block:{...,label:'BRD'},
  app_fact:{bg:'bg-blue-50',...,label:'App'}, doc_section:{bg:'bg-sky-50',...,label:'Doc'},
  discover_qa:{bg:'bg-violet-50',...,label:'Q&A'}, within_nfr:{bg:'bg-gray-50',...,label:'NFR'},
} as const
export const NFR_FINDING_GROUPS = [
  {key:'critical',label:'Critical',cls:'text-red-700 bg-red-50 border-red-200'},
  {key:'major',   label:'Major',   cls:'text-amber-700 bg-amber-50 border-amber-200'},
  {key:'minor',   label:'Minor',   cls:'text-blue-700 bg-blue-50 border-blue-200'},
  {key:'warnings',label:'Warnings',cls:'text-gray-700 bg-gray-50 border-gray-200'},
] as const
```

### 8.4 Components — `frontend/app/components/nfr/`
- **`NfrBuilderView.tsx`** — clone `FrsBuilderView` state machine + SWR (refreshInterval 1500ms while `status==='generating'` or `_current_unit` set). Layout: `Header` (title, status badge, [Quality Radar] toggle, [Validate]) → body: `NfrCategoryRail` (left) + center pane that shows the active-category `NfrRequirementTable` **or** the `NfrGovernancePanel` (when a governance section is selected in the rail) + Q&A thread; `NfrFindingsDrawer` slides over; `NfrQualityRadar` in header / expandable panel. States: empty (no doc) → `NfrEmptyState`; generating → `NfrGenerationTheater`; builder.
- **`NfrCategoryRail.tsx`** — the 7 category rows (emoji · label · count badge · a 4-segment MoSCoW mini-bar) **plus a "Governance" group** beneath them listing the 6 governance sections + Overview/Objectives, each with its own count badge. A category with 0 active requirements (and not N/A) shows an amber "thin" chip; N/A categories render muted. Active row uses the accent left-border treatment from `NavItem`. Clicking a category filters the requirement table; clicking a governance entry opens that section in `NfrGovernancePanel`. Rail + radar share `activeSection`.
- **`NfrRequirementTable.tsx`** — columns: `NFR#` · `Attribute` · `Requirement` · `Measurement` (mono) · `Priority` (MoSCoW pill) · BRD `NfrTraceChip`s · row actions (Edit/History/Lock/Delete on hover). **Quality nudge:** rows with empty `measurement` get a subtle amber left-border + "needs metric" hint. `[+ Add NFR]` opens `AddNfrDialog`. Every cell is editable via `NfrRowEditDialog`.
- **`NfrGovernancePanel.tsx`** — **fulfils R-CRUD-5 for non-requirement sections.** Renders the selected governance section (risks · trade-offs · open questions · pending decisions · references · glossary · overview/objectives) as an inline-editable table whose columns come from that table's `NFR_TYPED_COLS`. Each row has the same hover menu (Edit · History · Lock · Delete), and the panel header has a `[+ Add row]` button opening the schema-driven `AddRowDialog`. Uses the generic `api.nfr.editRow/deleteRow/unlockRow/restoreRow/rowHistory/addRow` against the section's table — so **no section is read-only**.
- **`NfrQualityRadar.tsx`** — the signature. See §8.5.
- **`NfrRowEditDialog.tsx`** — **schema-driven by table**: renders a field per `NFR_TYPED_COLS[table]` (text / textarea / MoSCoW-select / tag-input for `brd_refs` / JSON list for `options_considered`), with a lock toggle and a version-history tab. One dialog serves edits for **all 8 sections** (clone the FRS row dialog, generalized).
- **`AddRowDialog.tsx`** — generic schema-driven add for any governance section (fields from `NFR_TYPED_COLS[table]`); posts to `api.nfr.addRow(table, fields)`.
- **`AddNfrDialog.tsx`** — the requirement-specific add: category select, attribute, requirement, measurement, MoSCoW, and a **BRD-element link picker** (typeahead over BRD objectives + business requirements via `api.brd.get`); ≥1 link required; links persist as `brd_refs` + `nfr_traceability`.
- **`NfrFindingsDrawer.tsx`** — clone `FrsFindingsDrawer` (right slide-over, `w-[480px]`, grouped by `NFR_FINDING_GROUPS`, "{total} total · {blocking} blocking", per-finding Jump/Accept-fix, Validate footer enabled when blocking=0). On validate success → optional confetti (reuse BRD's burst pattern) + toast "NFR validated — N rows locked".
- **`NfrTraceChip.tsx`** — clone `FrsTraceChip` with `NFR_TRACE_KIND_STYLES`; hover popover (kind, ref, confidence — low = dotted underline + "AI inferred, verify"); click → jump to the BRD element.
- **`NfrEmptyState.tsx`** — the **landing page** (R-INTAKE). Shows a BRD-validated prerequisite chip, a preview of the 7 category cards, and an **optional "Ad-hoc NFR requirements" panel**:
  - a multi-line `textarea` (placeholder: "Optional — paste any quality requirements, standards, or constraints to fold in (e.g. WCAG 2.2 AA, p99 < 800ms, SOC-2 audit logging). Leave blank to generate from the BRD alone.");
  - an **"✨ AI Enhance"** button → `api.nfr.enhance({ brief_text })`; while running shows a spinner; on return replaces the textarea text with `enhanced` and reveals an **Undo** button (restores the pre-enhance draft); enhance is idempotent and re-runnable; errors surface via `toast` (504/500);
  - a primary **"Generate NFRs"** button → `api.nfr.generate({ brief: <current textarea text or undefined> })`, then the view transitions to the generation theater and normal builder flow. The brief is optional — the button is enabled with or without text.
  - Local state: `brief`, `enhancing`, `preEnhanceBrief` (for Undo). Uses `cn()`, `sonner` toast, lucide `Sparkles`/`Loader2`/`Undo2`.
- **`NfrGenerationTheater.tsx`** — clone `FrsConstructionTheater`: a 9-step narrative (overview → 7 categories → governance) with the running step pulsing, driven by `unit_status._current_unit` + per-unit `{completeness}`.
- **(optional polish) `NfrInsightStrip.tsx`** — a one-line intelligence callout computed client-side from `radar`: e.g. "Security is your heaviest axis (8 Must) · Portability is thin (1 Could) · 2 NFRs lack a measurement." Makes the artifact feel smart.

### 8.5 Quality Radar algorithm (`NfrQualityRadar.tsx`)
Reuses the `FrsCoverageGalaxy` coordinate idiom but in **polar** space.
- Input: `radar: NfrRadarAxis[]` (7 axes, server-computed).
- 7 axis angles `θ_i = -90° + i·(360/7)`. Chart radius `R`; center `(cx,cy)`.
- `maxW = max(weighted)`; each axis radius `r_i = (weighted_i / maxW) · R`; point `P_i = (cx + r_i·cosθ_i, cy + r_i·sinθ_i)`.
- **Filled polygon** through `P_0..P_6` (closed), fill `var(--nfr-radar-fill)` low-opacity, animated draw-in via framer-motion `pathLength` (respect `useReducedMotion`).
- **Dashed secondary polygon** for raw `count_i` (normalized to `maxCount`) — shows "how many" vs "how weighted."
- **Per-axis MoSCoW spoke:** along each axis, render a stacked segmented line (segments sized by `by_priority` must→should→could→wont, colored `--nfr-must…--nfr-wont`) — read priority composition per category at a glance.
- Grid: 4 concentric heptagon rings (`var(--nfr-radar-grid)`) + 7 spokes + category emoji/label at each vertex.
- **Interaction:** hover an axis → tooltip (category, count, weighted, MoSCoW breakdown) + highlight that spoke (dim others, mirroring the galaxy's hover-dim). Click an axis → set `activeCategory` (filters rail + table). Center label: "N NFRs · k/7 categories".

### 8.6 `app/globals.css` — `--nfr-*` token block (mirror the `--frs-*` block globals.css:57)
```css
/* ── NFR (E5) — category accents ───────────────────────────── */
--nfr-performance:#B45309; --nfr-performance-bg:#FEF3C7;
--nfr-security:#BE123C;    --nfr-security-bg:#FFE4E6;
--nfr-availability:#047857;--nfr-availability-bg:#D1FAE5;
--nfr-usability:#BE185D;   --nfr-usability-bg:#FCE7F3;
--nfr-scalability:#6D28D9; --nfr-scalability-bg:#EDE9FE;
--nfr-maintainability:#0369A1; --nfr-maintainability-bg:#E0F2FE;
--nfr-portability:#1D4ED8; --nfr-portability-bg:#DBEAFE;
/* MoSCoW bands */
--nfr-must:#DC2626; --nfr-should:#D97706; --nfr-could:#2563EB; --nfr-wont:#9CA3AF;
/* Quality Radar */
--nfr-radar-grid:#E5E7EB; --nfr-radar-fill:rgba(16,185,129,0.18); --nfr-radar-axis:#94A3B8;
/* Generation theater (reuse FRS theater tokens or alias) */
--nfr-theater-step-done:var(--accent); --nfr-theater-step-current:#2563EB; --nfr-theater-step-queue:#D6D3D1;
```

### 8.7 `app/projects/[id]/page.tsx` — exact edits
1. **:40** View union → `… | 'brd' | 'nfr' | 'frs' | 'test-cases' | null`.
2. **:151–154** localStorage guard → add `|| v === 'nfr'`.
3. **Fetch + flags (near :290)** — add `nfrDetail` SWR (`api.nfr.get`), `const nfrStatus = nfrDetail?.document?.status ?? null`, `const nfrValidated = nfrStatus === 'validated'`, and an `nfrStatusBadge()` cloning `frsStatusBadge()` (:303).
4. **NavItem — insert between BRD (:422) and FRS (:432):**
   ```tsx
   {/* 3.5 NFR — standalone, unlocks with BRD; parallel to FRS */}
   <NavItem
     label="NFR" sublabel={nfrSublabel} icon={<Gauge size={14} />}
     active={view === 'nfr'} locked={!brdValidated}
     badge={nfrStatusBadge()}
     onClick={brdValidated ? () => setView('nfr') : undefined} />
   ```
   `nfrSublabel`: `!nfrStatus ? (brdValidated ? 'Non-Functional Requirements' : 'Unlocks after BRD') : nfrStatus==='generating' ? 'Generating…' : nfrStatus==='validated' ? 'Validated ✓' : 'Draft'`.
5. **:432 FRS NavItem stays `locked={!brdValidated}`** (NOT `!nfrValidated`). Optional: when `nfrValidated`, render a tiny "NFRs ✓" hint chip in the FRS sublabel — never gate.
6. **viewLabel (:352)** — add `: view === 'nfr' ? 'NFR'`.
7. **mainContent (the `view==='frs'` branch, ~:559)** — add:
   ```tsx
   {view === 'nfr' && brdValidated && (
     <NfrBuilderView projectId={projectId} onBack={() => setView(null)} />
   )}
   ```
8. Import `Gauge` from lucide and `NfrBuilderView`.

### 8.8 Wireframes
**Landing page (empty state — R-INTAKE)**
```
┌──────────────────────────────────────────────────────────────────────────┐
│ NFR Builder · PayHub                                  BRD validated ✓      │
│                                                                            │
│   Generate non-functional requirements across 7 quality dimensions:       │
│   ⚡ Performance  🛡 Security  🟢 Availability  🎨 Usability                │
│   📈 Scalability  🔧 Maintainability  🔌 Portability                       │
│                                                                            │
│   ┌── Ad-hoc requirements (optional) ─────────────────────────────────┐   │
│   │ Paste any quality requirements / standards / constraints to fold   │   │
│   │ in — e.g. "WCAG 2.2 AA · p99 < 800ms · SOC-2 audit logging".       │   │
│   │ Leave blank to generate from the BRD alone.                        │   │
│   │                                                          [ ✨ AI   ]│   │
│   │                                                          [ Enhance ]│   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                              [ Generate NFRs → ]                            │
└──────────────────────────────────────────────────────────────────────────┘
   After ✨ Enhance: textarea fills with structured text + an [↩ Undo] button.
   Generate is enabled with or without text; brief flows into all 9 units.
```
**Workspace shell**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SpecForge ▸ PayHub                                              [Export ▾] [⚙] │
├───────────────┬──────────────────────────────────────────────────────────────┤
│ NAV           │ NFR Builder        ⬡ Quality Radar ▾            [Validate ✓]   │
│ ● Interview ✓ │ ┌─────────────────┬──────────────────────────┬───────────────┐│
│ ● Wiki        │ │ ⚡ Perf  (3) ▮▮▯ │ Performance & Efficiency  │ Q&A · Findings││
│ ● Ask         │ │ 🛡 Sec   (4) ▮▮▮ │ NFR# Attr  Requirement … │ ❓ latency?   ││
│ ● Concept Br. │ │ 🟢 Avail (2) ▮▯  │ 001  Latency p95<300ms M │ ✅ throughput ││
│ ● BRD      ✓  │ │ 🎨 Usab  (3) ▮▮  │ 002  Thru.. 1k req/s   S │ ⚠ 2 findings  ││
│ ▸ NFR [Draft] │ │ 📈 Scale (2) ▮   │ 003  …                   │               ││
│ ○ FRS  (lock) │ │ 🔧 Maint (2) ▮   │ [+ Add NFR]              │  Findings ▸   ││
│ ○ Test (lock) │ │ 🔌 Port  (1) ▯   │  ⓘ 2 NFRs lack a metric  │  major: trace ││
│               │ └─────────────────┴──────────────────────────┴───────────────┘│
└───────────────┴──────────────────────────────────────────────────────────────┘
   rail mini-bars = MoSCoW composition · click rail/radar axis ⇒ filters table
```
**Quality Radar**
```
                 Performance ⚡ (w11)
        Portability 🔌 ╱‾‾╲ Security 🛡 (w14)
              ▕   ╱      ╲   ▏
   Maintain. 🔧 ◀─●────────●─▶ Availability 🟢
              ▕   ╲      ╱   ▏     ● = weighted polygon (filled)
        Scalability 📈 ╲__╱ Usability 🎨   ┄ dashed = raw count
   spokes segmented by MoSCoW: ▰must ▰should ▰could ▰wont
   center: "24 NFRs · 6/7 categories" · hover axis → breakdown · click → filter
```

---

## 9. Blast-radius & non-regression ("does not screw the other modules")

Every shared-file change is **additive**; existing BRD/FRS/Test-Cases behavior is provably unchanged.

| File | Change | Why it can't break others |
|---|---|---|
| `models/artifact.py:19` | add `'nfr'` to `ArtifactType` values | Enum widening; existing values/rows untouched. |
| `models/__init__.py` | import/export 9 NFR classes | New names only. |
| `alembic/0025` | `ADD VALUE IF NOT EXISTS 'nfr'` + new `nfr_*` tables/enums | Pure additions; touches no existing table. |
| `project_context.py` BRD-load (:220) | add `"nfr"` to the tuple | FRS/TC still load BRD exactly as before; only adds a new case. |
| `project_context.py` NFR-load (:227) | new `if artifact_type in ("frs","test_cases")` block | Builds an extra layer object; doesn't read/modify BRD/FRS layers. |
| `project_context.py` `_compute_readiness` | add `nfr` param (default None); add `"nfr"` to `brd_ready` tuple; add non-blocking `nfr_ready` | `can_generate` formula **unchanged** (`docs ∧ cb ∧ brd ∧ frs`). FRS/TC `brd_ready`/`frs_ready` lines unchanged. NFR-as-artifact now correctly requires BRD. |
| `projection.py` | add `nfr` branch + guarded NFR-driver append + `nfr_context` field | The append is gated on `nfr.nfr_status=='validated' and nfr.requirements`; with no/unvalidated NFR the FRS `combined` string is identical (snapshot test M5). |
| `dspy_frs.py` | +1 conditional sentence in Stage-B docstring | Behavior only differs when the NFR-drivers block exists; absent ⇒ unchanged output. |
| `frs_orchestrator.py`/`validators/frs.py` | add 2 **minor** findings (`nfr_drivers_missing`/`nfr_drivers_stale`) | Minor ⇒ never in the blocking set; FRS validation gate unchanged. |
| `exporters/frs.py:592` (optional) | update the "ships in a later release" copy | Cosmetic. |
| `main.py` | import + `include_router(nfr.router)` | New route namespace `/api/projects/{id}/artifacts/nfr`; no existing route touched. |
| `workers/tasks.py` | new `generate_nfr` task | New task name; existing tasks unchanged. |

**Golden invariants (asserted by tests §10):** (1) `can_generate` for FRS/TC is unchanged; (2) FRS generation output is identical when NFR is absent/unvalidated; (3) NFR validation findings never block FRS; (4) a category re-gen never soft-deletes another category's rows; (5) the mock path makes zero Vertex/PageIndex calls.

---

## 10. Verification (mock-first)

1. **Migration:** `make migrate` on a scratch DB; assert 9 tables + 3 enums + `'nfr'` in `artifact_type` + partial `is_current` indexes; `make typecheck`.
2. **Orchestrator (pytest, `LLM_PROVIDER=mock`):** `generate_nfr_all` populates all 7 categories with gap-free global `NFR-nnn`; re-run idempotent (no new versions unchanged); locked row preserved verbatim; **category re-gen scope** — regenerating `security` leaves `performance` rows untouched; `_upsert_nfr_traceability` replace-all yields no dups.
2b. **Row-level CRUD across ALL 8 sections (R-CRUD):** for each table (requirements + 6 governance + text_blocks) assert `add_nfr_row` allocates the correct next row_key, `edit_nfr_row` versions + locks, `delete_nfr_row` soft-deletes, `restore_nfr_row` brings it back, `get_nfr_row_history` returns the full timeline; a **manually-added (`source='human'`) row survives a full regeneration** (not soft-deleted); `nfr_traceability` is rejected by the generic routes.
2c. **Celery path (R-CELERY):** with real-provider settings + a stubbed broker, `/generate` and `/units/{u}/regenerate` set `status='generating'` and dispatch the task (assert `generate_nfr`/`regenerate_nfr_unit` enqueued, request returns immediately); broker-down → status reset + `503 worker_unavailable`; task exception → doc reset to `in_interview`; mock-mode runs in-process.
3. **Validation gate:** the broken-fixture set fires each of the 7 checks with the right `group`; `critical`/`major` block, `minor`/`warnings` pass; on pass, `status='validated'` + rows locked.
4. **Feeds-FRS (the safety tests):**
   - **M5 snapshot:** FRS `generate` output rows are identical with NFR (a) absent, (b) present-unvalidated, (c) validated — only `nfr_driver` traces differ; spec prose unchanged.
   - NFR validated **after** FRS ⇒ FRS findings include **minor** `nfr_drivers_missing`; FRS re-validation still succeeds.
   - Delete an NFR referenced by an FRS `nfr_driver` trace ⇒ **minor** `nfr_drivers_stale`; re-gen that FRS module clears it; validated FRS never auto-mutated.
   - `_compute_readiness`: `can_generate` for FRS/TC byte-identical before/after this change (unit test on the function).
5. **API:** `require_artifact_validated("brd")` returns 4xx when BRD unvalidated; `/generate` 503 + status-reset when broker down; `/export` zip markdown matches `nfr-template.md` section order.
5b. **Ad-hoc brief + enhance (R-INTAKE):** `/enhance` returns rewritten text (mock fixture) and 504/500 on timeout/failure; `/generate` with a `brief` persists it as the `is_initial_brief` `ArtifactMessage`; a unit test asserts that brief text is passed into the `brief` input of every generated unit (and that an empty brief is a no-op — generation still runs from the corpus).
6. **UI (dev-browser, `architect@specforge.test`, PayHub with validated BRD):** NFR nav locked until BRD validated, then opens; Generate → theater shows the 9 steps; rail renders 7 categories with counts + MoSCoW mini-bars; **Quality Radar** renders 7 axes with correct weighted magnitudes (must=4…wont=1); hover shows breakdown, click filters the table; add a manual NFR via the BRD link picker → appears, traces, and updates the radar; **in every section** (a requirement category AND each governance section via the rail's Governance group) add a row, edit a field, lock it, delete it, and restore it from history; Validate blocks on a seeded gap then passes (confetti + lock).
7. `make typecheck && make lint && make test-be` green; optional real-Vertex smoke (one project, one category) behind a non-CI marker.

---

## 11. Build order (each step independently verifiable)

**Phase 1 — data spine.** `models/nfr.py` → register (`models/artifact.py`, `models/__init__.py`) → migration `0025` → `make migrate && make typecheck`. ✅ tables exist.

**Phase 2 — generation engine (mock).** `manifest/nfr.py` → `dspy_nfr.py` + 9 fixtures → `nfr_orchestrator.py` → `context/nfr_layer.py` → context wiring edits (`project_context.py`, `projection.py`) → `validators/nfr.py`. Pytest: generate→validate→regen-scope→idempotency. ✅ green mock path.

**Phase 3 — API + workers + export.** `api/nfr.py` (incl. `/enhance` reusing `enhance_brief(…, "nfr", …)`, and the brief-on-`/generate` flow) → `workers/tasks.py` (`generate_nfr` + `regenerate_nfr_unit`) → `main.py` mount → `exporters/nfr.py`. Pytest: endpoints, gate, enhance, 503, export. ✅ reachable & gated.

**Phase 4 — feeds-FRS (soft).** `projection.py` NFR-driver injection (already added in P2) + `dspy_frs.py` sentence + `frs_orchestrator.py`/`validators/frs.py` 2 minor findings. Pytest: M5 snapshot + advisory findings. ✅ FRS unchanged when NFR absent.

**Phase 5 — frontend.** `lib/types.ts` → `lib/nfr-manifest.ts` → `lib/api.ts` (`nfr:`) → `globals.css` (`--nfr-*`) → `components/nfr/*` (Builder, Rail w/ Governance group, RequirementTable, **GovernancePanel**, **QualityRadar**, RowEditDialog [schema-driven, all tables], AddRowDialog, AddNfrDialog, FindingsDrawer, TraceChip, EmptyState, GenerationTheater, InsightStrip) → `page.tsx` integration. Dev-browser walkthrough including **add/edit/delete/restore in every section** (R-CRUD-5). ✅ wonderful UI.

**Phase 6 — polish & docs.** Confetti on validate, radar draw-in/reduced-motion, insight strip; update `exporters/frs.py` "ships later" copy; `make typecheck && lint && test-be`. ✅ ship.

---

## 12. Open questions (carried from PRD §9)
OQ-1 global vs per-category numbering (plan: **global**). OQ-2 `na=true` satisfies `all_categories_covered` (plan: **yes**). OQ-3 one-click "re-gen affected FRS modules" vs manual (plan: **manual + minor finding**). OQ-4 BIA RTO/RPO as free-text context vs structured (plan: **free-text**, no BIA artifact). OQ-5 export single-md vs zip (plan: **zip**, mirror FRS). OQ-6 vague-measurement severity (plan: **minor**).

**Hard constraints honored:** no PII anywhere; every LLM/embedding/corpus call behind the provider abstraction (mock path green); secrets untouched.
```
