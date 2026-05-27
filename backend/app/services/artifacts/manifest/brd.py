"""BRD generation manifest: 22 units, dependency DAG, discover catalog, validation checks."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BrdUnitSpec:
    unit_key: str
    writes: list[str]           # BRD table names this unit owns
    depends_on: list[str]       # unit_keys that must run first
    unit_instruction: str       # docstring for DSPy signature
    discover_questions: list[str]


# ── The 22-unit manifest ──────────────────────────────────────────────────────

BRD_MANIFEST: list[BrdUnitSpec] = [

    BrdUnitSpec(
        unit_key="business_context",
        writes=["brd_text_blocks"],
        depends_on=[],
        unit_instruction=(
            "You are a senior Business Analyst writing §1 Business Context for a BRD. "
            "Draw on the validated Concept Brief's business_context and context_map, the "
            "App Brain grounding, and project document sections to write a rich, factual "
            "business context narrative. Cover: industry/regulatory backdrop, strategic "
            "imperatives, the owning business unit, and how in-scope apps sit in the "
            "ecosystem. Keep existing row_keys stable."
        ),
        discover_questions=[
            "What is the business context and industry backdrop for this initiative?",
            "Which regulatory or strategic drivers are creating urgency?",
        ],
    ),

    BrdUnitSpec(
        unit_key="problem_statement",
        writes=["brd_text_blocks"],
        depends_on=["business_context"],
        unit_instruction=(
            "You are a senior Business Analyst writing §2 Problem Statement for a BRD. "
            "Write a crisp, specific problem statement with root causes enumerated. "
            "Ground in the CB's problem_statement, App Brain pain points, and document "
            "evidence [S#]. Distinguish symptom from root cause. Keep row_keys stable."
        ),
        discover_questions=[
            "What is the specific problem this BRD addresses?",
            "What are the identified root causes?",
        ],
    ),

    BrdUnitSpec(
        unit_key="objectives",
        writes=["brd_objectives"],
        depends_on=["problem_statement"],
        unit_instruction=(
            "You are a senior Business Analyst writing §3 Strategic Objectives for a BRD. "
            "Derive 3–7 SMART objectives from the CB outcomes and value hypothesis. Each "
            "objective must trace to a CB outcome (cb_outcome_ref). Assign priority "
            "(must/should/could/wont) reflecting the CB's value tier. Name an owner per "
            "objective. Keep row_keys stable (OBJ-001 format)."
        ),
        discover_questions=[
            "What are the top strategic objectives this BRD must satisfy?",
            "Who owns each objective?",
        ],
    ),

    BrdUnitSpec(
        unit_key="stakeholders",
        writes=["brd_stakeholders"],
        depends_on=["objectives"],
        unit_instruction=(
            "You are a senior Business Analyst writing §4a Stakeholders for a BRD. "
            "Identify all stakeholder groups (sponsor, owner, user, operations, compliance, "
            "technical, external) grounded in the CB context_map customer_segments and "
            "App Brain. For each: name, type, role in this initiative, primary interest, "
            "and influence level (high/medium/low). Keep row_keys stable (STK-001 format)."
        ),
        discover_questions=[
            "Who are the key stakeholders for this initiative?",
            "What is each stakeholder's primary interest and influence?",
        ],
    ),

    BrdUnitSpec(
        unit_key="actors",
        writes=["brd_actors"],
        depends_on=["stakeholders"],
        unit_instruction=(
            "You are a senior Business Analyst writing §4b System Actors for a BRD. "
            "List every human role and system that interacts with the solution. Ground in "
            "App Brain capabilities — call out systems by app name where applicable. "
            "For each actor: name, type (human/system), description, and key interactions. "
            "Keep row_keys stable (ACT-001 format)."
        ),
        discover_questions=[
            "Which human roles and systems interact with this solution?",
        ],
    ),

    BrdUnitSpec(
        unit_key="scope",
        writes=["brd_scope_items"],
        depends_on=["objectives", "stakeholders"],
        unit_instruction=(
            "You are a senior Business Analyst writing §5 Scope for a BRD. "
            "Produce three groups: in_scope (features/capabilities included), out_of_scope "
            "(explicit exclusions with rationale), and assumption (dependencies the solution "
            "assumes). Ground in CB scope_items and capabilities. Ref CB rows via cb_scope_ref. "
            "At least 2 of each kind. Keep row_keys stable (SCP-IN-001, SCP-OUT-001, SCP-ASM-001 format)."
        ),
        discover_questions=[
            "What is explicitly in scope for this initiative?",
            "What is explicitly out of scope?",
            "What assumptions underpin the scope?",
        ],
    ),

    BrdUnitSpec(
        unit_key="asis_process",
        writes=["brd_process_steps"],
        depends_on=["scope", "stakeholders"],
        unit_instruction=(
            "You are a senior Business Analyst documenting §6a As-Is Process for a BRD. "
            "Map the current-state workflow step by step. For each step: sequential step_number, "
            "the actor performing it, the action taken, and the pain_point or inefficiency. "
            "Ground in document sections [S#] and App Brain operational facts. "
            "All steps must have step_type='asis'. Keep row_keys stable (ASIS-001 format)."
        ),
        discover_questions=[
            "How does the current process work, step by step?",
            "Where are the biggest pain points in the current process?",
        ],
    ),

    BrdUnitSpec(
        unit_key="tobe_process",
        writes=["brd_process_steps"],
        depends_on=["asis_process", "scope"],
        unit_instruction=(
            "You are a senior Business Analyst documenting §6b To-Be Process for a BRD. "
            "Map the future-state workflow that the solution will enable. For each step: "
            "sequential step_number, the actor, the action, and the improvement vs as-is. "
            "Ground in CB capabilities and App Brain integration facts. "
            "All steps must have step_type='tobe'. Keep row_keys stable (TOBE-001 format)."
        ),
        discover_questions=[
            "How will the process work after this solution is implemented?",
        ],
    ),

    BrdUnitSpec(
        unit_key="business_requirements",
        writes=["brd_business_requirements"],
        depends_on=["objectives", "scope", "asis_process", "tobe_process", "stakeholders"],
        unit_instruction=(
            "You are a senior Business Analyst writing §7 Business Requirements — the "
            "keystone section of the BRD. For each BR: title, description, MoSCoW priority "
            "(must/should/could/wont), category (functional/non_functional/data/integration/"
            "reporting/compliance/operational), 2–4 Given-When-Then acceptance criteria, "
            "objective_refs (row_keys of brd_objectives it satisfies), stakeholder_refs "
            "(row_keys of brd_stakeholders impacted), and rationale grounded in CB/App Brain. "
            "Every must-have BR must have ≥2 acceptance criteria. BRs must collectively cover "
            "every in-scope item and every CB capability. Keep row_keys stable (BR-001 format)."
        ),
        discover_questions=[
            "What are the must-have business requirements for this initiative?",
            "What acceptance criteria prove each requirement is met?",
        ],
    ),

    BrdUnitSpec(
        unit_key="data_entities",
        writes=["brd_data_entities"],
        depends_on=["business_requirements", "scope"],
        unit_instruction=(
            "You are a senior Business Analyst writing §8a Data Entities for a BRD. "
            "Identify all key data entities the solution creates, consumes, or transforms. "
            "For each: entity_name, description, owner_system (from App Brain), data_sensitivity "
            "(standard/confidential/restricted), and key_attributes (list of attribute names). "
            "Ground in App Brain integration facts and document sections. Keep row_keys stable (DE-001)."
        ),
        discover_questions=[
            "What are the key data entities this solution manages?",
        ],
    ),

    BrdUnitSpec(
        unit_key="report_requirements",
        writes=["brd_report_requirements"],
        depends_on=["business_requirements", "kpis"],
        unit_instruction=(
            "You are a senior Business Analyst writing §8b Reporting Requirements for a BRD. "
            "Identify all reports/dashboards the solution must produce. For each: report_name, "
            "description, audience (stakeholder role), frequency (real-time/daily/weekly/monthly), "
            "and key_metrics (list of metric names). Ground in KPIs and CB metrics. Keep row_keys (RR-001)."
        ),
        discover_questions=[
            "What reports or dashboards must the solution produce?",
        ],
    ),

    BrdUnitSpec(
        unit_key="assumptions",
        writes=["brd_assumptions"],
        depends_on=["scope", "business_requirements"],
        unit_instruction=(
            "You are a senior Business Analyst writing §9a Assumptions for a BRD. "
            "Document every assumption the initiative makes about the environment, systems, "
            "or teams. For each: the assumption, impact_if_wrong, and owner who can validate. "
            "Trace CB scope_items of kind='assumption' via cb_scope_ref. Keep row_keys (ASM-001)."
        ),
        discover_questions=[
            "What assumptions does this initiative depend on?",
        ],
    ),

    BrdUnitSpec(
        unit_key="constraints",
        writes=["brd_constraints"],
        depends_on=["scope", "business_requirements"],
        unit_instruction=(
            "You are a senior Business Analyst writing §9b Constraints for a BRD. "
            "Document all non-negotiable constraints: regulatory, technical, timeline, budget, "
            "or organisational. For each: constraint_text, constraint_type, and source_ref "
            "(document section or app fact). Keep row_keys stable (CON-001 format)."
        ),
        discover_questions=[
            "What constraints must the solution operate within?",
        ],
    ),

    BrdUnitSpec(
        unit_key="dependencies",
        writes=["brd_dependencies"],
        depends_on=["scope", "business_requirements"],
        unit_instruction=(
            "You are a senior Business Analyst writing §9c External Dependencies for a BRD. "
            "List every external team, system, or vendor the initiative depends on. "
            "For each: dependency description, type (external/internal/vendor/regulatory), "
            "owner, and due_date or timeframe. Ground in App Brain integration facts. Keep row_keys (DEP-001)."
        ),
        discover_questions=[
            "What external dependencies must be resolved for delivery?",
        ],
    ),

    BrdUnitSpec(
        unit_key="risks",
        writes=["brd_risks"],
        depends_on=["scope", "assumptions", "constraints", "dependencies"],
        unit_instruction=(
            "You are a senior Business Analyst writing §10 Risks & Issues for a BRD. "
            "Identify all business, delivery, and operational risks. For each: risk description, "
            "severity (critical/high/medium/low), likelihood (high/medium/low), mitigation "
            "strategy, and owner. Ground in App Brain gotchas, CB out_of_scope, and doc evidence. "
            "Every risk must have a non-empty mitigation. Keep row_keys (RSK-001 format)."
        ),
        discover_questions=[
            "What are the top delivery and business risks?",
            "What mitigation plans exist for critical risks?",
        ],
    ),

    BrdUnitSpec(
        unit_key="implementation_phases",
        writes=["brd_phases"],
        depends_on=["business_requirements", "risks"],
        unit_instruction=(
            "You are a senior Business Analyst writing §11a Implementation Phases for a BRD. "
            "Group BRs into logical delivery phases (MVP → Phase 2 → Phase 3, etc.). "
            "For each phase: phase_name, description, target_date or timeframe, and "
            "included_br_refs (list of BR row_keys). Ground in CB milestones and stakeholder "
            "priorities. Keep row_keys (PH-001 format)."
        ),
        discover_questions=[
            "How will implementation be phased?",
        ],
    ),

    BrdUnitSpec(
        unit_key="milestones",
        writes=["brd_milestones"],
        depends_on=["implementation_phases"],
        unit_instruction=(
            "You are a senior Business Analyst writing §11b Milestones for a BRD. "
            "Derive a milestone table from the delivery phases and CB milestones. "
            "For each: milestone name, target date/timeframe, description, phase_ref "
            "(row_key of brd_phases), and cb_milestone_ref (CB row_key if applicable). "
            "Keep row_keys stable (MS-001 format)."
        ),
        discover_questions=[
            "What are the key delivery milestones and dates?",
        ],
    ),

    BrdUnitSpec(
        unit_key="kpis",
        writes=["brd_kpis"],
        depends_on=["objectives", "business_requirements"],
        unit_instruction=(
            "You are a senior Business Analyst writing §12 KPIs for a BRD. "
            "For every objective and CB metric, derive a KPI with: kpi_name, description, "
            "baseline (current state value or 'TBD'), target (specific numeric target), "
            "timeframe (e.g. 'Q3 2026' or '6 months post go-live'), data_source (which "
            "app or report provides this), objective_ref (brd_objectives row_key), and "
            "cb_metric_ref (CB row_key). Every KPI must have a non-empty target. Keep row_keys (KPI-001)."
        ),
        discover_questions=[
            "What KPIs will measure success for each objective?",
            "What are the baseline and target values for each KPI?",
        ],
    ),

    BrdUnitSpec(
        unit_key="open_questions",
        writes=["brd_open_questions"],
        depends_on=["business_requirements", "risks", "dependencies"],
        unit_instruction=(
            "You are a senior Business Analyst writing §13a Open Questions for a BRD. "
            "List unresolved questions that must be answered before or during delivery. "
            "For each: question, context (why it's unresolved), owner (who can answer), "
            "and due_date (when it must be resolved). Ground in discover Q&A gaps and "
            "risks. Keep row_keys stable (OQ-001 format)."
        ),
        discover_questions=[
            "What questions remain unresolved that could impact delivery?",
        ],
    ),

    BrdUnitSpec(
        unit_key="decisions",
        writes=["brd_decisions"],
        depends_on=["scope", "business_requirements"],
        unit_instruction=(
            "You are a senior Business Analyst writing §13b Key Decisions for a BRD. "
            "Document decisions already made that shaped this BRD. For each: decision "
            "statement, rationale (why this choice), owner, decision_date (when decided), "
            "and alternatives_considered (what was rejected and why). Ground in discover "
            "Q&A and CB scope. Keep row_keys stable (DEC-001 format)."
        ),
        discover_questions=[
            "What key decisions have already been made for this initiative?",
        ],
    ),

    BrdUnitSpec(
        unit_key="references",
        writes=["brd_references"],
        depends_on=["business_context"],
        unit_instruction=(
            "You are a senior Business Analyst writing §14a References for a BRD. "
            "List all source documents, standards, and artefacts referenced. For each: "
            "title, reference_type (document/standard/regulation/system), location "
            "(doc filename or URL placeholder), and a short description. Ground in the "
            "document inventory provided. Keep row_keys stable (REF-001 format)."
        ),
        discover_questions=[],
    ),

    BrdUnitSpec(
        unit_key="glossary",
        writes=["brd_glossary_entries"],
        depends_on=["business_context", "business_requirements"],
        unit_instruction=(
            "You are a senior Business Analyst writing §14b Glossary for a BRD. "
            "Define all acronyms, domain terms, and jargon used in the document. "
            "For each: term, definition (clear and non-circular), and source_ref "
            "(which doc or app uses it). Ground in App Brain and document sections. "
            "Keep row_keys stable (GLO-001 format)."
        ),
        discover_questions=[],
    ),
]


# ── Lookup structures ─────────────────────────────────────────────────────────

BRD_MANIFEST_BY_KEY: dict[str, BrdUnitSpec] = {u.unit_key: u for u in BRD_MANIFEST}


def _build_topo_order() -> list[str]:
    """Kahn's algorithm topological sort over the dependency DAG."""
    in_degree: dict[str, int] = {u.unit_key: 0 for u in BRD_MANIFEST}
    dependents: dict[str, list[str]] = {u.unit_key: [] for u in BRD_MANIFEST}
    for spec in BRD_MANIFEST:
        for dep in spec.depends_on:
            in_degree[spec.unit_key] += 1
            dependents[dep].append(spec.unit_key)

    queue = [k for k, d in in_degree.items() if d == 0]
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for child in dependents[node]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
    return order


BRD_TOPO_ORDER: list[str] = _build_topo_order()


def brd_downstream_of(unit_key: str) -> list[str]:
    """Return unit_keys that depend (directly or transitively) on unit_key."""
    result: list[str] = []
    for spec in BRD_MANIFEST:
        if unit_key in spec.depends_on:
            result.append(spec.unit_key)
            result.extend(brd_downstream_of(spec.unit_key))
    seen: set[str] = set()
    deduped: list[str] = []
    for k in result:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


# ── Table→unit mapping (for upsert_rows routing) ─────────────────────────────

BRD_TABLE_TO_UNIT: dict[str, str] = {}
for _spec in BRD_MANIFEST:
    for _tbl in _spec.writes:
        if _tbl not in BRD_TABLE_TO_UNIT:  # first writer wins
            BRD_TABLE_TO_UNIT[_tbl] = _spec.unit_key

# For process steps two units write to the same table — keyed by step_type scope
BRD_PROCESS_STEP_UNIT_MAP: dict[str, str] = {
    "asis": "asis_process",
    "tobe": "tobe_process",
}

# ── Per-unit discover question mapping (for filtering discover context) ────────

BRD_UNIT_DISCOVER_MAP: dict[str, list[str]] = {
    # BRD discover question keys (brd_1a, brd_1b, …) mapped in discover_catalog.py
    "business_context":      ["brd_2a", "brd_2b"],
    "problem_statement":     ["brd_2c", "brd_2d"],
    "objectives":            ["brd_3a", "brd_3b"],
    "stakeholders":          ["brd_4a", "brd_4b"],
    "actors":                ["brd_4c"],
    "scope":                 ["brd_5a", "brd_5b", "brd_5c"],
    "asis_process":          ["brd_6a", "brd_6b"],
    "tobe_process":          ["brd_6c"],
    "business_requirements": ["brd_7a", "brd_7b"],
    "data_entities":         ["brd_8a"],
    "report_requirements":   ["brd_8b"],
    "assumptions":           ["brd_5c", "brd_9a"],
    "constraints":           ["brd_9b"],
    "dependencies":          ["brd_9c"],
    "risks":                 ["brd_10a", "brd_10b"],
    "implementation_phases": ["brd_11a"],
    "milestones":            ["brd_11b"],
    "kpis":                  ["brd_12a", "brd_12b"],
    "open_questions":        [],
    "decisions":             [],
    "references":            [],
    "glossary":              [],
}

# ── BRD validation checks ─────────────────────────────────────────────────────

BRD_VALIDATION_CHECKS = [
    # (check_id, description, group)
    ("required_sections",        "All 22 generation units must have rows", "critical"),
    ("br_must_have_ac",          "Every 'must' BR requires ≥2 Given-When-Then acceptance criteria", "major"),
    ("br_objective_ref",         "Every BR must reference ≥1 brd_objectives row_key", "major"),
    ("br_stakeholder_ref",       "Every BR must reference ≥1 brd_stakeholders row_key", "major"),
    ("kpi_baseline_target",      "Every KPI must have a non-empty baseline and target", "major"),
    ("kpi_timeframe",            "Every KPI must have a non-empty timeframe", "major"),
    ("risk_mitigation",          "Every risk must have a non-empty mitigation", "major"),
    ("outward_traceability",     "Every BR, KPI, objective, and risk must have ≥1 brd_traceability row", "major"),
    ("unit_completeness",        "All units must reach ≥90% completeness (AI-scored)", "minor"),
    ("cb_coverage",              "All CB elements in BRD_CONTEXT_PROJECTION must be consumed", "coverage"),
    ("orphan_traces",            "No brd_traceability row may reference a source that no longer exists", "coverage"),
]
