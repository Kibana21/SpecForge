# E4c · Part 2 — FRS Functional Design PRD

> **Stage B** of the FRS Builder pipeline (RU → CB → BRD → **FRS = Modularization + Functional Design**).
> This PRD covers the **second of two skills** in `reference_mds/skills/frs-builder/`:
> `guidelines/functional-design.md` + `templates/frs-template.md`. The first skill
> (Modularization, Stage A) is documented in `prd-e4c-frs-modularization.md` and produces the
> module inventory + FRS backlog stubs that this stage consumes.
>
> **Goal of this stage**: for each FRS backlog stub produced by Stage A, produce a complete,
> development-ready FRS specification with UI / Backend / Data / Cross-Cutting / Acceptance
> Scenarios / Functional Requirements / Observability — strictly following the FRS template.
>
> **Two blocking gates** enforced by the skill:
> - **[FIGMA-LINK-REQUIRED]** — no UI Specification can be authored without a Figma link
> - **[SPEC-DECISION]** — when AI hits ambiguity, an MCQ is surfaced for the user to confirm
>
> **Depends on Stage A** — this PRD assumes modules + actors + responsibilities + interfaces
> + data entities + FRS backlog stubs already exist in the database with `is_current=True`
> and `status='active'`. The validator gates Stage B from running while Stage A has critical
> or major findings open.

---

## 1. Context & purpose

Stage A produces a structured set of modules + backlog stubs but **no implementable specs yet**.
A backlog stub is just `{title, priority, br_refs, description}`. A coding agent or human
implementer cannot work from a stub.

**Stage B — Functional Design** is the bridge between "backlog stubs" and "code-ready specs".
For each stub in each module, it produces:

- **Intent narrative** — what the system does and why
- **§1 UI Specification** — screens, components, validation rules, data mapping (BLOCKED until Figma link is provided)
- **§2 Backend Service Specification** — service overview, endpoints (request/response/error/security/operational), integrations
- **§3 Data Specification** — entities, columns, keys, indexes, relationships, access logic, cache
- **§4 Cross-Cutting** — business rules table + security specification
- **Independent Test** — boundary-only validation description
- **Acceptance Scenarios** — ≥6 Given-When-Then bullets with ≥2 negatives
- **Functional Requirements** — FR-1, FR-2, … each tracing to ≥1 scenario
- **Data and Validation** — input rules, PII notes
- **Errors and Edge Cases** — error behaviors with recovery paths
- **Observability** — required logs/metrics/traces/audit events
- **Implementation Tasks** — optional non-binding checklist

Plus, every section emits **outward traceability rows** linking back to BRD/NFR/apps/docs/Q&A.

**Why this stage matters strategically**:
- Each FRS becomes a complete, isolated specification a coding agent (or human) can implement.
- Acceptance scenarios become the test basis for QA.
- Traceability rows close the loop from BR to FR to AC to test case.
- Cross-FRS dependencies (`depends_on`) become the implementation ordering.

---

## 2. The skill — what we implement (verbatim from `functional-design.md` + `frs-template.md`)

This PRD implements the **Functional Specification Design Process** at
`reference_mds/skills/frs-builder/guidelines/functional-design.md` and the **FRS template** at
`reference_mds/skills/frs-builder/templates/frs-template.md`.

### 2.1 The 12-step design process (the LLM must follow internally)

1. **Understand the scope** — business goal, users, boundaries, in/out, assumptions.
2. **Break down into modules** (already done in Stage A; here we pick ONE module and one stub).
3. **Define functional requirements** — for the spec: inputs, outputs, triggers, business rules,
   validations, exceptions, expected outcomes.
4. **Define non-functional requirements** — performance, security, availability, scalability,
   audit, compliance, maintainability. These come from `nfr_refs` if any.
5. **Design end-to-end flow** — user flow + system flow across UI, backend, data.
6. **Produce UI Specification** — per screen: purpose, layout, navigation, interactive behavior;
   per component: validation, behavior, data mapping. **Requires Figma link.**
7. **Produce Backend Service Specification** — per endpoint: URL, method, request/response,
   validation, errors, auth, audit, operational characteristics.
8. **Produce Data Specification** — per entity: columns, types, keys, indexes, relationships,
   retention. SQL/data-access logic at intent level (not runnable).
9. **Apply cross-cutting design rules** — security, logging, configuration, error handling,
   performance, reusability.
10. **Ensure traceability** — every design item maps back to BR / FR / UI / API / data / test.
11. **Validate completeness** — no requirement missing a mapping; no UI without backend/data
    support; no API without request/response/error definition; all validations + security
    defined.
12. **Deliver 7 artifacts** — FRS, UI Spec, API Spec, Data Spec, Technical Design/LLD, NFRs,
    Traceability/Test Basis. In SpecForge: all are **sections within the FRS row** and its
    sub-rows, not separate artifacts.

### 2.2 Core principles (from §`Core Principles`)

- Be clear, structured, and implementation-aware.
- Avoid ambiguity (enforced via [SPEC-DECISION] gating).
- Separate **requirements** from **design**.
- Keep every item testable and traceable.
- Prefer standard templates and consistent naming.

### 2.3 The FRS template structure (every spec output by Stage B)

The template at `templates/frs-template.md` defines the **exact** structure each FRS file must
follow. Lines prefixed with `> **[G]**` in the template are authoring guidance — they tell the
LLM what to write but are not copied into the output file.

```markdown
# <FRS-ID> – <Title>

**Priority:** P0/P1/P2/P3    **Layer:** 0 Foundation / 1 Vertical Feature / 2 Cross-cutting
**Module:** <module name>    **Business Requirements:** <BR-IDs>
**NFR Drivers:** <NFR-IDs>   **Depends on:** <FRS-IDs or N/A>

## Intent / Narrative
<1–2 paragraphs describing user-visible and system behavior>

## Detailed Design

### 1. UI Specification  ← BLOCKING: Figma link required
#### 1.1 Screens         ← repeated per screen
  - Screen design source: Figma link
  - Screen purpose: business purpose, user roles, entry/navigation
  - Layout and presentation: layout, responsive behavior, colors, typography, a11y
  - Navigation: menu, breadcrumbs, redirects, deep links
  - Interactive behavior: initial load, loading indicators, enable/disable, visibility,
    editability, dynamic refresh, timeout, errors

#### 1.2 UI Components on Each Screen  ← repeated per component on each screen
  - Component definition: name, type, position, mandatory/optional, default, placeholder, tooltip
  - Behavior: click, change, focus/blur, auto-populate, dependencies, conditional display
  - Field validation: type, length, format, allowed values, regex, mandatory, cross-field,
    uniqueness, server-side, message
  - Overall screen validation: trigger, order, blocking, placement, save/submit eligibility
  - Actions: buttons available, enable conditions, confirmation, success/failure behavior

#### 1.3 UI Data Mapping
  - Field-to-API parameter mapping
  - Display vs stored value
  - Dropdown source and code tables
  - Grid columns, sorting/filtering/pagination, export/print

### 2. Backend Service Specification
#### 2.1 Service Overview
  - Name, business purpose, owning module, consumers, dependencies, folder structure

#### 2.2 Service Endpoints  ← repeated per endpoint
  - Basic definition: URL, protocol, method, sync/async, idempotent
  - Request: headers, query/path/body params, types, sources, mandatory, defaults,
    format, example, validation, logic to implement
  - Response: structure, fields, optional/nullable, example, pagination, sorting/filtering
  - Error handling: codes, format, business vs technical, retryable, timeout, fallback
  - Security: auth, token, role, action-permission map, masking/encryption, audit
  - Operational: rate limit, timeout, payload size, concurrency, transaction boundary,
    versioning, backward compatibility

#### 2.3 Integration Specification  ← only if external systems involved
  - External system, interface type, auth, message format, scheduling, retry, error, SLA

### 3. Database / Storage / Cache Specification
#### 3.1 Data Store Overview
  - Type, purpose, ownership, read/write pattern, retention, folder structure

#### 3.2 Table / Collection / Object Definition  ← repeated per entity
  - Basic: name, description, related module, volume estimate
  - Columns: name, type, length, nullable, mandatory, default, allowed values, generated,
    sensitivity, encryption
  - Keys: PK, FK, unique
  - Indexes: name, columns, unique, purpose
  - Relationships: cardinality, cascade

#### 3.3 SQL / Data Access Logic  ← intent level, not runnable SQL
  - Table creation, DDL, DML patterns, queries, procedures, views, joins, pagination,
    search, transactions, locking

#### 3.4 Cache Specification  ← only if cache layer used
  - Key design, structure, TTL, invalidation, refresh, consistency, fallback

### 4. Cross-Cutting Specifications
#### 4.1 Business Rules
  | Rule ID | Description | Applies to | Logic / Decision |

#### 4.2 Security Specification
  - Auth, authorization/RBAC, encryption, masking, audit, session, secrets, compliance

## Independent Test
<2–5 sentences describing end-to-end validation without internal access; system boundary only>

## Acceptance Scenarios  ← ≥6, ≥2 negative
- Given … When … Then …

## Functional Requirements  ← FR-1, FR-2, …
- FR-1. <precise, testable, self-contained>

## Data and Validation
<inputs, required fields, validation rules, PII/consent>

## Errors and Edge Cases
<expected error behaviors; every error has a recovery path>

## Observability
<required logs/metrics/traces/audit events at requirement level>

## Implementation Tasks (non-binding)
- [ ] Task 1
```

### 2.4 The two blocking gates

#### Gate 1: [FIGMA-LINK-REQUIRED]

Per the skill's SKILL.md §Questioning rules:

> The Figma design link is missing and is required before any UI specification can be authored.
> - MUST be asked **before** writing any FRS that contains a UI Specification section.
> - BLOCKING: do not write any UI specification content until the user provides the Figma link
>   or explicitly confirms there is no Figma design.

**Implementation**:
- For each FRS spec, check `module_interfaces` for `interface_kind='ui_surface'`. If any exist
  and the spec's screens have no `figma_link`, mark §1 UI Specification as **blocked**.
- AI must NOT produce any `frs_screens` or `frs_ui_components` content while blocked.
- AI emits a `figma_link_required` message into `artifact_messages` with `meta.spec_row_key`.
- Frontend renders an inline `FigmaLinkPrompt` in §1 of the spec panel.
- User options: paste a Figma URL, or click "Skip — UI design TBD" (writes sentinel `__none__`).
- After link arrives, orchestrator re-runs `design_module` for that spec with UI-only scope.

#### Gate 2: [SPEC-DECISION] MCQ

Per the skill's SKILL.md §Ambiguity elimination:

> No FRS may contain unresolved "OR" behaviors or implementation ambiguity.

**Implementation**:
- When AI encounters multiple valid implementations (e.g., "strip or reject", ordering rules,
  fallback vs error, timeout strategies), it emits a `FrsSpecDecisionRow` with 2–4 MCQ options.
- AI picks `recommended_index` and writes the FRS using that choice — the FRS is consistent
  with one implementation.
- The decision is stored in `frs_spec_decisions` with `resolution_status='open'`.
- User confirms / overrides / dismisses via the `FrsDecisionPrompt` UI.
- Unresolved decisions become **warnings** at validate time (non-blocking).

### 2.5 Stage B is NOT optional sections

Per the template: "Cover all sub-sections that apply to this FRS; omit sub-sections that are
genuinely not relevant (e.g. omit §1 UI Specification for a backend-only FRS, omit §3 Database
for a pure UI aggregation FRS). Justify omissions with a one-line note."

**Implementation**:
- If module interfaces have no `ui_surface` rows, the AI may legitimately produce zero
  `frs_screens` rows for that spec — but must write a one-line note in `narrative`:
  *"§1 UI Specification omitted — backend-only FRS."*
- The validator checks: a spec with no screens but with `module_interfaces.ui_surface` rows is
  a major finding ("Module has UI surfaces but spec has no screens").

---

## 3. Inputs (what Stage B consumes)

For each module's `design_module` call:

### 3.1 Module context (from Stage A)

- `module_row_key` (the target module being designed)
- The module's full inventory: `frs_modules` row + all child rows (`frs_module_actors`,
  `_responsibilities`, `_interfaces`, `_data_entities`)
- The module's FRS backlog stubs (`frs_specs` with `module_row_key` matching, `completeness=0`)

### 3.2 Cross-module context

A summary of every other module's `name`, `layer`, and `frs_module_interfaces` rows that target
this module (so the AI knows what contracts this module must fulfill).

### 3.3 Full corpus

- `bundle.brd.formatted_context` — entire validated BRD
- `bundle.cb.formatted_context` — validated Concept Brief
- `bundle.apps.formatted_context` — in-scope app facts
- `bundle.docs.outline_text` — PageIndex outline of all project docs
- Per-spec depth-search of project docs (filtered to NFR/Architecture if uploaded)
- `qa_pairs` — FRS discover Q&A (the 5 questions mapped to `design_module`:
  `frs_5a, frs_6a, frs_6b, frs_7a, frs_8a`)

### 3.4 Idempotency context

- `current_specs` — JSON of the module's specs already produced (so regeneration is idempotent)
- `locked_specs` — JSON of specs the user has locked (preserved verbatim)
- `current_sub_rows` — JSON of screens / endpoints / entities / scenarios / FRs already created

### 3.5 User-provided overrides

- Per-spec Figma link(s) — if user has provided
- Resolved [SPEC-DECISION] choices from `frs_spec_decisions` (where `user_chosen_index IS NOT NULL`)

---

## 4. Outputs (what Stage B produces per backlog stub)

For each backlog stub in the target module:

### 4.1 Updated `frs_specs` row

The stub's columns get filled in:

- `narrative` (1–2 paragraphs)
- `nfr_refs` (NFR driver IDs if NFR/Arch docs exist)
- `depends_on` (other FRS spec row_keys this depends on, e.g., a Cross-cutting Standards FRS)
- `independent_test` (2–5 sentences)
- `data_and_validation` (text)
- `errors_and_edge_cases` (text)
- `observability` (text)
- `implementation_tasks` (JSONB checklist, optional)
- `completeness` (Int, AI's self-rating)
- `confidence` (`high | medium | low`)

### 4.2 Sub-row tables

Per spec:
- `frs_screens` — 0+ rows (0 if no UI; 1+ if UI surfaces exist and Figma link provided)
- `frs_ui_components` — 0+ rows per screen
- `frs_endpoints` — 0+ rows (per service endpoint owned by this spec)
- `frs_data_entities` — 0+ rows (per entity owned at the FRS level — schema detail)
- `frs_business_rules` — 0+ rows (table of business rules)
- `frs_acceptance_scenarios` — **≥6** rows with ≥2 negatives
- `frs_functional_requirements` — 1+ rows, each tracing to ≥1 scenario

### 4.3 Spec-scoped decisions

`frs_spec_decisions` rows with `spec_row_key=<spec_row_key>` and `module_row_key=NULL`. AI
populates `recommended_index` and `recommended_rationale`; user resolves later.

### 4.4 Traceability rows

`frs_traceability` rows (NOT versioned — replace-all semantics on each spec regenerate). For
each spec, emit:
- ≥1 row tracing the spec to a BR (`source_table='frs_specs', source_row_key=<spec>, target_kind='brd_business_requirement', target_ref=<BR row_key>`)
- 1 row per Functional Requirement to its BR / scenario / data
- 1 row per Acceptance Scenario to its FR(s)
- Optional rows from spec/FRs to NFR drivers, app facts, doc sections, discover Q&A

---

## 5. Data model (tables Stage B owns / fills)

The 14-table schema was introduced in Stage A's migration `0019_frs_artifact.py`. Stage B fills
in the 9 spec-level tables below. (Stage A creates them as part of the migration but only
writes stub-form rows to `frs_specs`.)

All sub-row tables use `VersionedRowMixin` (versioning + lock + soft-delete + source attribution).

### 5.1 `frs_specs` (FULL form — Stage B fills out)

| Column | Type | Notes (Stage B populates) |
|--------|------|---------------------------|
| (versioning) | — | row_key e.g. `M001-FRS001` |
| `module_row_key` | Text | FK to `frs_modules.row_key` (set in Stage A) |
| `title` | Text | set in Stage A |
| `priority` | enum `frs_priority` | set in Stage A |
| `layer` | enum `frs_module_layer` | set in Stage A |
| `br_refs` | JSONB list[Text] | set in Stage A; Stage B may expand |
| `nfr_refs` | JSONB list[Text] | Stage B fills if NFR/Arch docs uploaded |
| `depends_on` | JSONB list[Text] | Stage B fills (other FRS spec row_keys) |
| `narrative` | Text | Stage B writes 1–2 paragraphs |
| `independent_test` | Text | Stage B writes 2–5 sentences |
| `data_and_validation` | Text | Stage B writes |
| `errors_and_edge_cases` | Text | Stage B writes |
| `observability` | Text | Stage B writes |
| `implementation_tasks` | JSONB list[{task, done}] | Stage B writes optional |
| `completeness` | Int | Stage B updates (0 → ~90+) |
| `confidence` | Text | Stage B updates (low → high/medium) |

### 5.2 `frs_screens`

UI Spec §1.1.

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-SCR-1` |
| `spec_row_key` | Text | FK |
| `screen_name` | Text | "Customer Registration" |
| `figma_link` | Text \| NULL | THE BLOCKING GATE; sentinel `__none__` if user opts out |
| `purpose` | Text | business purpose narrative |
| `user_roles` | JSONB list[Text] | who can access (mirrors actors) |
| `layout` | Text | layout narrative w/ markdown bullets |
| `navigation` | Text | menu/breadcrumb/back/redirect behavior |
| `interactive_behavior` | Text | initial load, loading states, dynamic refresh, errors |

### 5.3 `frs_ui_components`

UI Spec §1.2.

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-CMP-1` |
| `spec_row_key` | Text | FK |
| `screen_row_key` | Text | FK |
| `component_name` | Text | "Email Input" |
| `component_type` | Text | conceptual: "input", "dropdown", "button", "table", "card" |
| `definition` | JSONB | `{ position, mandatory, default, placeholder, tooltip }` |
| `behavior` | JSONB | `{ click, change, focus, blur, auto_populate, dependencies, conditional_display, editable }` |
| `validation` | JSONB | `{ data_type, length, format, allowed_values, regex, mandatory, cross_field, uniqueness, server_side, message }` |
| `actions` | JSONB list | `[{ button: 'Create', enabled_when, confirm_dialog, on_success, on_failure }]` |
| `data_mapping` | JSONB | UI field → API param mapping |

### 5.4 `frs_endpoints`

Backend Spec §2.2.

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-EP-1` |
| `spec_row_key` | Text | FK |
| `service_name` | Text | "Customer Onboarding Service" |
| `endpoint_name` | Text | "Register Customer" |
| `url` | Text | "/api/customers/register" |
| `protocol` | Text | "HTTPS" (or "gRPC", "AMQP", etc.) |
| `method` | enum `frs_http_method` | `GET | POST | PUT | PATCH | DELETE` |
| `sync_async` | Text | "sync" or "async" |
| `idempotent` | Bool | |
| `request_spec` | JSONB | `{ headers, query, path, body, validation, example }` |
| `response_spec` | JSONB | `{ structure, fields, optional, example, pagination, sorting }` |
| `error_handling` | JSONB | `{ codes: [{code, message, business_or_technical, retryable}], retry, fallback, timeout }` |
| `security` | JSONB | `{ auth_method, required_token, roles, action_permission_map, masking, audit }` |
| `operational` | JSONB | `{ rate_limit, timeout, max_payload, concurrency, transaction_boundary, versioning, bc_rules }` |
| `integration_target` | Text \| NULL | external system name if §2.3 integration applies |

### 5.5 `frs_data_entities`

Data Spec §3.2 (FRS-level — full schema; module-level entities at `frs_module_data_entities`
are conceptual only).

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-DE-1` |
| `spec_row_key` | Text | FK |
| `entity_name` | Text | "customer_profile" |
| `data_store_type` | Text | "RDBMS", "NoSQL", "ObjectStore", "Cache" |
| `description` | Text | business description |
| `expected_volume` | Text | "~10k rows/day; ~5M total" |
| `columns` | JSONB list | `[{name, type, length, nullable, mandatory, default, allowed_values, generated, sensitivity, encryption}]` |
| `keys_constraints` | JSONB | `{ primary: [cols], foreign: [{cols, ref_entity, ref_cols, on_delete, on_update}], unique: [[cols]] }` |
| `indexes` | JSONB list | `[{name, columns, unique, purpose}]` |
| `relationships` | JSONB list | `[{cardinality, target_entity, cascade}]` |
| `access_logic` | Text | SQL/data-access intent, not runnable |
| `cache_spec` | JSONB \| NULL | §3.4 if cache used: `{ key_design, structure, ttl, invalidation, refresh, consistency, fallback }` |
| `retention_policy` | Text | from §3.1 retention requirement |

### 5.6 `frs_business_rules`

Cross-Cutting §4.1.

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-BR-1` |
| `spec_row_key` | Text | FK |
| `rule_id` | Text | local within FRS, e.g. "BR-1" |
| `description` | Text | |
| `applies_to` | Text | which component/endpoint/entity |
| `logic_decision` | Text | actual rule in if-then language |

### 5.7 `frs_acceptance_scenarios`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-AS-1` |
| `spec_row_key` | Text | FK |
| `scenario_index` | Int | display order (1, 2, …) |
| `given` | Text | |
| `when` | Text | |
| `then` | Text | |
| `is_negative` | Bool | true for failure/error scenarios |
| `fr_refs` | JSONB list[Text] | FR row_keys this scenario validates |

### 5.8 `frs_functional_requirements`

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-FR-1` |
| `spec_row_key` | Text | FK |
| `fr_id` | Text | local within FRS, e.g. "FR-1" |
| `requirement_text` | Text | precise, testable, self-contained |
| `scenario_refs` | JSONB list[Text] | acceptance scenario row_keys |

### 5.9 `frs_spec_decisions` (spec-scoped; module-scoped covered in PRD 1)

| Column | Type | Notes |
|--------|------|-------|
| (versioning) | — | row_key e.g. `M001-FRS001-DEC-1` |
| `spec_row_key` | Text | set when spec-scoped (Stage B) |
| `module_row_key` | Text \| NULL | NULL when spec-scoped |
| `question` | Text | "Hard-fail or soft-warn on duplicate email?" |
| `options` | JSONB list | `[{label, description, implications}]` (2–4) |
| `recommended_index` | Int | AI's pick |
| `recommended_rationale` | Text | |
| `user_chosen_index` | Int \| NULL | |
| `resolution_status` | enum `frs_decision_status` | `open | accepted_ai | overridden | dismissed` |

### 5.10 `frs_traceability` (NOT versioned — replace-all semantics)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `document_id` | UUID | FK to `artifact_documents` (CASCADE) |
| `source_table` | Text | `frs_specs`, `frs_functional_requirements`, `frs_acceptance_scenarios`, `frs_endpoints`, etc. |
| `source_row_key` | Text | e.g. `M001-FRS001`, `M001-FRS001-FR-1` |
| `target_kind` | enum `frs_trace_kind` | `brd_business_requirement | brd_objective | brd_kpi | brd_risk | brd_text_block | nfr_driver | app_fact | doc_section | discover_qa | within_frs` |
| `target_ref` | Text | row_key / fact_id / doc-section-id / question-key |
| `target_label` | Text | human-readable |
| `confidence` | Text | `high | medium | low` |

### 5.11 Enums added by Stage B (in same migration `0019_frs_artifact.py`)

- `frs_http_method` (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`)
- `frs_trace_kind` (10 values listed above)

(The enums for Stage A — `frs_module_layer`, `frs_actor_relationship`, `frs_interface_kind`,
`frs_interface_direction`, `frs_priority`, `frs_decision_status` — are also added by the same
migration since the model file lives together.)

---

## 6. Backend implementation

### 6.1 Files (under `backend/app/`)

| Path | Purpose | New / Extend |
|------|---------|--------------|
| `models/frs.py` | All 14 tables (created in Stage A migration); this PRD uses the 9 spec-level tables | covered by Stage A |
| `services/artifacts/manifest/frs.py` | Add `FRS_STAGE_B_UNIT` for "design_module" | extend (Stage A added `FRS_STAGE_A_UNIT`) |
| `services/skills/dspy_frs.py` | Add `FrsDesignModuleSignature` + `FrsDesignModuleModule` + `run_design_module` | extend |
| `services/llm/fixtures/frs_design_module.json` | Mock fixture for Stage B (one module's worth of specs) | new (hand-written) |
| `services/artifacts/frs_orchestrator.py` | Add `generate_frs_design_module(module_row_key, ...)`, `generate_frs_all` (calls Stage A then Stage B), per-spec regenerate, per-spec figma-link handler, decision resolver | extend |
| `services/artifacts/validators/frs.py` | Add `_validate_stage_b` rules (UI/figma, scenarios, FR/scenario coverage, depends_on integrity, cycle detection, traceability) | extend |
| `services/artifacts/discover_catalog.py` | Already added in Stage A; Stage B reuses FRS_UNIT_DISCOVER_MAP[`design_module`] = `["frs_4a", "frs_5a", "frs_6a", "frs_6b", "frs_7a", "frs_8a"]` | covered |
| `api/frs.py` | Add Stage-B routes (listed in §6.5) | extend |
| `services/artifacts/exporters/frs.py` | Generates the markdown export bundle (modules + specs + traceability) | new |
| `workers/tasks.py` | Add `incorporate_frs_answer`, `regenerate_frs_spec`, `regenerate_frs_module` Celery tasks | extend |
| `workers/dispatch.py` | Register the 3 new tasks | extend |

### 6.2 The `FrsDesignModuleSignature` (DSPy)

```python
# backend/app/services/skills/dspy_frs.py (Stage B section)

class FrsScreenRow(BaseModel):
    row_key: str               # "M001-FRS001-SCR-1"
    screen_name: str
    figma_link: str | None     # None if Figma link still required (gates the rest)
    purpose: str
    user_roles: list[str]
    layout: str
    navigation: str
    interactive_behavior: str

class FrsUiComponentRow(BaseModel):
    row_key: str               # "M001-FRS001-CMP-1"
    screen_row_key: str
    component_name: str
    component_type: str
    definition: dict
    behavior: dict
    validation: dict
    actions: list[dict]
    data_mapping: dict

class FrsEndpointRow(BaseModel):
    row_key: str               # "M001-FRS001-EP-1"
    service_name: str
    endpoint_name: str
    url: str
    protocol: str
    method: Literal["GET","POST","PUT","PATCH","DELETE"]
    sync_async: str
    idempotent: bool
    request_spec: dict
    response_spec: dict
    error_handling: dict
    security: dict
    operational: dict
    integration_target: str | None = None

class FrsDataEntityRow(BaseModel):
    row_key: str               # "M001-FRS001-DE-1"
    entity_name: str
    data_store_type: str
    description: str
    expected_volume: str
    columns: list[dict]
    keys_constraints: dict
    indexes: list[dict]
    relationships: list[dict]
    access_logic: str
    cache_spec: dict | None = None
    retention_policy: str

class FrsBusinessRuleRow(BaseModel):
    row_key: str               # "M001-FRS001-BR-1"
    rule_id: str               # "BR-1"
    description: str
    applies_to: str
    logic_decision: str

class FrsAcceptanceScenarioRow(BaseModel):
    row_key: str               # "M001-FRS001-AS-1"
    scenario_index: int
    given: str
    when: str
    then: str
    is_negative: bool
    fr_refs: list[str]

class FrsFunctionalRequirementRow(BaseModel):
    row_key: str               # "M001-FRS001-FR-1"
    fr_id: str                 # "FR-1"
    requirement_text: str
    scenario_refs: list[str]   # acceptance scenario row_keys

class FrsTraceabilityRow(BaseModel):
    source_table: str          # "frs_specs", "frs_functional_requirements", etc.
    source_row_key: str
    target_kind: Literal[
        "brd_business_requirement","brd_objective","brd_kpi","brd_risk","brd_text_block",
        "nfr_driver","app_fact","doc_section","discover_qa","within_frs"
    ]
    target_ref: str
    target_label: str
    confidence: Literal["high","medium","low"]

class FrsSpecFullOutput(BaseModel):
    row_key: str               # matches the backlog stub's row_key
    title: str                 # may stay same; AI can refine if user gives more context
    priority: Literal["P0","P1","P2","P3"]
    layer: Literal["foundation","vertical","cross_cutting"]
    br_refs: list[str]         # from backlog stub; AI can expand
    nfr_refs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    narrative: str
    screens: list[FrsScreenRow] = Field(default_factory=list)            # empty if Figma blocked
    ui_components: list[FrsUiComponentRow] = Field(default_factory=list)
    endpoints: list[FrsEndpointRow] = Field(default_factory=list)
    data_entities: list[FrsDataEntityRow] = Field(default_factory=list)
    business_rules: list[FrsBusinessRuleRow] = Field(default_factory=list)
    acceptance_scenarios: list[FrsAcceptanceScenarioRow] = Field(..., min_length=6)
    functional_requirements: list[FrsFunctionalRequirementRow] = Field(..., min_length=1)
    spec_decisions: list[FrsSpecDecisionRow] = Field(default_factory=list)
    traceability: list[FrsTraceabilityRow]  # required; ≥1 row per spec
    independent_test: str
    data_and_validation: str
    errors_and_edge_cases: str
    observability: str
    implementation_tasks: list[dict] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high","medium","low"]
    ui_blocked_reason: str | None = None  # "figma_link_required" if UI omitted because no link

class FrsDesignModuleOutput(BaseModel):
    specs: list[FrsSpecFullOutput]
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high","medium","low"]


class FrsDesignModuleSignature(dspy.Signature):
    """Run Step 4 of the FRS-Builder skill for ONE module. For each FRS backlog stub in this
    module, produce a full development-ready FRS spec following templates/frs-template.md.

    HARD RULES:

    - Every FRS spec MUST have ≥1 traceability row to a BR row_key (br_refs). If a backlog
      stub has empty br_refs, this is a Stage-A defect — emit an open_question rather than
      fabricating a trace.
    - Every FRS spec MUST have ≥6 acceptance_scenarios with ≥2 negative (is_negative=True).
    - Every FRS spec MUST have FR-1, FR-2, …. Each functional_requirement MUST reference ≥1
      acceptance_scenario row_key via scenario_refs.
    - Every acceptance_scenario MUST reference ≥1 functional_requirement row_key via fr_refs.

    FIGMA-LINK BLOCKING GATE:
    Check the module's interfaces (module_context.interfaces). If any have
    interface_kind='ui_surface' AND no screen in current_specs[<spec_row_key>] has a
    figma_link, OMIT the screens[] and ui_components[] arrays for that spec. Instead, set
    ui_blocked_reason='figma_link_required' and write a one-line note in narrative:
    "§1 UI Specification omitted pending Figma link."
    Do NOT fabricate figma_link URLs. Do NOT author UI spec content without a real link.

    [SPEC-DECISION] AMBIGUITY:
    If multiple valid implementations exist (e.g., 'strip or reject special chars', 'retry
    or fail-fast on timeout', 'eager or lazy load'), emit a spec_decisions row with 2–4
    MCQ options. Pick recommended_index (typically the simpler/safer option) and author the
    FRS using that choice — the spec MUST be consistent. The user will confirm/override later.

    DEPENDS_ON:
    If this spec depends on a Cross-cutting Standards FRS (e.g., for error envelope, audit
    pattern, RBAC base), list that FRS row_key in depends_on. Reference the dependency in
    the appropriate section (e.g., 'Error handling follows the common envelope defined in
    M000-FRS001 — see Depends on.').

    TRACEABILITY:
    Emit traceability rows for:
    - Spec → ≥1 BR (target_kind='brd_business_requirement')
    - Spec → ≥1 BRD objective (target_kind='brd_objective', if applicable)
    - Each FR → ≥1 BR or scenario
    - Each scenario → ≥1 FR
    - Optionally: spec → app_fact, spec → doc_section, spec → discover_qa

    SECTION-OMISSION RULE:
    Omit only sections that are genuinely not relevant. Justify omission in narrative with a
    one-line note. Examples:
    - Pure backend FRS (no ui_surface in module_interfaces) → omit screens, ui_components
    - Pure UI aggregation FRS → omit endpoints, data_entities
    - Stateless FRS → omit data_entities
    Never omit acceptance_scenarios, functional_requirements, traceability — those are mandatory.

    Use existing row_keys from current_specs JSON to preserve continuity; never invent new
    row_keys for existing specs. Locked specs (in locked_specs JSON) must be reproduced verbatim.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    module_row_key: str = dspy.InputField()
    module_context: str = dspy.InputField(desc="Full JSON: this module's scope, actors, responsibilities, interfaces, data_entities, frs_backlog stubs")
    other_modules_summary: str = dspy.InputField(desc="JSON list of other modules' names + cross-module interfaces targeting this module")
    brd_context: str = dspy.InputField()
    cb_context: str = dspy.InputField()
    app_brain: str = dspy.InputField()
    source_sections: str = dspy.InputField(desc="Depth-searched project doc sections (esp. NFR/Arch if uploaded)")
    qa_pairs: str = dspy.InputField()
    current_specs: str = dspy.InputField(desc="JSON of existing specs in this module (for idempotent regen)")
    locked_specs: str = dspy.InputField(desc="JSON of locked specs to preserve verbatim")
    resolved_decisions: str = dspy.InputField(desc="JSON of decisions where user has chosen an option")
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

### 6.3 The orchestrator's design-module flow

```python
# backend/app/services/artifacts/frs_orchestrator.py

async def generate_frs_all(project, db) -> dict:
    """Full FRS pipeline: Stage A (modularize) → Stage B (design each module in parallel)."""
    doc = await _ensure_frs_document(project.id, db)

    # Reset unit_status so theater starts clean
    doc.unit_status = {}
    doc.status = "generating"
    await db.commit()

    bundle = await gather_project_context(project.id, db, artifact_document_id=doc.id, artifact_type="frs")

    # Stage A
    await generate_frs_modularize(project, doc, bundle, db)

    # Pull modules created by Stage A
    modules = await _current_frs_modules(doc.id, db)

    # Stage B — design each module in parallel
    sem = asyncio.Semaphore(3)  # cap Vertex concurrency
    async def _design(mod):
        async with sem, AsyncSessionLocal() as unit_db:
            unit_doc = (await unit_db.execute(
                select(ArtifactDocument).where(ArtifactDocument.id == doc.id)
            )).scalar_one()
            await generate_frs_design_module(project, mod.row_key, unit_doc, bundle, unit_db)
            await unit_db.commit()
    await asyncio.gather(*[_design(m) for m in modules])

    # Finalize
    doc.status = "in_interview"
    await db.refresh(doc)
    return await get_frs_detail(project.id, db)


async def generate_frs_design_module(
    project: Project,
    module_row_key: str,
    doc: ArtifactDocument,
    bundle: ProjectContextBundle,
    db: AsyncSession,
    *,
    target_spec_row_key: str | None = None,   # if set, only design this one stub
    ui_only: bool = False,                     # if True, only re-author §1 UI Spec
) -> dict:
    """Phase B: design all FRS specs for one module (or one spec, or just UI section)."""
    # Mark this module as currently running
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) "
        "  || CAST(:patch AS jsonb), updated_at = NOW() WHERE id = :doc_id"
    ), {
        "patch": json.dumps({"_current_unit": f"design_mod_{module_row_key}"}),
        "doc_id": str(doc.id),
    })

    # Load module's full context
    module_row = await _load_module(doc.id, module_row_key, db)
    module_context = await _serialize_module_with_children(doc.id, module_row_key, db)
    other_modules = await _summarize_other_modules(doc.id, exclude=module_row_key, db=db)
    current_specs = await _serialize_module_specs(doc.id, module_row_key, db)
    locked_specs = [s for s in current_specs if s.get("is_locked")]
    resolved_decisions = await _serialize_resolved_decisions(doc.id, module_row_key, db)

    # Depth-search project docs for this module's purpose
    query = f"{project.name} {module_row['name']} functional specification"
    doc_sections = await depth_search(project.id, db, query, artifact_document_id=doc.id)

    # Gather Q&A for design_module unit
    qa_pairs = await _gather_frs_unit_qa(doc.id, "design_module", db)

    result = await run_design_module(
        project_name=project.name,
        business_unit=project.business_unit or "—",
        module_row_key=module_row_key,
        module_context=json.dumps(module_context),
        other_modules_summary=json.dumps(other_modules),
        brd_context=bundle.brd.formatted_context if bundle.brd else "",
        cb_context=bundle.cb.formatted_context,
        app_brain=bundle.apps.formatted_context,
        source_sections=doc_sections,
        qa_pairs=qa_pairs,
        current_specs=json.dumps(current_specs),
        locked_specs=json.dumps(locked_specs),
        resolved_decisions=json.dumps(resolved_decisions),
    )

    # Filter to target spec if requested
    specs_to_persist = result["specs"]
    if target_spec_row_key:
        specs_to_persist = [s for s in specs_to_persist if s["row_key"] == target_spec_row_key]
    if ui_only:
        # Only update screens / ui_components for the target spec
        await _persist_ui_only_result(doc.id, specs_to_persist, db)
    else:
        await _persist_design_module_result(doc.id, specs_to_persist, db)

    # Emit messages for FIGMA_LINK_REQUIRED and open SPEC_DECISIONs
    await _emit_design_messages(doc, result, db)

    # Atomic unit_status update for this module
    await db.execute(sa_text(
        "UPDATE artifact_documents "
        "SET unit_status = COALESCE(unit_status, '{}'::jsonb) "
        "  || CAST(:patch AS jsonb), updated_at = NOW() WHERE id = :doc_id"
    ), {
        "patch": json.dumps({
            f"design_mod_{module_row_key}": {
                "completeness": result.get("completeness", 0),
                "confidence": result.get("confidence", "low"),
            },
            "_current_unit": None,
        }),
        "doc_id": str(doc.id),
    })
    return result


async def _persist_design_module_result(document_id, specs, db):
    """Route each spec's content to the 9 spec-level tables."""
    for spec in specs:
        # 1. Update the spec row (was a stub from Stage A)
        await upsert_frs_rows("frs_specs", document_id, [{
            "row_key":            spec["row_key"],
            "module_row_key":     spec.get("module_row_key"),   # carried from Stage A
            "title":              spec["title"],
            "priority":           spec["priority"],
            "layer":              spec["layer"],
            "br_refs":            spec["br_refs"],
            "nfr_refs":           spec["nfr_refs"],
            "depends_on":         spec["depends_on"],
            "narrative":          spec["narrative"],
            "independent_test":   spec["independent_test"],
            "data_and_validation": spec["data_and_validation"],
            "errors_and_edge_cases": spec["errors_and_edge_cases"],
            "observability":      spec["observability"],
            "implementation_tasks": spec.get("implementation_tasks", []),
            "completeness":       spec["completeness"],
            "confidence":         spec["confidence"],
        }], "ai", db)

        # 2. Screens (skip if UI blocked)
        if not spec.get("ui_blocked_reason"):
            await upsert_frs_rows("frs_screens", document_id,
                [{**s, "spec_row_key": spec["row_key"]} for s in spec.get("screens", [])],
                "ai", db, scope_keys={s["row_key"] for s in spec.get("screens", [])},
            )
            # 3. UI Components
            await upsert_frs_rows("frs_ui_components", document_id,
                [{**c, "spec_row_key": spec["row_key"]} for c in spec.get("ui_components", [])],
                "ai", db,
            )

        # 4. Endpoints
        await upsert_frs_rows("frs_endpoints", document_id,
            [{**e, "spec_row_key": spec["row_key"]} for e in spec.get("endpoints", [])],
            "ai", db,
        )

        # 5. Data entities (FRS-level)
        await upsert_frs_rows("frs_data_entities", document_id,
            [{**e, "spec_row_key": spec["row_key"]} for e in spec.get("data_entities", [])],
            "ai", db,
        )

        # 6. Business rules
        await upsert_frs_rows("frs_business_rules", document_id,
            [{**r, "spec_row_key": spec["row_key"]} for r in spec.get("business_rules", [])],
            "ai", db,
        )

        # 7. Acceptance scenarios
        await upsert_frs_rows("frs_acceptance_scenarios", document_id,
            [{**s, "spec_row_key": spec["row_key"]} for s in spec.get("acceptance_scenarios", [])],
            "ai", db,
        )

        # 8. Functional requirements
        await upsert_frs_rows("frs_functional_requirements", document_id,
            [{**f, "spec_row_key": spec["row_key"]} for f in spec.get("functional_requirements", [])],
            "ai", db,
        )

        # 9. Spec-scoped decisions
        decisions = []
        for i, d in enumerate(spec.get("spec_decisions", []), 1):
            decisions.append({
                "row_key": d.get("row_key", f"{spec['row_key']}-DEC-{i}"),
                "spec_row_key": spec["row_key"],
                "module_row_key": None,
                "question": d["question"],
                "options": d["options"],
                "recommended_index": d["recommended_index"],
                "recommended_rationale": d["recommended_rationale"],
                "user_chosen_index": None,
                "resolution_status": "open",
            })
        await upsert_frs_rows("frs_spec_decisions", document_id, decisions, "ai", db)

        # 10. Traceability (REPLACE-ALL — not versioned)
        await _upsert_frs_traceability(document_id, "frs_specs", spec["row_key"],
                                        spec.get("traceability", []), db)
        for fr in spec.get("functional_requirements", []):
            fr_traces = [t for t in spec.get("traceability", [])
                         if t["source_row_key"] == fr["row_key"]]
            await _upsert_frs_traceability(document_id, "frs_functional_requirements",
                                            fr["row_key"], fr_traces, db)
```

### 6.4 Figma link handler

When user submits a Figma link:

```python
@router.post("/projects/{project_id}/artifacts/frs/specs/{spec_row_key}/figma-link")
async def set_figma_link(
    project_id: UUID, spec_row_key: str, body: FigmaLinkIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set figma_link on every screen of a spec. If no screens exist yet (because UI was
    blocked), create placeholder screens with the link, then trigger UI-only regen."""
    doc = await _get_frs_document(project_id, db)
    spec = await _load_spec(doc.id, spec_row_key, db)
    if spec is None:
        err("spec_not_found", f"FRS spec {spec_row_key} not found", 404)

    screens = await _current_screens(doc.id, spec_row_key, db)
    if body.link == "__none__":
        # User opted out — write sentinel; no regen
        for s in screens:
            await edit_frs_row(doc.id, "frs_screens", s.id, {"figma_link": "__none__"}, current_user.id, db)
        return ok({"status": "skipped", "spec_row_key": spec_row_key})

    if not screens:
        # No screens yet — create one placeholder with the link, regen will fill in details
        await upsert_frs_rows("frs_screens", doc.id, [{
            "row_key": f"{spec_row_key}-SCR-1",
            "spec_row_key": spec_row_key,
            "screen_name": "Primary Screen",
            "figma_link": body.link,
            "purpose": "",
            "user_roles": [],
            "layout": "",
            "navigation": "",
            "interactive_behavior": "",
        }], "human", db)
    else:
        for s in screens:
            await edit_frs_row(doc.id, "frs_screens", s.id, {"figma_link": body.link},
                                current_user.id, db)

    # Trigger UI-only regen for this spec
    project = await _load_project(project_id, db)
    bundle = await gather_project_context(project_id, db, artifact_document_id=doc.id, artifact_type="frs")
    module = await _load_module(doc.id, spec.module_row_key, db)
    await generate_frs_design_module(
        project, module.row_key, doc, bundle, db,
        target_spec_row_key=spec_row_key, ui_only=True,
    )
    await db.commit()
    return ok({"status": "regenerated", "spec_row_key": spec_row_key})
```

### 6.5 API endpoints (Stage-B additions)

In `backend/app/api/frs.py` (in addition to Stage A's routes):

```
POST   /projects/{id}/artifacts/frs/modules/{mod_row_key}/design         → re-run design_module for a module
POST   /projects/{id}/artifacts/frs/specs/{spec_row_key}/regenerate      → re-run for one spec
POST   /projects/{id}/artifacts/frs/specs/{spec_row_key}/figma-link      → set link; triggers UI-only regen

POST   /projects/{id}/artifacts/frs/decisions/{dec_row_key}/resolve      → spec-scoped + module-scoped

POST   /projects/{id}/artifacts/frs/validate                             → run validator; commit if 0 blocking
GET    /projects/{id}/artifacts/frs/findings                             → Stage-A + Stage-B findings
GET    /projects/{id}/artifacts/frs/coverage                             → BR↔FRS coverage map (for Galaxy)

GET    /projects/{id}/artifacts/frs/export                               → Markdown bundle (zip)
```

(Generic row CRUD endpoints from PRD 1 work for Stage B sub-rows too.)

### 6.6 Validator (Stage-B rules)

```python
async def _validate_stage_b(document_id, doc, db) -> list[dict]:
    findings = []

    specs = await _active_rows(FrsSpec, document_id, db)
    completed_specs = [s for s in specs if s.completeness > 0]  # Stage B has run

    # CRITICAL
    for m in (await _active_rows(FrsModule, document_id, db)):
        specs_in_m = [s for s in specs if s.module_row_key == m.row_key]
        if len(specs_in_m) == 0:
            findings.append(_finding(check_id="module_empty", group="critical", row_key=m.row_key,
                description=f"Module {m.row_key} has no FRS specs. Stage B failed for this module.",
                suggested_fix="Re-run design_module for this module."))

    if _has_depends_on_cycle(specs):
        findings.append(_finding(check_id="depends_on_cycle", group="critical",
            description="Cyclic depends_on graph among FRS specs.",
            suggested_fix="Restructure dependencies; consider extracting shared logic into a Cross-cutting Standards FRS."))

    # MAJOR — per-spec rules
    for spec in completed_specs:
        # Spec must trace to BR
        spec_traces = await _frs_traceability_for("frs_specs", spec.row_key, document_id, db)
        if not any(t.target_kind == "brd_business_requirement" for t in spec_traces):
            findings.append(_finding(check_id="spec_no_br_trace", group="major", row_key=spec.row_key,
                description=f"FRS {spec.row_key} does not trace to any BR. Every spec must trace to ≥1 BR.",
                suggested_fix="Re-run this spec — AI will infer BR from module's stub br_refs."))

        # Figma link required if UI surfaces exist
        module_ui_surfaces = await _module_has_ui_surfaces(spec.module_row_key, document_id, db)
        screens = await _active_screens_for_spec(document_id, spec.row_key, db)
        has_real_figma = any(s.figma_link and s.figma_link != "__none__" for s in screens)
        if module_ui_surfaces and not has_real_figma:
            findings.append(_finding(check_id="figma_link_missing", group="major", row_key=spec.row_key,
                description=f"FRS {spec.row_key} module has UI surfaces but no Figma link provided.",
                suggested_fix="Provide a Figma URL via the [Add Figma link] prompt, or click 'Skip — UI design TBD'."))

        # Acceptance scenarios count + negatives
        scenarios = await _active_scenarios_for_spec(document_id, spec.row_key, db)
        if len(scenarios) < 6:
            findings.append(_finding(check_id="too_few_scenarios", group="major", row_key=spec.row_key,
                description=f"FRS {spec.row_key} has {len(scenarios)} acceptance scenarios (need ≥6).",
                suggested_fix="Re-run this spec; AI will add scenarios."))
        negatives = [s for s in scenarios if s.is_negative]
        if len(negatives) < 2:
            findings.append(_finding(check_id="too_few_negative_scenarios", group="major", row_key=spec.row_key,
                description=f"FRS {spec.row_key} has {len(negatives)} negative scenarios (need ≥2).",
                suggested_fix="Re-run this spec; AI will add failure/error cases."))

        # FR ↔ scenario coverage
        frs = await _active_frs_of_spec(document_id, spec.row_key, db)
        scenario_keys = {s.row_key for s in scenarios}
        for fr in frs:
            if not any(ref in scenario_keys for ref in fr.scenario_refs):
                findings.append(_finding(check_id="fr_no_scenario", group="major", row_key=fr.row_key,
                    description=f"FR {fr.row_key} '{fr.fr_id}' references no acceptance scenario.",
                    suggested_fix=f"Add scenario_refs to FR {fr.fr_id} or re-run spec."))
        fr_keys = {f.row_key for f in frs}
        for sc in scenarios:
            if not any(ref in fr_keys for ref in sc.fr_refs):
                findings.append(_finding(check_id="scenario_no_fr", group="major", row_key=sc.row_key,
                    description=f"Acceptance scenario {sc.row_key} (#{sc.scenario_index}) references no FR.",
                    suggested_fix="Add fr_refs to this scenario or re-run spec."))

        # Depends_on integrity
        all_spec_keys = {s.row_key for s in specs}
        for dep in spec.depends_on or []:
            if dep not in all_spec_keys:
                findings.append(_finding(check_id="depends_on_missing", group="major", row_key=spec.row_key,
                    description=f"FRS {spec.row_key} depends on {dep}, which does not exist.",
                    suggested_fix=f"Either remove the dependency or create FRS {dep}."))

    # MINOR — spec completeness
    for spec in completed_specs:
        if spec.completeness < 90:
            findings.append(_finding(check_id="spec_completeness", group="minor", row_key=spec.row_key,
                description=f"FRS {spec.row_key} completeness {spec.completeness}%.",
                suggested_fix="Review the AI's note in narrative or open_questions; address gaps and re-run."))

    # COVERAGE — every BR row must be traced by ≥1 FRS
    all_brs = await _all_br_row_keys(document_id, db)
    covered_brs = await _br_keys_traced_by_any_spec(document_id, db)
    for br_key in (all_brs - covered_brs):
        findings.append(_finding(check_id="br_uncovered_in_frs", group="coverage", target_ref=br_key,
            description=f"BR {br_key} is not traced by any FRS.",
            suggested_fix="Add the BR to a backlog stub via [Edit module backlog]."))

    # WARNINGS — open decisions
    open_decisions = await _active_rows_by_status(FrsSpecDecision, document_id, "open", db)
    for d in open_decisions:
        findings.append(_finding(check_id="open_spec_decision", group="warnings", row_key=d.row_key,
            description=f"Decision '{d.question[:80]}…' is open. AI recommends option {d.recommended_index}.",
            suggested_fix="Resolve via the Decision panel."))

    return findings
```

### 6.7 Export bundle

`backend/app/services/artifacts/exporters/frs.py` produces a zip:

```
frs-export-<project>-<timestamp>.zip
  ├── README.md                              # overview + traceability summary + counts
  ├── modules/
  │     ├── module001-user-onboarding.md     # rendered from module-template.md
  │     ├── module002-authentication.md
  │     └── …
  ├── specs/
  │     ├── m001-frs001-user-registration.md # rendered from frs-template.md
  │     ├── m001-frs002-email-verification.md
  │     └── …
  └── traceability/
        ├── br-to-frs.md                     # BR-007 → [M001-FRS001, M002-FRS004]
        ├── nfr-to-frs.md                    # N-005 → [M001-FRS001]
        ├── module-to-frs.md                 # MOD-001 → [FRS001, FRS002, FRS003]
        └── matrix.csv                       # flat CSV of all traceability rows
```

Each module file is built from the `frs_modules` + child rows. Each spec file is built from
the `frs_specs` row + all sub-rows, following the template structure. The CSV is the raw
`frs_traceability` table.

`GET /artifacts/frs/export` returns the zip as `application/zip` with
`Content-Disposition: attachment; filename=frs-export-...`.

### 6.8 Celery tasks

```python
@celery_app.task(name="incorporate_frs_answer", bind=True)
def incorporate_frs_answer(self, project_id: str, target_spec_row_key: str | None = None):
    """User answered a question; re-run the affected spec(s)."""
    return _run_async(_incorporate_frs_answer(uuid.UUID(project_id), target_spec_row_key))


@celery_app.task(name="regenerate_frs_spec", bind=True)
def regenerate_frs_spec(self, project_id: str, spec_row_key: str):
    return _run_async(_regenerate_frs_spec(uuid.UUID(project_id), spec_row_key))


@celery_app.task(name="regenerate_frs_module", bind=True)
def regenerate_frs_module(self, project_id: str, module_row_key: str):
    return _run_async(_regenerate_frs_module(uuid.UUID(project_id), module_row_key))
```

---

## 7. Frontend implementation (Stage B)

### 7.1 Files (under `frontend/`)

| Path | Purpose | New / Extend |
|------|---------|--------------|
| `lib/types.ts` | Add `FrsScreenRow`, `FrsUiComponentRow`, `FrsEndpointRow`, `FrsDataEntityRow`, `FrsBusinessRuleRow`, `FrsAcceptanceScenarioRow`, `FrsFunctionalRequirementRow`, `FrsTraceabilityRow`, `FrsCoverage` | extend (Stage A added base types) |
| `lib/frs-manifest.ts` | Add `FRS_TRACE_KIND_STYLES`, `FRS_HTTP_METHOD_COLORS`, `FRS_FINDING_GROUPS` | extend |
| `lib/api.ts` | Add Stage-B routes (`design`, `regenerate`, `figma-link`, `validate`, `coverage`, `export`) | extend |
| `app/components/frs/FrsBuilderView.tsx` | Mount Stage-B surfaces (FrsModuleRail's nested specs, FrsSpecPanel, Findings, Coverage, Export) | extend (Stage A added root component) |
| `app/components/frs/FrsTwoPhaseGenerationViz.tsx` | Replaces Stage A's simpler theater when full pipeline runs (shows Phase A + Phase B) | new |
| `app/components/frs/FrsModuleRail.tsx` | Extend to nest individual spec rows under each module (Stage A only showed stub count) | extend |
| `app/components/frs/FrsSpecPanel.tsx` | The big spec view — orchestrates all sub-section components | new |
| `app/components/frs/FrsScreenCard.tsx` | §1.1 — one card per screen + FigmaLinkPrompt | new |
| `app/components/frs/FrsUiComponentCard.tsx` | §1.2 — row per component (collapsible) | new |
| `app/components/frs/FrsEndpointCard.tsx` | §2.2 — collapsible 6-section card | new |
| `app/components/frs/FrsDataEntityCard.tsx` | §3.2 — columns/keys/indexes editable inline | new |
| `app/components/frs/FrsBusinessRulesTable.tsx` | §4.1 — table | new |
| `app/components/frs/FrsScenariosList.tsx` | Scenarios with ≥6 ≥2-neg counters | new |
| `app/components/frs/FrsFunctionalRequirementsList.tsx` | FR list w/ scenario refs as chips | new |
| `app/components/frs/FigmaLinkPrompt.tsx` | Inline prompt within screen card | new |
| `app/components/frs/FrsSpecDecisionPrompt.tsx` | MCQ Radix popover for spec-scoped decisions | new |
| `app/components/frs/FrsTraceChip.tsx` | Trace chip w/ new target_kind colour palette | new |
| `app/components/frs/FrsFindingsDrawer.tsx` | Full validation drawer (5 groups, accept-fix, jump-to-row) | new |
| `app/components/frs/FrsCoverageGalaxy.tsx` | BR ↔ FRS bezier viz (~120 LOC SVG) | new |
| `app/components/frs/BrdConfettiBurst.tsx` | Reuse existing | reuse |

### 7.2 The spec panel — the big view

This is the centerpiece of Stage B. One spec panel per selected FRS:

```
┌────────────────────────────────────────────────────────────────────────────┐
│ § FRS M001-FRS001 · User Registration                                       │
│ Priority [P0] · Layer 1 · BR refs [BR-007, BR-012] · NFR [N-005] · Dep [M000-FRS001]│
│ [Edit metadata] [Regenerate] [⤴ History] [🔒 Lock]   completeness 92% · high │
│ ──────────────────────────────────────────────────────────────────────────  │
│                                                                              │
│ ▾ Intent / Narrative                                                         │
│   <editable textarea>                                                        │
│                                                                              │
│ ▾ § 1. UI Specification                                                      │
│   ┌─ If no Figma link: ──────────────────────────────────────────────────  │
│   │ ⚠  Figma link required.                                                 │
│   │    Once provided, AI will author the UI spec following the design.      │
│   │    [Add Figma link]  [Skip — UI design TBD]                              │
│   └─────────────────────────────────────────────────────────────────────────│
│                                                                              │
│   ┌─ If Figma link present: ─────────────────────────────────────────────── │
│   │  1.1 Screens                                                            │
│   │    Card: Customer Registration   [Edit] [🔒]                            │
│   │      Figma: https://figma.com/file/xyz/...                              │
│   │      Purpose · Layout · Navigation · Interactive behavior               │
│   │    [+ Add screen]                                                       │
│   │                                                                          │
│   │  1.2 UI Components on Each Screen                                       │
│   │    On 'Customer Registration':                                          │
│   │      Email Input · input · mandatory                                    │
│   │      Password Input · input · mandatory                                 │
│   │      Submit Button · button · enable_when=form-valid                    │
│   │    [+ Add component]                                                    │
│   │                                                                          │
│   │  1.3 UI Data Mapping (rows: field → API param)                          │
│   └─────────────────────────────────────────────────────────────────────────│
│                                                                              │
│ ▾ § 2. Backend Service Specification                                         │
│   2.1 Service Overview (editable text)                                       │
│   2.2 Service Endpoints                                                      │
│     Card: POST /api/customers/register                                       │
│       sync · idempotent: no                                                  │
│       ▾ Request   (headers, body, validation, example JSON)                  │
│       ▾ Response  (structure, fields, example)                               │
│       ▾ Errors    (400/409/500 codes, retry policy)                          │
│       ▾ Security  (Bearer JWT, roles)                                        │
│       ▾ Operational (rate limit 100/min, timeout 5s)                         │
│       [Edit] [🔒]                                                            │
│     [+ Add endpoint]                                                         │
│   2.3 Integration Specification (rows or N/A)                                │
│                                                                              │
│ ▾ § 3. Database / Storage / Cache Specification                              │
│   3.1 Data Store Overview (editable text)                                    │
│   3.2 Table / Collection Definitions                                         │
│     Card: customer_profile                                                   │
│       data_store_type: RDBMS · expected_volume: ~10k/day                     │
│       ▾ Columns (rows; click to edit each)                                   │
│       ▾ Keys & Constraints                                                   │
│       ▾ Indexes                                                              │
│       ▾ Relationships                                                        │
│       [Edit] [🔒]                                                            │
│   3.3 SQL / Data Access Logic (text)                                         │
│   3.4 Cache (N/A or rows)                                                    │
│                                                                              │
│ ▾ § 4. Cross-Cutting                                                         │
│   4.1 Business Rules (table)                                                 │
│     | BR-1 | Email must be unique | Registration form | Reject if exists |  │
│   4.2 Security Specification (text)                                          │
│                                                                              │
│ ▾ Independent Test                                                           │
│ ▾ Acceptance Scenarios     6/6 scenarios · 2/2 negatives  ✓                  │
│   1. Given a new user · When … · Then …                                      │
│   2. ✘ Given duplicate email · When … · Then 409 returned · [negative]       │
│   …                                                                          │
│ ▾ Functional Requirements                                                    │
│   FR-1 · "System must accept new email/password registration" → scenarios 1,3│
│   FR-2 · "System must reject duplicate emails" → scenario 2                  │
│   …                                                                          │
│ ▾ Data and Validation (text)                                                 │
│ ▾ Errors and Edge Cases (text)                                               │
│ ▾ Observability (text or rows)                                               │
│ ▾ Implementation Tasks (optional checklist)                                  │
│                                                                              │
│ ⚠ 1 [SPEC-DECISION] open — "Hard-fail or soft-warn on duplicate email?"     │
│   [Review decision →]                                                         │
└────────────────────────────────────────────────────────────────────────────┘
```

Every editable element uses inline edit (textarea or modal) + version + lock + restore.

### 7.3 FigmaLinkPrompt

```tsx
function FigmaLinkPrompt({ specRowKey, projectId, onLinkAdded }: Props) {
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (linkValue: string) => {
    setBusy(true)
    try {
      await api.frs.setFigmaLink(projectId, specRowKey, { link: linkValue })
      toast.success(linkValue === '__none__' ? 'Skipped — UI spec marked TBD' : 'Regenerating UI spec…')
      onLinkAdded()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle className="text-amber-600 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-amber-900">Figma link required</p>
          <p className="text-xs text-amber-700 mt-1">
            UI Specification cannot be authored until a Figma design link is provided.
            Once added, the AI will follow the design section by section.
          </p>
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <input
          type="url" value={link} onChange={(e) => setLink(e.target.value)}
          placeholder="https://figma.com/file/.../node-id=..."
          className="flex-1 rounded-md border border-amber-300 px-3 py-1.5 text-sm"
        />
        <button onClick={() => submit(link)} disabled={!link || busy}
          className="rounded-md bg-amber-600 text-white px-3 py-1.5 text-xs font-semibold disabled:opacity-50">
          {busy ? 'Saving…' : 'Add link'}
        </button>
        <button onClick={() => submit('__none__')} disabled={busy}
          className="rounded-md border border-amber-300 text-amber-700 px-3 py-1.5 text-xs">
          Skip — UI TBD
        </button>
      </div>
    </div>
  )
}
```

### 7.4 FrsSpecDecisionPrompt

```
┌─ Decision M001-FRS001-DEC-1 ────────────────────────── ✕ ─┐
│ Hard-fail or soft-warn on duplicate email registration?  │
│                                                          │
│ ✦ AI recommends: Option A                                │
│                                                          │
│ ⦿ Option A — Hard-fail with 409                          │
│   Description: Reject with HTTP 409 Conflict.            │
│   Implications: Clear contract; matches REST conventions │
│                                                          │
│ ◯ Option B — Soft-warn + auto-resend verification        │
│   Description: Return 200 OK with a warning; trigger     │
│   re-send of verification email.                         │
│   Implications: Friendlier UX; obscures account enumeration│
│                                                          │
│ ◯ Option C — 422 with field error                        │
│   Description: Return 422 Unprocessable Entity.          │
│   Implications: Middle ground; non-standard for dupe.    │
│                                                          │
│ [Accept AI recommendation]  [Override → Option B]  [Override → Option C]│
│ [Dismiss — not relevant]                                  │
└──────────────────────────────────────────────────────────┘
```

### 7.5 FrsModuleRail extension

Stage A showed each module + stub count. Stage B nests individual spec rows:

```
┌────────────────────────────────┐
│ MODULES                        │
│                                │
│ ▼ MOD-001 User Onboarding (3)  │   ← expanded
│   • M001-FRS001 ● User Reg.    │
│   • M001-FRS002 ● Login        │
│   • M001-FRS003 ◐ Wizard       │   ← currently regenerating
│                                │
│ ▶ MOD-002 Authentication (2)   │
│ ▶ MOD-003 Notifications (4)    │
│ ▶ MOD-000 Cross-cutting (2)    │
│                                │
│ [+ Add Module]                 │
└────────────────────────────────┘
```

Right-click a spec row → context menu:
- "Open spec"
- "Regenerate spec"
- "Lock spec"
- "Delete spec"

### 7.6 FrsFindingsDrawer (full)

```
┌─ FRS Findings ──────────────────────────────────────── ✕ ─┐
│ 7 findings to resolve before validation                  │
│                                                          │
│ ▾ Critical (1)                                           │
│   • Cyclic depends_on graph: M001-FRS003 → M002-FRS005 → │
│     M001-FRS003                                          │
│     [Show cycle] [Edit M001-FRS003 depends_on]           │
│                                                          │
│ ▾ Major (3)                                              │
│   ☐ M001-FRS001 has UI surfaces but no Figma link        │
│     [Add link] [Jump to spec →]                          │
│   ☐ M002-FRS004 has 4 acceptance scenarios (need ≥6)     │
│     [Accept fix — regenerate to add 2 more]              │
│     [Jump to scenarios →]                                │
│   ☐ FR-2 of M001-FRS001 references no scenario           │
│     [Accept fix — add scenario_ref] [Edit FR →]          │
│                                                          │
│ ▾ Minor (0)                                              │
│                                                          │
│ ▾ Coverage (1) — non-blocking                            │
│   ⚠ BR-019 is not traced by any FRS                      │
│     [Add stub to a module]                               │
│                                                          │
│ ▾ Warnings (2) — non-blocking                            │
│   • Decision M001-FRS001-DEC-1 still open                │
│     [Review decision]                                    │
│   • Module MOD-003 has 1 spec (under-decomposed)         │
│     [Open MOD-003]                                       │
│                                                          │
│ ────────────────────────────────────────────────────     │
│             [ Validate FRS ] (disabled — 4 blocking)     │
│                                                          │
│ [override blocking findings] (platform_admin only)       │
└──────────────────────────────────────────────────────────┘
```

The "Validate FRS" button enables only when critical + major findings = 0. Coverage and warnings
are visible but don't block validation. The drawer mirrors the BRD `FindingsDrawer` shape with
FRS-specific accept-fix flows.

### 7.7 FrsCoverageGalaxy

A modal opened from the header's `✦ Coverage` button. Shows the BR ↔ FRS coverage map:

```
┌─ BR → FRS Coverage Map ───────────────────────────── ✕ ─┐
│   BRD                              FRS                  │
│   ─────────────────────            ───────────────────  │
│   ● BR-001  must  ───────────►   M001-FRS001  ✓        │
│   ● BR-002  must  ──────────────► M002-FRS004  ✓        │
│   ● BR-003  should ───────────►   M001-FRS002  ✓        │
│   ● BR-004  must  ───────────►   M001-FRS003  ✓        │
│   ● BR-005  could ──╮              M002-FRS005  ✓       │
│                     └─►            M003-FRS006  ✓       │
│   ● BR-006  must                                        │
│   ● BR-007  must  ───────────►   M001-FRS001  ✓        │
│   ⚠ BR-019  must  (uncovered — glowing red)             │
│                                                          │
│   17 of 18 BRs covered. 1 uncovered.                    │
└──────────────────────────────────────────────────────────┘
```

Implementation: ~120 LOC SVG with hand-laid anchor points + cubic bezier curves. Iterates
`api.frs.coverage(projectId)` response.

### 7.8 Export menu

Triggered from the header's `⤓ Export` button:

```
[ Markdown bundle (.zip) ← primary ]
  DOCX (coming soon — disabled)
  Copy public link (coming soon — disabled)
```

Clicking Markdown bundle calls `GET /artifacts/frs/export`; browser saves the zip.

---

## 8. Workflow stages (Stage B's user journey)

- **Stage B-0** — Stage A complete; user has no critical/major Stage-A findings open.
- **Stage B-1** — Generation theater shows Phase B starting: parallel module bars filling.
- **Stage B-2** — On completion, status → `in_interview`. Module rail now has nested spec rows.
- **Stage B-3** — User clicks a spec → `FrsSpecPanel` renders the full template structure.
- **Stage B-4** — If §1 UI Spec is blocked, user sees FigmaLinkPrompt; either adds link
  (triggers UI-only regen) or skips.
- **Stage B-5** — User reviews scenarios, FRs, business rules; edits in place (each row is
  versioned + lockable).
- **Stage B-6** — User resolves [SPEC-DECISION] prompts (or leaves them open as warnings).
- **Stage B-7** — User clicks `✓ Check & Validate` → FrsFindingsDrawer (GET, read-only). Sees
  full Stage-A + Stage-B findings.
- **Stage B-8** — User addresses blocking findings (accept fix / edit / regenerate). Drawer
  count decrements.
- **Stage B-9** — User clicks `Validate FRS` (POST, commits) → confetti, status → `validated`,
  all rows locked.
- **Stage B-10** — User clicks Export → downloads markdown bundle.
- **Stage B-11** — Test Cases chip in workspace flips to "Disabled — FRS validated ✓".

---

## 9. Defaults & scope decisions (baked in)

1. **Figma: link-only in v1.** Captured as `figma_link` on each screen. No Figma API or MCP
   fetch. Downstream coding agent fetches the design when generating UI code (in v2+).
2. **Skip-Figma option always available.** Sentinel `figma_link='__none__'` lets a user proceed
   with placeholder UI spec ("UI layout TBD — Figma design not yet available"). Validation
   surfaces this as a warning (not major) when the sentinel is set.
3. **[SPEC-DECISION] non-blocking.** AI picks `recommended_index` and authors the spec; user
   can confirm/override/dismiss. Open decisions become warnings (not majors).
4. **Section omission allowed.** Spec may omit §1 UI / §3 Database etc. when genuinely not
   relevant; AI must justify in `narrative`. Validator only flags omission when the module's
   interfaces indicate the section should exist.
5. **`completeness ≥ 90` is the AI's self-rating threshold.** Below 90 → minor finding.
6. **Per-spec regenerate preserves locked rows.** Lock a scenario / FR / endpoint / entity →
   it survives regeneration verbatim.
7. **Coverage galaxy uses `Must`-priority threshold only for blocking.** Should/Could/Wont BRs
   surface as coverage gaps but don't block validation.
8. **Traceability is replace-all per regenerate.** No history kept for `frs_traceability`
   rows; the latest AI output is canonical. (Versioning would create row explosion with no UX
   benefit.)

All defaults reversible without schema migration.

---

## 10. Implementation phases

### Phase B1 — Backend (~6 days)

| # | Task | Files |
|---|------|-------|
| B1.1 | Add Stage B unit to manifest | extend `manifest/frs.py` |
| B1.2 | Mock fixture for design_module (one module with 2 specs covering UI + non-UI) | `services/llm/fixtures/frs_design_module.json` |
| B1.3 | DSPy Signature + Module + runner | extend `services/skills/dspy_frs.py` |
| B1.4 | Orchestrator: `generate_frs_design_module`, `generate_frs_all`, per-spec regen, figma-link handler, decision resolver | extend `frs_orchestrator.py` |
| B1.5 | Validator: full Stage-B rules | extend `validators/frs.py` |
| B1.6 | Stage-B API routes | extend `api/frs.py` |
| B1.7 | Exporter (markdown bundle) | `services/artifacts/exporters/frs.py` |
| B1.8 | Celery tasks | extend `workers/tasks.py`, `workers/dispatch.py` |

### Phase B2 — Frontend atomic components (~7 days)

| # | Task | Files |
|---|------|-------|
| B2.1 | Type additions (sub-row types, traceability, coverage) | extend `lib/types.ts` |
| B2.2 | API client (Stage-B endpoints) | extend `lib/api.ts` |
| B2.3 | Manifest mirror (trace kind colours, HTTP method colours) | extend `lib/frs-manifest.ts` |
| B2.4 | FrsScreenCard + FigmaLinkPrompt | new |
| B2.5 | FrsUiComponentCard (per-screen rows) | new |
| B2.6 | FrsEndpointCard (collapsible 6 sub-sections) | new |
| B2.7 | FrsDataEntityCard (columns/keys/indexes editable) | new |
| B2.8 | FrsBusinessRulesTable, FrsScenariosList, FrsFunctionalRequirementsList | new |
| B2.9 | FrsSpecDecisionPrompt (MCQ Radix popover) | new |
| B2.10 | FrsTraceChip + Trace popover | new |
| B2.11 | FrsModuleRail extension (nested spec rows + right-click menu) | extend |

### Phase B3 — Frontend hero surfaces (~3 days)

| # | Task | Files |
|---|------|-------|
| B3.1 | FrsSpecPanel — orchestrate all sub-components per spec | new |
| B3.2 | FrsTwoPhaseGenerationViz — Phase A + Phase B columns w/ live progress | new |
| B3.3 | FrsFindingsDrawer — full 5-group view w/ accept-fix flows | new |
| B3.4 | FrsCoverageGalaxy — BR ↔ FRS bezier SVG | new |
| B3.5 | Header actions (Sources / Coverage / Check & Validate / Export menu) | extend `FrsBuilderView.tsx` |
| B3.6 | Two-step validate (Check then Approve — clone from BRD pattern) | extend `FrsBuilderView.tsx` |
| B3.7 | Refine composer w/ affected-scope chip (module vs spec target) | extend `FrsBuilderView.tsx` |

### Phase B4 — Polish & verification (~3 days)

| # | Task |
|---|------|
| B4.1 | Always-visible "Resume from here" recovery button in generation theater |
| B4.2 | Reduced-motion paths; keyboard shortcuts (g s = section rail, g t = thread, / = composer) |
| B4.3 | Responsive breakpoints (md/sm) |
| B4.4 | Manual visual QA on `claims chatbot` project |
| B4.5 | Validation E2E: trigger every Stage-B finding type, verify accept-fix flows |
| B4.6 | Export QA: verify markdown bundle renders correctly in any markdown viewer |

**Total Stage B**: ~19 calendar days (BE + FE in parallel).

**Stage A + Stage B combined**: ~28 calendar days end-to-end.

---

## 11. Verification

### 11.1 Mock-mode E2E (no Vertex)

Pre-req: Stage A E2E (PRD 1 §11.1) has been run and produces modules + backlog stubs.

1. With Stage A complete (status `in_interview` after Stage A only), click "Continue to Stage 2".
2. Generation theater pivots to Phase B view: 4–6 modules queued, then running in parallel.
3. After ~2s (mock), status flips again to `in_interview` (full pipeline complete).
4. **Verify** in module rail:
   - Each module is expandable; specs nested under
   - At least one spec has the "⚠ Figma link required" inline prompt in §1
   - At least one spec has "⚠ 1 [SPEC-DECISION] open" banner
5. Click a spec → `FrsSpecPanel` renders all sections (UI Spec greyed if Figma missing).
6. Click `[Add Figma link]` → paste `https://figma.com/file/xyz/Demo`. Toast "Regenerating UI spec…".
   After ~2s, §1 populates with 1 screen + ~3 UI components.
7. Click "Skip — UI TBD" on a different spec → §1 shows note "UI layout TBD"; no warning.
8. Click the [SPEC-DECISION] banner → MCQ popover with 2–3 options. Click "Accept AI recommendation".
9. Click an acceptance scenario row → inline edit; change Given clause; row version v2.
10. Click "Regenerate spec" on a third spec → that spec only re-runs; its sub-rows update; locked
    rows preserved.
11. Click `✓ Check & Validate` → FrsFindingsDrawer opens.
12. Trigger findings:
    - Delete an FR's scenario_refs → "FR M001-FRS001-FR-1 references no scenario" appears.
    - Delete a scenario → "M002-FRS004 has 5 scenarios (need ≥6)" appears.
    - Set a spec's depends_on to a non-existent FRS row_key → "FRS depends on M999-FRS999, which
      does not exist" appears.
13. Click `[Accept fix]` on the FR/scenario finding → triggers spec re-run; finding clears.
14. Click `[Jump to spec →]` on the depends_on finding → smooth-scroll + spec row pulses red.
15. Resolve all findings, click `Validate FRS` → confetti animation, status → `validated`, all
    rows show 🔒 lock chips.
16. Click `⤓ Export → Markdown bundle` → zip downloads with `README.md`, `modules/*.md`,
    `specs/*.md`, `traceability/*.md`, `traceability/matrix.csv`.
17. Open a spec markdown file → verify it follows the template structure (heading, metadata
    line, all 4 detailed-design sections, scenarios, FRs).
18. Verify `traceability/br-to-frs.md` lists every BR with its covering FRS row_keys.
19. **Workspace chip**: Test Cases sublabel flips to "Disabled — FRS validated ✓".

### 11.2 Real-mode sanity (with Vertex)

- Run full pipeline with `LLM_PROVIDER=vertex`. Stage A: ~30–60s. Stage B: ~60–150s for 5 modules.
- Verify the AI:
  - Uses BR row_keys verbatim in `br_refs` (no fabrications).
  - Produces ≥6 scenarios per spec with ≥2 negatives, no exceptions.
  - Every FR's `scenario_refs` points to existing scenario row_keys (no orphans).
  - Every spec emits ≥1 traceability row to a BR.
  - Hoists cross-cutting standards as Layer 0 module when applicable.
  - Respects locked rows during regenerations.

### 11.3 Tests

- `LLM_PROVIDER=mock pytest backend/tests/test_frs_design_module.py`:
  - Smoke test calling `generate_frs_design_module` for a single module; asserts all 9 sub-row
    tables populated.
  - Figma blocking test: module with UI surface + no figma_link → AI returns `ui_blocked_reason`
    and no `frs_screens` rows.
  - Idempotency test: 2nd call with same input produces no new versions.
  - Lock test: lock a scenario, re-run, scenario unchanged.
- `pytest backend/tests/test_frs_validator_stage_b.py`:
  - Scenario count test (5 scenarios → major finding).
  - Negative scenario count test (1 negative → major finding).
  - FR ↔ scenario coverage test (FR with no scenario_refs → major finding).
  - depends_on cycle test (A→B→A → critical finding).
  - BR coverage test (BR with no FRS trace → coverage finding).
- `pytest backend/tests/test_frs_exporter.py`:
  - Smoke test generating zip from a fixture; asserts every file exists and parses as valid
    markdown.

### 11.4 Performance budget

- FrsSpecPanel TTI ≤ 1.5s on a spec with 5 screens × 12 components × 4 endpoints × 8 scenarios.
- Generation theater Phase B parallel progress dot updates ≤ 200ms after each unit_status JSONB merge.
- Export markdown bundle generation ≤ 5s for a 30-spec project.
- Coverage galaxy SVG render ≤ 100ms for 18 BRs × 30 FRSes.

### 11.5 Reduced-motion / a11y

- macOS "Reduce motion" → generation theater shows static "Designing module X of Y…" text
  instead of pulsing dots; confetti is skipped; spec section toggles are instant.
- Tab order through the spec panel hits every editable row, every action button, every chip.
- VoiceOver reads: "FRS M001-FRS001, User Registration, priority P0, traces to BR-007 and BR-012".

### 11.6 Type / lint

- `make typecheck && make lint` green on every PR.

---

## 12. Out of scope (deferred to v2+)

- **Figma API / MCP fetch**: link captured only in v1; no design-driven UI spec authoring.
- **Live preview of Figma frames**: link is a URL chip; user clicks to open Figma in a new tab.
- **DOCX / public-link export**: Markdown bundle only.
- **Inline AI rewrite of a single sentence** ("improve this scenario"): only full-spec regenerate.
- **Real-time multi-user editing / cursors**.
- **Cross-FRS auto-refactor** (e.g., AI detects two specs sharing a business rule and offers to
  hoist into Cross-cutting Standards): manual for v1; AI surfaces as warning finding.
- **Test Case artifact (E5)**: the validated FRS becomes the input; not built here.
- **Code generation**: never — SpecForge is spec-first.

---

## 13. Risks & open UX questions

- **Spec panel density**: A spec with 5 screens × 12 components × 4 endpoints × 8 scenarios is
  a lot of cards. Mitigation: default-collapse all card bodies; "Expand all in §1.2" header
  toggle.
- **Stage B latency**: Vertex latency for 5 modules × ~5 specs each = ~25 spec generations.
  Even with parallelism cap 3, total can hit 2–3 minutes. Mitigation: theater shows live
  per-module progress; "Resume from here" recovery button always visible.
- **Figma link friction**: Users without Figma may abandon. Mitigation: "Skip — UI TBD" is
  a one-click escape; FRS proceeds with placeholder UI spec; validation surfaces it as
  warning only.
- **Decision overload**: AI may emit 3–5 [SPEC-DECISION] questions per spec. Mitigation: cap
  decisions per spec at 3 in the DSPy instruction; aggregate in a single "Decisions" tab in
  the spec panel rather than inline banners.
- **Coverage galaxy at scale**: 30 BRs × 30 FRSes = 900 candidate lines. Mitigation: only draw
  lines for actually-existing traceability rows (~30–60 lines typically); group lines by BR
  with collapsible sub-rays.
- **depends_on cycles after manual edit**: User may add a circular `depends_on` while editing.
  Mitigation: edit endpoint validates the new value before commit; validator catches missed
  cycles as critical findings.

---

## 14. Appendix · Stage B manifest sketch (extends `manifest/frs.py`)

```python
FRS_STAGE_B_UNIT = FrsUnitSpec(
    unit_key="design_module",
    phase="B",
    label="Design module FRS specs",
    writes=[
        "frs_specs",                       # updated from stub → full content
        "frs_screens",
        "frs_ui_components",
        "frs_endpoints",
        "frs_data_entities",
        "frs_business_rules",
        "frs_acceptance_scenarios",
        "frs_functional_requirements",
        "frs_spec_decisions",              # spec-scoped (module-scoped were in Stage A)
        "frs_traceability",                # replace-all, not versioned
    ],
    depends_on=["modularize"],
    unit_instruction=...,                  # full docstring from FrsDesignModuleSignature
    discover_question_keys=["frs_4a", "frs_5a", "frs_6a", "frs_6b", "frs_7a", "frs_8a"],
)


FRS_MANIFEST: list[FrsUnitSpec] = [
    FRS_STAGE_A_UNIT,                      # from PRD 1
    FRS_STAGE_B_UNIT,                      # this PRD
]

FRS_TABLE_MAP_STAGE_B: dict[str, type] = {
    "frs_screens":                  FrsScreen,
    "frs_ui_components":            FrsUiComponent,
    "frs_endpoints":                FrsEndpoint,
    "frs_data_entities":            FrsDataEntity,
    "frs_business_rules":           FrsBusinessRule,
    "frs_acceptance_scenarios":     FrsAcceptanceScenario,
    "frs_functional_requirements":  FrsFunctionalRequirement,
    # frs_specs + frs_spec_decisions also in Stage A's map; same table, both stages write
    # frs_traceability has no versioning, separate handler (`_upsert_frs_traceability`)
}

# Full table map (both stages combined):
FRS_TABLE_MAP = {**FRS_TABLE_MAP_STAGE_A, **FRS_TABLE_MAP_STAGE_B}
```

---

## 15. Appendix · Quick-reference component map

```
FrsBuilderView (extended by both PRDs)
├── Stage A surfaces (PRD 1)
│   ├── FrsEmptyState
│   ├── DiscoverPhase (existing, FRS catalog)
│   ├── FrsModularizeTheater
│   ├── FrsModulePanel
│   ├── FrsBacklogTable
│   └── FrsModularizeFindings
├── Stage B surfaces (THIS PRD)
│   ├── FrsTwoPhaseGenerationViz
│   │   ├── Phase A column (modularize ✓)
│   │   └── Phase B column (per-module parallel)
│   ├── FrsModuleRail (extended with nested spec rows)
│   └── FrsSpecPanel
│       ├── Spec metadata header + actions
│       ├── Narrative (editable)
│       ├── § 1. UI Spec
│       │   ├── FigmaLinkPrompt (if missing)
│       │   ├── FrsScreenCard[]
│       │   └── FrsUiComponentCard[]
│       ├── § 2. Backend Spec
│       │   ├── Service Overview text
│       │   ├── FrsEndpointCard[] (collapsible 6 sub-sections each)
│       │   └── Integration Spec text/rows
│       ├── § 3. Data Spec
│       │   ├── Data Store Overview text
│       │   ├── FrsDataEntityCard[] (columns/keys/indexes editable)
│       │   ├── SQL/Access Logic text
│       │   └── Cache rows (optional)
│       ├── § 4. Cross-Cutting
│       │   ├── FrsBusinessRulesTable
│       │   └── Security Spec text
│       ├── Independent Test (text)
│       ├── FrsScenariosList (≥6 ≥2-neg counters)
│       ├── FrsFunctionalRequirementsList (each row → scenario refs as chips)
│       ├── Data and Validation (text)
│       ├── Errors and Edge Cases (text)
│       ├── Observability (text or rows)
│       ├── Implementation Tasks (checklist)
│       └── FrsSpecDecisionPrompt (banner if open decisions)
├── Shared surfaces
│   ├── SourceStrip (extended with BRD layer)
│   ├── FrsBrdEchoStrip
│   ├── FrsTraceChip + popover
│   ├── FrsCoverageGalaxy (BR ↔ FRS bezier viz)
│   ├── FrsFindingsDrawer (full 5-group)
│   └── BrdConfettiBurst (reused for validate-success)
└── Q&A Thread (collapsible bottom)
```
