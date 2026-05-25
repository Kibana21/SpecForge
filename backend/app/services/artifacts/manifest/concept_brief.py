"""Concept Brief generation manifest: unit DAG, instructions, discover questions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UnitSpec:
    unit_key: str
    writes: list[str]          # table names
    depends_on: list[str]      # unit_keys
    unit_instruction: str      # docstring / system prompt for the DSPy signature
    discover_questions: list[str]


MANIFEST: list[UnitSpec] = [
    UnitSpec(
        unit_key="problem_context",
        writes=["cb_text_blocks", "cb_context_map"],
        depends_on=[],
        unit_instruction=(
            "You are a senior Business Analyst writing the Problem Statement & Context Map for a "
            "Concept Brief. Ground every statement in the source documents [S#] and impacted "
            "applications [impacted_apps]. Write a clear Business Context paragraph and a concise "
            "Problem Statement paragraph. For the Context Map, produce exactly 6 rows using the "
            "fixed dimensions: business_unit, new_channel, customer_segments, current_gap, "
            "strategic_driver, engagement_goal. The current_gap, strategic_driver, and new_channel "
            "must reflect the impacted applications' documented capabilities and impact notes. "
            "Reproduce any locked rows verbatim. Keep existing row_keys stable; mint new ones only "
            "for new rows."
        ),
        discover_questions=[
            "What is the name of the initiative?",
            "What business problem does this solve?",
            "Which business unit owns this initiative?",
            "Who are the primary customer segments affected?",
            "What is the current gap or pain point this addresses?",
            "What strategic driver (OKR, regulation, market) is motivating this?",
        ],
    ),
    UnitSpec(
        unit_key="value_hypothesis",
        writes=["cb_text_blocks", "cb_outcomes"],
        depends_on=["problem_context"],
        unit_instruction=(
            "You are a senior Business Analyst writing the Value Hypothesis & Expected Outcomes "
            "section. Based on the problem context and source material, write a testable "
            "'If [action] then [measurable result] for [who]' hypothesis. List 3–6 concrete "
            "Expected Outcomes as rows. Ground outcomes in the impacted applications' capabilities "
            "and documented constraints. Keep existing row_keys stable."
        ),
        discover_questions=[
            "What value will this initiative deliver?",
            "What are the top 3–5 expected business outcomes?",
            "Who benefits most (internal teams, customers, partners)?",
        ],
    ),
    UnitSpec(
        unit_key="metrics",
        writes=["cb_metrics"],
        depends_on=["value_hypothesis"],
        unit_instruction=(
            "You are a senior Business Analyst writing the Success Metrics. Produce at least one "
            "quantifiable metric (quantifiable=true) with a specific numeric target. Ground metrics "
            "in the expected outcomes and any KPIs mentioned in the source documents or the "
            "impacted applications. Keep existing row_keys stable."
        ),
        discover_questions=[
            "What KPIs or metrics define success?",
            "Are there specific numeric targets (e.g., conversion rate, cost reduction)?",
        ],
    ),
    UnitSpec(
        unit_key="capabilities",
        writes=["cb_capabilities"],
        depends_on=["problem_context", "value_hypothesis"],
        unit_instruction=(
            "You are a senior Business Analyst listing Proposed Capabilities. Each capability "
            "should be solution-agnostic and traceable to a problem or outcome. Ground capabilities "
            "in the impacted applications' existing capabilities and constraints — call out "
            "where an app supports, enables, or limits a capability. Keep existing row_keys stable."
        ),
        discover_questions=[
            "What new capabilities does the business need?",
            "Are there existing system capabilities we can leverage?",
        ],
    ),
    UnitSpec(
        unit_key="scope",
        writes=["cb_scope_items"],
        depends_on=["capabilities", "value_hypothesis"],
        unit_instruction=(
            "You are a senior Business Analyst defining Scope Boundaries & Assumptions. Produce "
            "in_scope items (aligned to capabilities), out_of_scope items (explicit exclusions), "
            "and assumption items (dependencies, constraints). Reflect the impacted applications' "
            "documented limitations and integration constraints in the assumptions and out_of_scope "
            "lists. At least 1 of each kind. Keep existing row_keys stable."
        ),
        discover_questions=[
            "What is explicitly in scope?",
            "What is explicitly out of scope?",
            "What assumptions are you making about systems, data, or teams?",
        ],
    ),
    UnitSpec(
        unit_key="milestones",
        writes=["cb_milestones"],
        depends_on=["capabilities", "scope"],
        unit_instruction=(
            "You are a senior Business Analyst writing the Delivery Approach milestones. Produce "
            "a realistic milestone table with target dates or relative timeframes (e.g. Q3 2026, "
            "Month 2). Ground in the scope and impacted applications' integration complexity. "
            "Keep existing row_keys stable."
        ),
        discover_questions=[
            "What are the key delivery milestones?",
            "Is there a hard go-live date or phase approach?",
        ],
    ),
]

# Lookup by key
MANIFEST_BY_KEY: dict[str, UnitSpec] = {u.unit_key: u for u in MANIFEST}

# Topological order (dependencies first)
TOPO_ORDER = [u.unit_key for u in MANIFEST]


def downstream_of(unit_key: str) -> list[str]:
    """Return unit_keys that depend (directly or transitively) on unit_key."""
    result = []
    for spec in MANIFEST:
        if unit_key in spec.depends_on:
            result.append(spec.unit_key)
            result.extend(downstream_of(spec.unit_key))
    seen = set()
    deduped = []
    for k in result:
        if k not in seen:
            seen.add(k)
            deduped.append(k)
    return deduped


# Validation checklist (§7.1 of plan)
VALIDATION_CHECKS = [
    ("problem_statement_present",    "Problem statement must be present and non-trivial"),
    ("value_hypothesis_present",     "Value hypothesis (if/then) must be present and testable"),
    ("quantifiable_metric",          "At least one quantifiable metric required"),
    ("capability_present",           "At least one capability required"),
    ("in_scope_present",             "At least one in-scope item required"),
    ("out_of_scope_present",         "At least one out-of-scope item required"),
    ("assumption_present",           "At least one assumption required"),
    ("milestone_present",            "At least one milestone required"),
    ("clarity_pass",                 "All units must reach ≥90% completeness (clarity=Pass)"),
]
