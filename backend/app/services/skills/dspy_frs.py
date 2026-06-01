"""DSPy modules for FRS generation — 2 units: modularize (Stage A) + design_module (Stage B).

Stage A: one DSPy call decomposes the BRD into 5–12 modules + backlog stubs.
Stage B: per-module DSPy call (parallel) authors full FRS specs.

Pattern follows dspy_brd.py:
- Pydantic output model
- DSPy Signature with typed docstring
- DSPy Module (ChainOfThought)
- Async runner (mock path → fixture, real path → Gemini)
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Literal

import dspy
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

_FIXTURE_DIR = Path(__file__).parent.parent / "llm" / "fixtures"


def _configure() -> None:
    from app.services.skills.fact_extractor.dspy_extractor import _configure_dspy
    _configure_dspy()


def _is_mock() -> bool:
    from app.config import get_settings
    return get_settings().llm_provider == "mock"


def _load_fixture(name: str) -> dict:
    """Load a fixture JSON file. Name prefix is implied (frs_*)."""
    path = _FIXTURE_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


# ── Common output models ──────────────────────────────────────────────────────

class FrsOpenQuestion(BaseModel):
    question: str
    field: str
    why: str
    example: str = ""


class FrsSpecDecisionRow(BaseModel):
    """[SPEC-DECISION] MCQ raised during modularize or design_module."""
    row_key: str
    spec_row_key: str | None = None       # set in Stage B (spec-scoped)
    module_row_key: str | None = None     # set in Stage A (module-scoped)
    question: str
    options: list[dict[str, Any]] = Field(
        description="2–4 options: each {label, description, implications}"
    )
    recommended_index: int = Field(ge=0)
    recommended_rationale: str


# ── Stage A — Modularize output models ────────────────────────────────────────

class FrsActorRow(BaseModel):
    actor_name: str
    relationship: Literal["primary_user", "dependency", "external_system", "downstream_consumer"]
    notes: str = ""


class FrsResponsibilityRow(BaseModel):
    responsibility: str
    frs_refs: list[str] = Field(default_factory=list, description="Backlog stub row_keys this maps to")


class FrsInterfaceRow(BaseModel):
    interface_kind: Literal["ui_surface", "api", "event"]
    direction: Literal["inbound", "outbound"] | None = None      # None for ui_surface
    transport: Literal["rest", "grpc", "mq", "webhook", "event_bus"] | None = None
    name: str
    counterpart: str | None = None
    user_role: str | None = None
    purpose: str = ""
    frs_ref: str | None = None


class FrsModuleDataRow(BaseModel):
    entity_name: str
    business_purpose: str = ""
    source_of_truth: str = ""


class FrsBacklogStub(BaseModel):
    row_key: str = Field(description="M001-FRS001 format (zero-padded, module-prefixed)")
    title: str
    priority: Literal["P0", "P1", "P2", "P3"]
    br_refs: list[str] = Field(description="BR row_keys from the validated BRD this stub traces to")
    description: str = Field(description="1–2 sentence description; Stage B expands to full FRS")


class FrsModuleInventoryRow(BaseModel):
    row_key: str = Field(description="MOD-000 for Cross-cutting Standards, MOD-001+, …")
    name: str = Field(description="Capability-language name — NEVER tech-specific")
    slug: str = Field(description="URL-safe kebab-case")
    layer: Literal["foundation", "vertical", "cross_cutting"]
    scope_in: str = Field(description="Bullet narrative of what's in scope")
    scope_out: str = Field(description="Bullet narrative of what's out of scope (with module-owner notes)")
    summary: str = Field(description="2–3 sentences describing the module")
    actors: list[FrsActorRow] = Field(description="2–8 actors typical")
    responsibilities: list[FrsResponsibilityRow] = Field(description="Business-language responsibilities; each maps to ≥1 FRS")
    interfaces: list[FrsInterfaceRow] = Field(description="UI surfaces + APIs (inbound/outbound) + events")
    data_entities: list[FrsModuleDataRow] = Field(description="Conceptual entities only; NO schema")
    frs_backlog: list[FrsBacklogStub] = Field(description="3–15 stubs typical")


class FrsModularizeOutput(BaseModel):
    modules: list[FrsModuleInventoryRow] = Field(description="5–12 modules typical")
    spec_decisions: list[FrsSpecDecisionRow] = Field(
        default_factory=list,
        description="Module-scoped [SPEC-DECISION] MCQs; cap at 5",
    )
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


# ── Stage A — Modularize signature ────────────────────────────────────────────

class FrsModularizeSignature(dspy.Signature):
    """Run Steps 1+2+3 of the FRS-Builder skill: decompose the validated BRD into
    business-capability modules using DDD bounded contexts.

    HARD RULES (non-negotiable):

    1. Module names MUST use capability/role language. NEVER use tech-specific names:
       no 'API', 'Service', 'DB', 'Lambda', 'Kafka', 'Postgres', 'Redis',
       'Microservice', 'Gateway', etc. Use 'Authentication' (not 'Auth API'),
       'Notifications' (not 'Notification Service'), 'Claims Triage' (not 'Triage Lambda').

    2. Modules do NOT integrate via shared internal data models or shared databases.
       Every cross-module dependency MUST appear in BOTH source and target modules'
       `interfaces` (source = outbound, target = inbound) with matching `name` and
       `transport`. Symmetry is enforced by the downstream validator.

    3. Do NOT create modules for deployment / CI/CD / infrastructure / environment
       setup — those are architecture concerns, not business capabilities.

    4. Apply DDD bounded-context signals: rules/invariants differ, language differs,
       data ownership differs, actors differ, change cadence differs.

    5. Apply sizing rules. Split if: multiple independent sub-capabilities, >3 major
       end-to-end flows, >5 aggregates, >2 unrelated external integrations, or would
       produce >15 FRS for one module. Merge if two candidate modules always change
       together or share core invariants.

    CROSS-CUTTING STANDARDS (Layer 0):
    If you detect ≥2 modules sharing common rules (error envelope, reference data,
    RBAC base, common audit pattern, shared date/timezone handling), hoist those
    rules into a Layer-0 module called 'Cross-cutting Standards' with
    row_key='MOD-000'. Feature modules will reference its FRS via `depends_on`
    during Stage B.

    BACKLOG STUBS:
    For each module produce 3–15 FRS slices. Each stub must:
    - Use row_key M001-FRS001, M001-FRS002, … (module-prefixed, zero-padded to 3 digits)
    - Have a 1–2 sentence description (Stage B expands to a full FRS spec)
    - Trace to ≥1 BR row_key from the validated BRD (br_refs)
    DO NOT write full FRS spec content here.

    AMBIGUITY ([SPEC-DECISION]):
    For any module-boundary decision where multiple reasonable decompositions exist,
    emit a SpecDecisionRow with 2–4 MCQ options, pick recommended_index (typically
    the simpler/lower-coupling option), and PROCEED. The user can override later.
    Cap at 5 module-scoped decisions per run.

    ROW_KEY CONVENTIONS:
    - Modules:        MOD-000 (Cross-cutting), MOD-001, MOD-002, …
    - Actors:         {module_row_key}-ACT-1, -ACT-2, …
    - Responsib.:     {module_row_key}-R-1, -R-2, …
    - Interfaces:     {module_row_key}-IF-1, -IF-2, …
    - Data entities:  {module_row_key}-E-1, -E-2, …
    - Backlog stubs:  M001-FRS001, M001-FRS002, …
    - Decisions:      MOD-001-DEC-1, MOD-001-DEC-2, …

    Preserve row_keys for any modules in current_modules JSON. Locked modules
    (in locked_modules JSON) must be reproduced verbatim.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    brief: str = dspy.InputField(desc="Optional user brief; may be empty")
    brd_context: str = dspy.InputField(desc="Full validated BRD: every row, formatted")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    source_sections: str = dspy.InputField(
        desc="Retrieved NFR / Architecture doc sections (if uploaded), else empty"
    )
    qa_pairs: str = dspy.InputField(desc="FRS discover Q&A answers")
    current_modules: str = dspy.InputField(
        desc="JSON of existing modules for idempotent regen; '[]' on first run"
    )
    locked_modules: str = dspy.InputField(
        desc="JSON of locked modules to preserve verbatim; '[]' if none locked"
    )
    result: FrsModularizeOutput = dspy.OutputField()


class FrsModularizeModule(dspy.Module):
    def __init__(self) -> None:
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


# ── Stage B — design_module output models ─────────────────────────────────────

class FrsScreenRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-SCR-N format")
    screen_name: str
    figma_link: str | None = Field(
        default=None,
        description="Provide null if UI blocked pending Figma link; else the URL or sentinel '__none__'",
    )
    purpose: str
    user_roles: list[str] = Field(default_factory=list)
    layout: str
    navigation: str
    interactive_behavior: str


class FrsUiComponentRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-CMP-N format")
    screen_row_key: str = Field(description="FK to a FrsScreenRow's row_key in the same spec")
    component_name: str
    component_type: str = Field(
        description=(
            "Conceptual only (NEVER library-specific). Acceptable: input, textarea, "
            "dropdown, multi_select, checkbox, radio, button, link, table, card, tab, "
            "modal, accordion, date_picker, file_upload."
        )
    )
    definition: dict[str, Any] = Field(
        description="{position, mandatory, default, placeholder, tooltip}",
    )
    behavior: dict[str, Any] = Field(
        description="{click, change, focus, blur, auto_populate, dependencies, conditional_display, editable}",
    )
    validation: dict[str, Any] = Field(
        description="{data_type, length, format, allowed_values, regex, mandatory, cross_field, uniqueness, server_side, message}",
    )
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="[{button, enabled_when, confirm_dialog, on_success, on_failure}, …]",
    )
    data_mapping: dict[str, Any] = Field(
        default_factory=dict,
        description="UI field → API param mapping; display vs stored value; dropdown source",
    )


class FrsEndpointRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-EP-N format")
    service_name: str
    endpoint_name: str
    url: str
    protocol: str = Field(description="HTTPS, gRPC, AMQP, etc.")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    sync_async: Literal["sync", "async"]
    idempotent: bool
    request_spec: dict[str, Any] = Field(
        description="{headers, query, path, body, validation, example}",
    )
    response_spec: dict[str, Any] = Field(
        description="{structure, fields, optional, example, pagination, sorting}",
    )
    error_handling: dict[str, Any] = Field(
        description="{codes: [{code, message, business_or_technical, retryable}], retry, fallback, timeout}",
    )
    security: dict[str, Any] = Field(
        description="{auth_method, required_token, roles, action_permission_map, masking, audit}",
    )
    operational: dict[str, Any] = Field(
        description="{rate_limit, timeout, max_payload, concurrency, transaction_boundary, versioning, bc_rules}",
    )
    integration_target: str | None = Field(
        default=None,
        description="External system name if this endpoint calls or is called by one; else null",
    )


class FrsDataEntityRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-DE-N format")
    entity_name: str
    data_store_type: Literal["RDBMS", "NoSQL", "ObjectStore", "Cache", "FileStorage"]
    description: str
    expected_volume: str = Field(description="e.g. '~10k rows/day; ~5M total'")
    columns: list[dict[str, Any]] = Field(
        description="[{name, type, length, nullable, mandatory, default, allowed_values, generated, sensitivity, encryption}, …]",
    )
    keys_constraints: dict[str, Any] = Field(
        description="{primary: [cols], foreign: [{cols, ref_entity, ref_cols, on_delete, on_update}], unique: [[cols]]}",
    )
    indexes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="[{name, columns, unique, purpose}, …]",
    )
    relationships: list[dict[str, Any]] = Field(
        default_factory=list,
        description="[{cardinality, target_entity, cascade}, …]",
    )
    access_logic: str = Field(description="SQL/data-access intent (not runnable); joins, pagination, search")
    cache_spec: dict[str, Any] | None = Field(
        default=None,
        description="{key_design, structure, ttl, invalidation, refresh, consistency, fallback} or null",
    )
    retention_policy: str = Field(description="Retention / archival rule")


class FrsBusinessRuleRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-BR-N format (local rule id, NOT BRD BR)")
    rule_id: str = Field(description="Local within this FRS, e.g. 'BR-1'")
    description: str
    applies_to: str = Field(description="Component / endpoint / entity this rule governs")
    logic_decision: str = Field(description="If-then rule logic")


class FrsAcceptanceScenarioRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-AS-N format")
    scenario_index: int = Field(ge=1, description="Display order")
    given: str
    when: str
    then: str
    is_negative: bool = Field(description="True for failure / error / rejection cases")
    fr_refs: list[str] = Field(
        description="≥1 functional_requirement row_key this scenario validates",
        min_length=1,
    )


class FrsFunctionalRequirementRow(BaseModel):
    row_key: str = Field(description="{spec_row_key}-FR-N format")
    fr_id: str = Field(description="Local within this FRS, e.g. 'FR-1'")
    requirement_text: str = Field(description="Precise, testable, self-contained")
    scenario_refs: list[str] = Field(
        description="≥1 acceptance_scenario row_key this FR is validated by",
        min_length=1,
    )


class FrsTraceabilityRow(BaseModel):
    source_table: Literal[
        "frs_specs", "frs_functional_requirements", "frs_acceptance_scenarios",
        "frs_endpoints", "frs_data_entities", "frs_screens", "frs_ui_components",
        "frs_business_rules",
    ]
    source_row_key: str
    target_kind: Literal[
        "brd_business_requirement", "brd_objective", "brd_kpi", "brd_risk",
        "brd_text_block", "nfr_driver", "app_fact", "doc_section",
        "discover_qa", "within_frs",
    ]
    target_ref: str
    target_label: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class FrsSpecFullOutput(BaseModel):
    row_key: str = Field(description="MUST match the backlog stub's row_key from Stage A")
    title: str
    priority: Literal["P0", "P1", "P2", "P3"]
    layer: Literal["foundation", "vertical", "cross_cutting"]
    br_refs: list[str] = Field(description="BR row_keys carried from stub; may be expanded")
    nfr_refs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(
        default_factory=list,
        description="Other FRS spec row_keys this depends on (e.g., M000-FRS001 for cross-cutting)",
    )
    narrative: str = Field(description="1–2 paragraphs of intent (what + why, not how)")
    screens: list[FrsScreenRow] = Field(default_factory=list)
    ui_components: list[FrsUiComponentRow] = Field(default_factory=list)
    endpoints: list[FrsEndpointRow] = Field(default_factory=list)
    data_entities: list[FrsDataEntityRow] = Field(default_factory=list)
    business_rules: list[FrsBusinessRuleRow] = Field(default_factory=list)
    acceptance_scenarios: list[FrsAcceptanceScenarioRow] = Field(
        ..., min_length=6,
        description="≥6 scenarios with ≥2 negative (is_negative=True)",
    )
    functional_requirements: list[FrsFunctionalRequirementRow] = Field(
        ..., min_length=1,
        description="≥1 FR; each must scenario_refs ≥1 scenario AND each scenario must fr_refs ≥1 FR",
    )
    spec_decisions: list[FrsSpecDecisionRow] = Field(default_factory=list)
    traceability: list[FrsTraceabilityRow] = Field(
        ..., min_length=1,
        description="≥1 row tracing this spec to a BR (target_kind='brd_business_requirement')",
    )
    independent_test: str = Field(description="2–5 sentences, system boundary only")
    data_and_validation: str
    errors_and_edge_cases: str
    observability: str
    implementation_tasks: list[dict[str, Any]] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]
    ui_blocked_reason: str | None = Field(
        default=None,
        description=(
            "Set to 'figma_link_required' when omitting §1 UI Spec because the module has "
            "ui_surface interfaces but no Figma link was provided. screens[] and "
            "ui_components[] MUST be empty when set."
        ),
    )


class FrsDesignModuleOutput(BaseModel):
    specs: list[FrsSpecFullOutput] = Field(
        description="One full FRS per backlog stub in the target module",
    )
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)
    completeness: int = Field(ge=0, le=100)
    confidence: Literal["high", "medium", "low"]


class FrsDesignSpecOutput(BaseModel):
    """Output of a SINGLE-spec design call (one FRS, not a whole module).

    Generating one spec per LLM call keeps each completion small + reliable
    (gemini truncates a whole-module output) and makes per-spec regeneration
    cheap. FR↔scenario cross-references stay coherent because both live in the
    same completion.
    """
    spec: FrsSpecFullOutput
    open_questions: list[FrsOpenQuestion] = Field(default_factory=list)


# ── Stage B — design_module signature ─────────────────────────────────────────

class FrsDesignModuleSignature(dspy.Signature):
    """Run Step 4 of the FRS-Builder skill for ONE module. For each FRS backlog stub
    in this module, produce a full development-ready FRS spec following the 12-section
    template (Intent · §1 UI · §2 Backend · §3 Data · §4 Cross-Cutting · Independent
    Test · Acceptance Scenarios · Functional Requirements · Data & Validation ·
    Errors & Edge Cases · Observability · Implementation Tasks · Traceability).

    HARD RULES (non-negotiable):

    1. Every FRS spec MUST have ≥1 traceability row to a BR row_key
       (target_kind='brd_business_requirement'). If a backlog stub has empty br_refs,
       this is a Stage-A defect — emit an open_question rather than fabricating a trace.

    2. Every FRS spec MUST have ≥6 acceptance_scenarios with ≥2 negative
       (is_negative=True). Negative scenarios cover failure / error / rejection paths.

    3. Every FRS spec MUST have ≥1 functional_requirement. Each FR MUST reference
       ≥1 acceptance_scenario row_key via scenario_refs, AND each scenario MUST
       reference ≥1 FR row_key via fr_refs (bidirectional coverage).

    4. Use row_keys from current_specs JSON to preserve continuity; never invent
       new row_keys for existing specs. Locked specs (in locked_specs JSON) must
       be reproduced verbatim — do not modify any fields.

    FIGMA-LINK BLOCKING GATE:
    Check the module's interfaces (module_context.interfaces). If any have
    interface_kind='ui_surface' AND no screen in current_specs for the target
    spec has a real figma_link (or the link is the sentinel '__none__'), OMIT
    the screens[] and ui_components[] arrays for that spec. Instead, set
    ui_blocked_reason='figma_link_required' and write a one-line note in
    narrative: '§1 UI Specification omitted pending Figma link.' Do NOT
    fabricate figma_link URLs. Do NOT author UI spec content without a real link.

    [SPEC-DECISION] AMBIGUITY:
    If multiple valid implementations exist (e.g., 'strip or reject', 'retry
    or fail-fast', 'eager or lazy', 'hard-fail or soft-warn'), emit a
    spec_decisions row with 2–4 MCQ options. Pick recommended_index (typically
    the simpler/safer option) and author the FRS using that choice — the spec
    MUST be internally consistent. The user will confirm/override later.

    DEPENDS_ON:
    If this spec depends on a Cross-cutting Standards FRS (e.g., for error
    envelope, audit pattern, RBAC base), list that FRS row_key in depends_on.
    Reference the dependency in the appropriate section (e.g., 'Error handling
    follows the common envelope defined in M000-FRS001 — see Depends on.').

    TRACEABILITY (emit rows for):
    - Spec → ≥1 BR (target_kind='brd_business_requirement')
    - Spec → ≥1 BRD objective (target_kind='brd_objective', when applicable)
    - Each FR → ≥1 BR or scenario (target_kind='brd_business_requirement' or 'within_frs')
    - Each scenario → ≥1 FR (target_kind='within_frs')
    - Optionally: spec → app_fact, doc_section, discover_qa, nfr_driver

    NFR DRIVERS:
    If a '=== Validated NFR Drivers ===' block is present in the context, then for
    each FRS spec whose design is materially shaped by a specific NFR (a latency,
    availability, security, scalability, etc. driver) emit a traceability row with
    target_kind='nfr_driver' and target_ref=<the NFR-nnn row_key>. If that block is
    absent, do NOT emit nfr_driver traces — never fabricate them.

    SECTION-OMISSION RULE:
    Omit only sections that are genuinely not relevant. Justify omission in
    narrative with a one-line note:
    - Pure backend FRS (no ui_surface in module_interfaces) → omit screens,
      ui_components
    - Pure UI aggregation FRS → omit endpoints, data_entities
    - Stateless FRS → omit data_entities
    Never omit acceptance_scenarios, functional_requirements, traceability —
    those are mandatory.

    ARCHITECTURE EXCLUSION:
    Never author FRS sections for deployment, CI/CD, infrastructure
    provisioning, runtime packaging, or environment setup. If a backlog stub
    appears to require such content, set its completeness=0 and emit an
    open_question pointing the user at the project's Architecture Design doc.

    ROW_KEY CONVENTIONS:
    - Screens:          {spec_row_key}-SCR-1, -SCR-2, …
    - UI Components:    {spec_row_key}-CMP-1, -CMP-2, …
    - Endpoints:        {spec_row_key}-EP-1, -EP-2, …
    - Data entities:    {spec_row_key}-DE-1, -DE-2, …
    - Business rules:   {spec_row_key}-BR-1, -BR-2, … (local rule, not BRD BR)
    - Scenarios:        {spec_row_key}-AS-1, -AS-2, …
    - FRs:              {spec_row_key}-FR-1, -FR-2, …
    - Spec decisions:   {spec_row_key}-DEC-1, -DEC-2, …

    COMPONENT TYPE GUIDANCE:
    Use CONCEPTUAL component types only — never library-specific. Acceptable
    values: 'input', 'textarea', 'dropdown', 'multi_select', 'checkbox',
    'radio', 'button', 'link', 'table', 'card', 'tab', 'modal', 'accordion',
    'date_picker', 'file_upload'. Component library mapping is the downstream
    coding agent's job.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    module_row_key: str = dspy.InputField()
    module_context: str = dspy.InputField(
        desc="JSON: active module's scope, actors, responsibilities, interfaces, data_entities, frs_backlog stubs"
    )
    other_modules_summary: str = dspy.InputField(
        desc="JSON list of sibling modules' names + cross-module interfaces (for depends_on awareness)"
    )
    brd_context: str = dspy.InputField(desc="Full validated BRD: every row, formatted")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    source_sections: str = dspy.InputField(
        desc="Depth-searched project doc sections (esp. NFR / Architecture if uploaded)"
    )
    qa_pairs: str = dspy.InputField(desc="FRS discover Q&A (design_module unit)")
    current_specs: str = dspy.InputField(
        desc="JSON of existing specs in this module (for idempotent regen); '[]' on first run"
    )
    locked_specs: str = dspy.InputField(
        desc="JSON of locked specs to preserve verbatim; '[]' if none locked"
    )
    resolved_decisions: str = dspy.InputField(
        desc="JSON of decisions where user has chosen an option; '[]' if none"
    )
    result: FrsDesignModuleOutput = dspy.OutputField()


class FrsDesignModuleModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(FrsDesignModuleSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_design_module(**kwargs) -> dict:
    if _is_mock():
        import json as _json
        fixture = _load_fixture("frs_design_module")
        # Remap fixture spec row_keys to match the actual Stage-A stub row_keys
        # stored in current_specs.  This lets the mock work for both test projects
        # (which use "M001-FRS001" keys from the modularize fixture) and real
        # projects (which use "MOD-002-FRS001" style keys from the LLM).
        try:
            current_stubs: list[dict] = _json.loads(kwargs.get("current_specs", "[]") or "[]")
            stub_keys = [s["row_key"] for s in current_stubs if s.get("row_key")]
        except Exception:
            stub_keys = []

        if not stub_keys:
            return fixture  # no stubs yet — return fixture as-is (no-op)

        fixture_specs: list[dict] = list(fixture.get("specs", []))
        remapped: list[dict] = []
        for i, spec in enumerate(fixture_specs):
            actual_key = stub_keys[i] if i < len(stub_keys) else spec["row_key"]
            old_key = spec["row_key"]  # e.g. "M001-FRS001"
            if actual_key == old_key:
                remapped.append(spec)
                continue
            # String-replace the old key prefix everywhere in this spec's JSON
            # so sub-row keys (M001-FRS001-AS-1 etc.) are remapped too.
            spec_str = _json.dumps(spec).replace(
                _json.dumps(old_key), _json.dumps(actual_key)
            ).replace(
                f'"{old_key}-', f'"{actual_key}-'
            )
            remapped.append(_json.loads(spec_str))

        return {**fixture, "specs": remapped}
    _configure()
    loop = asyncio.get_running_loop()
    # run_in_executor wraps a blocking (synchronous) DSPy call in a thread.
    # We shield the future so that if the outer wait_for cancels us, the thread
    # is allowed to finish cleanly and the CancelledError is re-raised as
    # TimeoutError by the caller rather than leaking as CancelledError.
    fut = loop.run_in_executor(None, lambda: FrsDesignModuleModule()(**kwargs))
    try:
        return await asyncio.shield(fut)
    except asyncio.CancelledError:
        # The outer wait_for timed out; let the thread finish in background and
        # surface a TimeoutError so the orchestrator logs correctly.
        raise TimeoutError("DSPy FrsDesignModule timed out")


# ── Stage B — design_spec signature (ONE spec per call) ───────────────────────


class FrsDesignSpecSignature(dspy.Signature):
    """Author ONE development-ready FRS spec for a single backlog stub.

    This is the per-spec variant of the module designer: it produces exactly one
    full FRS for `target_spec_row_key`, not a whole module. Generate the spec for
    the stub described in `target_spec_stub`, grounded in the full project context.

    HARD RULES (mandatory, never omit):
    - ≥6 acceptance_scenarios, with ≥2 negative (is_negative=True).
    - ≥1 functional_requirement. Bidirectional integrity: every FR's
      scenario_refs must reference ≥1 scenario in THIS spec, and every scenario's
      fr_refs must reference ≥1 FR in THIS spec.
    - ≥1 traceability row to a BR (target_kind='brd_business_requirement').
    - row_key of the output spec MUST equal target_spec_row_key exactly.

    SECTION-OMISSION RULE (justify omission in narrative):
    - Pure backend FRS (no ui_surface in module_context) → omit screens, ui_components.
    - Pure UI aggregation FRS → omit endpoints, data_entities.
    - Stateless FRS → omit data_entities.
    Never omit acceptance_scenarios, functional_requirements, traceability.

    FIGMA-LINK GATE: if the module has ui_surface interfaces but no figma_link is
    available, set ui_blocked_reason='figma_link_required' and leave screens[] +
    ui_components[] empty.

    DEPENDS_ON: if this spec relies on a cross-cutting capability (audit, error
    envelope, RBAC base) defined in another spec, list that FRS row_key in
    depends_on (see sibling_specs_summary + other_modules_summary).

    ARCHITECTURE EXCLUSION: never author FRS for deployment, CI/CD, infra
    provisioning, runtime packaging, or environment setup. If the stub requires
    such content, set completeness=0 and emit an open_question.

    ROW_KEY CONVENTIONS (prefix with target_spec_row_key):
    - Screens {key}-SCR-n · UI Components {key}-CMP-n · Endpoints {key}-EP-n
    - Data entities {key}-DE-n · Business rules {key}-BR-n · Scenarios {key}-AS-n
    - FRs {key}-FR-n · Spec decisions {key}-DEC-n

    COMPONENT TYPES: conceptual only ('input','textarea','dropdown','button',
    'table','card','modal','file_upload', etc.) — never library-specific.
    """
    project_name: str = dspy.InputField()
    business_unit: str = dspy.InputField()
    module_row_key: str = dspy.InputField()
    target_spec_row_key: str = dspy.InputField(
        desc="The single backlog stub row_key to design now. Output spec.row_key MUST equal this."
    )
    target_spec_stub: str = dspy.InputField(
        desc="JSON of the stub being designed: row_key, title, priority, layer, br_refs, narrative"
    )
    module_context: str = dspy.InputField(
        desc="JSON: this module's scope, actors, responsibilities, interfaces, data_entities"
    )
    sibling_specs_summary: str = dspy.InputField(
        desc="JSON list of the OTHER specs in this module (row_key + title) for depends_on awareness"
    )
    other_modules_summary: str = dspy.InputField(
        desc="JSON list of sibling modules' names + cross-module interfaces"
    )
    brd_context: str = dspy.InputField(desc="Full validated BRD: every row, formatted")
    cb_context: str = dspy.InputField(desc="Validated Concept Brief")
    app_brain: str = dspy.InputField(desc="In-scope application facts")
    source_sections: str = dspy.InputField(
        desc="Depth-searched project doc sections (esp. NFR / Architecture if uploaded)"
    )
    qa_pairs: str = dspy.InputField(desc="FRS discover Q&A (design_module unit)")
    current_spec: str = dspy.InputField(
        desc="JSON of the existing version of THIS spec for idempotent regen; '{}' on first run"
    )
    resolved_decisions: str = dspy.InputField(
        desc="JSON of decisions where the user has chosen an option; '[]' if none"
    )
    result: FrsDesignSpecOutput = dspy.OutputField()


class FrsDesignSpecModule(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.predict = dspy.ChainOfThought(FrsDesignSpecSignature)

    def forward(self, **kwargs) -> dict:
        return self.predict(**kwargs).result.model_dump()


async def run_design_spec(**kwargs) -> dict:
    """Generate ONE FRS spec. Mock returns a fixture spec remapped to the target."""
    if _is_mock():
        import json as _json
        import re as _re
        fixture = _load_fixture("frs_design_module")
        specs: list[dict] = list(fixture.get("specs", []))
        target = kwargs.get("target_spec_row_key", "")
        if not specs:
            return {"spec": {}, "open_questions": []}
        # Pick a fixture spec by FRS index so distinct fixture variants
        # (ui-blocked, backend-only, has-decision) map deterministically:
        # FRS001 → specs[0], FRS002 → specs[1], FRS003 → specs[2], wrap otherwise.
        m = _re.search(r"FRS0*([0-9]+)$", target)
        idx = (int(m.group(1)) - 1) if m else 0
        base = specs[idx % len(specs)]
        old_key = base.get("row_key", "")
        if target and old_key and target != old_key:
            base = _json.loads(
                _json.dumps(base).replace(f'"{old_key}', f'"{target}')
            )
        return {"spec": base, "open_questions": fixture.get("open_questions", [])}
    _configure()
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(None, lambda: FrsDesignSpecModule()(**kwargs))
    try:
        return await asyncio.shield(fut)
    except asyncio.CancelledError:
        raise TimeoutError("DSPy FrsDesignSpec timed out")
