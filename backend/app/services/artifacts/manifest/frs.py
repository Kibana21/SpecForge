"""FRS generation manifest: 2 phases, table maps, per-unit discover mapping.

Stage A — modularize (single DSPy call). Decomposes the validated BRD into
business-capability modules using DDD bounded contexts. Each module owns scope,
actors, responsibilities, interfaces (UI/APIs/events), data ownership, and an
FRS backlog of 3–15 stubs.

Stage B — design_module (dynamic, one DSPy call per module). Picks up where
Stage A left off and fills in each backlog stub with a full FRS spec.
Defined in this same module but actual orchestration is parallel-per-module.

Mirrors the BRD manifest pattern (manifest/brd.py) with FRS-specific tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class FrsUnitSpec:
    unit_key: str
    phase: Literal["A", "B"]
    label: str
    writes: list[str]                   # FRS table names this unit owns
    depends_on: list[str]               # unit_keys that must run first
    unit_instruction: str               # docstring guidance for DSPy signature
    discover_question_keys: list[str]
    timeout_seconds: int = 90


# ── Stage A unit: modularize ───────────────────────────────────────────────────

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
        "frs_specs",              # backlog stubs (completeness=0)
        "frs_spec_decisions",     # module-scoped only
    ],
    depends_on=[],
    unit_instruction=(
        "You are a senior Solution Architect performing FRS Modularization per the "
        "DDD-first guideline. Decompose the validated BRD into 5–12 business-capability "
        "modules using Domain-Driven Design bounded contexts.\n\n"

        "HARD RULES (non-negotiable):\n"
        "1. Module names MUST use capability/role language. NEVER use tech-specific "
        "   names: no 'API', 'Service', 'DB', 'Lambda', 'Kafka', 'Postgres', 'Redis', "
        "   'Microservice', 'Gateway', etc.\n"
        "2. Modules do NOT integrate via shared internal data models or shared databases. "
        "   Every cross-module dependency MUST appear in BOTH source and target modules' "
        "   `interfaces` (source = outbound, target = inbound) with matching `name` and "
        "   `transport`.\n"
        "3. Do NOT create modules for deployment, CI/CD, infrastructure, environment "
        "   setup — those are architecture concerns, not business capabilities.\n"
        "4. Apply the cohesion vs coupling check: split a module if it has multiple "
        "   independent sub-capabilities (>3 major flows), too many entities (>5 "
        "   aggregates), or would produce >15 FRS. Merge if two candidate modules "
        "   always change together or share core invariants.\n\n"

        "CROSS-CUTTING STANDARDS (Layer 0):\n"
        "If you detect ≥2 modules sharing common rules (error envelope, reference "
        "data, RBAC base, common audit pattern, shared date/timezone handling), "
        "hoist those rules into a single Layer-0 module called 'Cross-cutting "
        "Standards' with row_key='MOD-000'. Feature modules will reference its "
        "FRS via `depends_on` in Stage B.\n\n"

        "BACKLOG STUBS:\n"
        "For each module, produce a backlog of 3–15 FRS slices. Each slice must:\n"
        "- Have a stub row_key of the form M001-FRS001, M001-FRS002, … "
        "  (module-prefixed, zero-padded to 3 digits)\n"
        "- Trace to ≥1 BR row_key from the validated BRD (br_refs)\n"
        "- Have a 1–2 sentence description that Stage B will expand into full FRS "
        "  content\n"
        "DO NOT write full FRS spec content here — Stage B handles that.\n\n"

        "AMBIGUITY ([SPEC-DECISION]):\n"
        "For any module-boundary decision where multiple reasonable decompositions "
        "exist (e.g., 'should X be its own module or part of Y?'), emit a "
        "SpecDecisionRow with 2–4 MCQ options, pick recommended_index "
        "(typically the simpler/lower-coupling option), and PROCEED with that "
        "choice. The user can override later. Cap at 5 module-scoped decisions "
        "per run.\n\n"

        "ROW_KEY CONVENTIONS:\n"
        "- Modules:        MOD-000 (Cross-cutting Standards), MOD-001, MOD-002, …\n"
        "- Actors:         {module_row_key}-ACT-1, -ACT-2, …\n"
        "- Responsib.:     {module_row_key}-R-1, -R-2, …\n"
        "- Interfaces:     {module_row_key}-IF-1, -IF-2, …\n"
        "- Data entities:  {module_row_key}-E-1, -E-2, …\n"
        "- Backlog stubs:  M001-FRS001, M001-FRS002, … (zero-padded)\n"
        "- Decisions:      MOD-001-DEC-1, MOD-001-DEC-2, …\n\n"

        "Preserve row_keys for any modules present in current_modules JSON. "
        "Locked modules (in locked_modules JSON) must be reproduced verbatim."
    ),
    discover_question_keys=[
        "frs_1a", "frs_1b", "frs_2a", "frs_3a", "frs_3b", "frs_4a", "frs_9a",
    ],
    timeout_seconds=90,
)


# ── Stage B unit: design_module (dynamic per-module; see E4c-2 plan) ──────────

FRS_STAGE_B_UNIT = FrsUnitSpec(
    unit_key="design_module",
    phase="B",
    label="Design module FRS specs",
    writes=[
        "frs_specs",                       # filled out from stub form
        "frs_screens",
        "frs_ui_components",
        "frs_endpoints",
        "frs_data_entities",
        "frs_business_rules",
        "frs_acceptance_scenarios",
        "frs_functional_requirements",
        "frs_spec_decisions",              # spec-scoped
        "frs_traceability",                # replace-all, not versioned
    ],
    depends_on=["modularize"],
    unit_instruction=(
        "You are a senior Solution Architect performing FRS Authoring per the "
        "Functional Design guideline. For each FRS backlog stub in this module, "
        "produce a development-ready FRS spec following the 12-section template:\n"
        "  Intent · §1 UI Spec · §2 Backend Spec · §3 Data Spec · §4 Cross-Cutting · "
        "Independent Test · Acceptance Scenarios · Functional Requirements · "
        "Data & Validation · Errors & Edge Cases · Observability · "
        "Implementation Tasks · Traceability.\n\n"

        "HARD RULES (non-negotiable):\n"
        "1. Every FRS spec MUST have ≥1 traceability row to a BR row_key (target_kind="
        "   'brd_business_requirement'). If a backlog stub has empty br_refs, this is a "
        "   Stage-A defect — emit an open_question rather than fabricating a trace.\n"
        "2. Every FRS spec MUST have ≥6 acceptance_scenarios with ≥2 negative "
        "   (is_negative=True). Negative scenarios cover failure / error / rejection paths.\n"
        "3. Every FRS spec MUST have ≥1 functional_requirement. Each functional_requirement "
        "   MUST reference ≥1 acceptance_scenario row_key via scenario_refs, AND each "
        "   acceptance_scenario MUST reference ≥1 functional_requirement row_key via "
        "   fr_refs (bidirectional coverage).\n"
        "4. Use row_keys from current_specs JSON to preserve continuity; never invent new "
        "   row_keys for existing specs. Locked specs (in locked_specs JSON) must be "
        "   reproduced verbatim — do not modify their fields.\n\n"

        "FIGMA-LINK BLOCKING GATE:\n"
        "Check the module's interfaces (module_context.interfaces). If any have "
        "interface_kind='ui_surface' AND no screen in current_specs for the target spec has "
        "a figma_link (or the link is the sentinel '__none__'), OMIT the screens[] and "
        "ui_components[] arrays for that spec. Instead, set ui_blocked_reason='figma_link_required' "
        "and write a one-line note in narrative: '§1 UI Specification omitted pending Figma link.' "
        "Do NOT fabricate figma_link URLs. Do NOT author UI spec content without a real link.\n\n"

        "[SPEC-DECISION] AMBIGUITY:\n"
        "If multiple valid implementations exist (e.g., 'strip or reject special chars', "
        "'retry or fail-fast on timeout', 'eager or lazy load', 'hard-fail or soft-warn'), "
        "emit a spec_decisions row with 2–4 MCQ options. Pick recommended_index (typically "
        "the simpler/safer option) and author the FRS using that choice — the spec MUST be "
        "internally consistent with the chosen option. The user will confirm/override later. "
        "Open decisions are warnings, not majors — proceed.\n\n"

        "DEPENDS_ON:\n"
        "If this spec depends on a Cross-cutting Standards FRS (e.g., for error envelope, "
        "audit pattern, RBAC base), list that FRS row_key in depends_on. Reference the "
        "dependency in the appropriate section (e.g., 'Error handling follows the common "
        "envelope defined in M000-FRS001 — see Depends on.').\n\n"

        "TRACEABILITY (emit rows for):\n"
        "  • Spec → ≥1 BR (target_kind='brd_business_requirement')\n"
        "  • Spec → ≥1 BRD objective (target_kind='brd_objective', when applicable)\n"
        "  • Each FR → ≥1 BR or scenario (target_kind='brd_business_requirement' or "
        "    'within_frs')\n"
        "  • Each scenario → ≥1 FR (target_kind='within_frs')\n"
        "  • Optionally: spec → app_fact, doc_section, discover_qa, nfr_driver\n\n"

        "SECTION-OMISSION RULE:\n"
        "Omit only sections that are genuinely not relevant. Justify omission in narrative "
        "with a one-line note. Examples:\n"
        "  • Pure backend FRS (no ui_surface in module_interfaces) → omit screens, "
        "    ui_components\n"
        "  • Pure UI aggregation FRS → omit endpoints, data_entities\n"
        "  • Stateless FRS → omit data_entities\n"
        "Never omit acceptance_scenarios, functional_requirements, traceability — "
        "those are mandatory.\n\n"

        "ARCHITECTURE EXCLUSION:\n"
        "Never author FRS sections for deployment, CI/CD, infrastructure provisioning, "
        "runtime packaging, or environment setup. If a backlog stub appears to require "
        "such content, set its completeness=0 and emit an open_question pointing the user "
        "at the project's Architecture Design doc.\n\n"

        "ROW_KEY CONVENTIONS:\n"
        "  • Screens:          {spec_row_key}-SCR-1, -SCR-2, …\n"
        "  • UI Components:    {spec_row_key}-CMP-1, -CMP-2, …\n"
        "  • Endpoints:        {spec_row_key}-EP-1, -EP-2, …\n"
        "  • Data entities:    {spec_row_key}-DE-1, -DE-2, …\n"
        "  • Business rules:   {spec_row_key}-BR-1, -BR-2, … (local BR-1; not BRD BR)\n"
        "  • Scenarios:        {spec_row_key}-AS-1, -AS-2, …\n"
        "  • FRs:              {spec_row_key}-FR-1, -FR-2, …\n"
        "  • Spec decisions:   {spec_row_key}-DEC-1, -DEC-2, …\n\n"

        "COMPONENT TYPE GUIDANCE (UI):\n"
        "Use CONCEPTUAL component types only — never library-specific. Acceptable values: "
        "'input', 'textarea', 'dropdown', 'multi_select', 'checkbox', 'radio', 'button', "
        "'link', 'table', 'card', 'tab', 'modal', 'accordion', 'date_picker', 'file_upload'.\n"
        "Component library mapping is the downstream coding agent's job."
    ),
    discover_question_keys=[
        "frs_4a", "frs_5a", "frs_6a", "frs_6b", "frs_7a", "frs_8a",
    ],
    timeout_seconds=360,   # 6 min — gemini-2.5-flash CoT on a full FRS spec needs 3-5 min
)


FRS_MANIFEST: list[FrsUnitSpec] = [FRS_STAGE_A_UNIT, FRS_STAGE_B_UNIT]
FRS_MANIFEST_BY_KEY: dict[str, FrsUnitSpec] = {u.unit_key: u for u in FRS_MANIFEST}


# ── Table→model mapping (for upsert routing + queries) ────────────────────────

from app.models.frs import (
    FrsModule, FrsModuleActor, FrsModuleResponsibility,
    FrsModuleInterface, FrsModuleDataEntity,
    FrsSpec, FrsSpecDecision,
    FrsScreen, FrsUiComponent, FrsEndpoint, FrsDataEntity,
    FrsBusinessRule, FrsAcceptanceScenario, FrsFunctionalRequirement,
    FrsTraceability,
)

FRS_TABLE_MAP: dict[str, type] = {
    "frs_modules":                  FrsModule,
    "frs_module_actors":            FrsModuleActor,
    "frs_module_responsibilities":  FrsModuleResponsibility,
    "frs_module_interfaces":        FrsModuleInterface,
    "frs_module_data_entities":     FrsModuleDataEntity,
    "frs_specs":                    FrsSpec,
    "frs_spec_decisions":           FrsSpecDecision,
    # Stage B tables (not written in Stage A; registered for orchestrator reuse)
    "frs_screens":                  FrsScreen,
    "frs_ui_components":            FrsUiComponent,
    "frs_endpoints":                FrsEndpoint,
    "frs_data_entities":            FrsDataEntity,
    "frs_business_rules":           FrsBusinessRule,
    "frs_acceptance_scenarios":     FrsAcceptanceScenario,
    "frs_functional_requirements":  FrsFunctionalRequirement,
    # frs_traceability has bespoke handling (replace-all) — not in upsert path
}


# ── Per-table editable column whitelist (for versioned upsert) ────────────────
#
# Excludes versioning columns (id, document_id, row_key, version, is_current,
# is_locked, status, source, created_by, created_at). All other columns are
# editable / upsertable.

FRS_TYPED_COLS: dict[str, list[str]] = {
    "frs_modules": [
        "name", "slug", "layer", "scope_in", "scope_out", "summary",
        "figma_root_link", "completeness", "confidence",
    ],
    "frs_module_actors": [
        "module_row_key", "actor_name", "relationship", "notes",
    ],
    "frs_module_responsibilities": [
        "module_row_key", "responsibility", "frs_refs",
    ],
    "frs_module_interfaces": [
        "module_row_key", "interface_kind", "direction", "transport",
        "name", "counterpart", "user_role", "purpose", "frs_ref",
    ],
    "frs_module_data_entities": [
        "module_row_key", "entity_name", "business_purpose", "source_of_truth",
    ],
    "frs_specs": [
        "module_row_key", "title", "priority", "layer", "br_refs",
        "nfr_refs", "depends_on", "narrative", "independent_test",
        "data_and_validation", "errors_and_edge_cases", "observability",
        "implementation_tasks", "completeness", "confidence",
    ],
    "frs_spec_decisions": [
        "spec_row_key", "module_row_key", "question", "options",
        "recommended_index", "recommended_rationale",
        "user_chosen_index", "resolution_status",
    ],
    # Stage B columns (written by design_module unit)
    "frs_screens": [
        "spec_row_key", "screen_name", "figma_link", "purpose",
        "user_roles", "layout", "navigation", "interactive_behavior",
    ],
    "frs_ui_components": [
        "spec_row_key", "screen_row_key", "component_name", "component_type",
        "definition", "behavior", "validation", "actions", "data_mapping",
    ],
    "frs_endpoints": [
        "spec_row_key", "service_name", "endpoint_name", "url", "protocol",
        "method", "sync_async", "idempotent", "request_spec", "response_spec",
        "error_handling", "security", "operational", "integration_target",
    ],
    "frs_data_entities": [
        "spec_row_key", "entity_name", "data_store_type", "description",
        "expected_volume", "columns", "keys_constraints", "indexes",
        "relationships", "access_logic", "cache_spec", "retention_policy",
    ],
    "frs_business_rules": [
        "spec_row_key", "rule_id", "description", "applies_to", "logic_decision",
    ],
    "frs_acceptance_scenarios": [
        "spec_row_key", "scenario_index", "given", "when", "then",
        "is_negative", "fr_refs",
    ],
    "frs_functional_requirements": [
        "spec_row_key", "fr_id", "requirement_text", "scenario_refs",
    ],
}


# ── Integer-type columns (for type coercion on LLM string→int) ────────────────

FRS_INT_COLS: dict[str, set[str]] = {
    "frs_modules":              {"completeness"},
    "frs_specs":                {"completeness"},
    "frs_spec_decisions":       {"recommended_index", "user_chosen_index"},
    "frs_acceptance_scenarios": {"scenario_index"},
}
