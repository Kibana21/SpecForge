"""Fixed discovery question catalogs per artifact type.

Concept Brief: 14 questions (CB_DISCOVER_QUESTIONS, existing).
BRD: 18 questions (BRD_DISCOVER_QUESTIONS, new).

Both sets are scoped by artifact_document_id at the DB level — the same
CbDiscoverQuestion table serves both artifact types.
"""
from __future__ import annotations

from app.models.project import Project

DISCOVER_QUESTIONS: list[dict] = [
    {"key": "1a", "category": "initiative_context",
     "text": "What is the initiative name or working title?"},
    {"key": "1b", "category": "initiative_context",
     "text": "What business problem does this initiative solve?"},
    {"key": "1c", "category": "initiative_context",
     "text": "What is driving this initiative right now? (e.g. regulatory, competitive, cost, growth)"},
    {"key": "2a", "category": "business_context",
     "text": "Which business unit or department owns this initiative?"},
    {"key": "2b", "category": "business_context",
     "text": "Who are the primary customers or end users?"},
    {"key": "2c", "category": "business_context",
     "text": "What is the current situation (as-is) — what exists today that is insufficient?"},
    {"key": "3a", "category": "value_outcomes",
     "text": "What value does this initiative create if successful?"},
    {"key": "3b", "category": "value_outcomes",
     "text": "What outcomes would indicate success? (qualitative and quantitative)"},
    {"key": "3c", "category": "value_outcomes",
     "text": "Are there any initial success metrics or KPIs in mind?"},
    {"key": "4a", "category": "scope_assumptions",
     "text": "What capabilities or features are expected to be in scope?"},
    {"key": "4b", "category": "scope_assumptions",
     "text": "What is explicitly out of scope or deferred to a later phase?"},
    {"key": "4c", "category": "scope_assumptions",
     "text": "What assumptions is the business making at this stage?"},
    {"key": "5a", "category": "delivery",
     "text": "Are there any known milestones, deadlines, or delivery constraints?"},
    {"key": "5b", "category": "delivery",
     "text": "Is there an MVP or phased delivery approach in mind?"},
]

# Keys answered directly from project fields (no LLM needed)
PROJECT_PREFILL: dict[str, "Callable[[Project], str]"] = {  # type: ignore[name-defined]
    "1a": lambda p: p.name or "",
    "2a": lambda p: p.business_unit or "",
}

# Questions analysed by LLM (all except direct prefills)
LLM_ANALYSIS_KEYS: list[str] = [
    q["key"] for q in DISCOVER_QUESTIONS if q["key"] not in PROJECT_PREFILL
]

# Maps each DSPy generation unit to the question keys that feed it
UNIT_DISCOVER_MAP: dict[str, list[str]] = {
    "problem_context":  ["1a", "1b", "1c", "2a", "2b", "2c"],
    "value_hypothesis": ["3a", "3b"],
    "metrics":          ["3c"],
    "capabilities":     ["4a"],
    "scope":            ["4b", "4c"],
    "milestones":       ["5a", "5b"],
}

# Ordered keys for seq assignment
QUESTION_KEYS: list[str] = [q["key"] for q in DISCOVER_QUESTIONS]
QUESTION_BY_KEY: dict[str, dict] = {q["key"]: q for q in DISCOVER_QUESTIONS}

# ── BRD Discover catalog (18 questions, 7 categories) ─────────────────────────

BRD_DISCOVER_QUESTIONS: list[dict] = [
    # 🎯 Initiative
    {"key": "brd_1a", "category": "initiative",
     "text": "What is the full initiative name and business sponsor?"},
    {"key": "brd_1b", "category": "initiative",
     "text": "What strategic objective does this initiative serve (e.g. cost reduction, revenue growth, compliance)?"},
    {"key": "brd_1c", "category": "initiative",
     "text": "What is the target go-live date or must-meet regulatory deadline?"},
    # 📊 Objectives
    {"key": "brd_2a", "category": "objectives",
     "text": "What are the top 3–5 measurable business objectives this BRD must achieve?"},
    {"key": "brd_2b", "category": "objectives",
     "text": "Who owns each objective — which business leader is accountable?"},
    # 👥 Stakeholders
    {"key": "brd_3a", "category": "stakeholders",
     "text": "Who are the primary business stakeholders and what is their level of influence?"},
    {"key": "brd_3b", "category": "stakeholders",
     "text": "Which operations or compliance teams must be engaged for sign-off?"},
    # 🔄 Processes
    {"key": "brd_4a", "category": "processes",
     "text": "Walk me through the current (as-is) process step by step. Where are the biggest pain points?"},
    {"key": "brd_4b", "category": "processes",
     "text": "What does the ideal (to-be) process look like? Which steps should be automated or eliminated?"},
    # 📦 Scope
    {"key": "brd_5a", "category": "scope",
     "text": "What capabilities or features are definitively in scope for this initiative?"},
    {"key": "brd_5b", "category": "scope",
     "text": "What is explicitly out of scope? What might seem related but is excluded from this initiative?"},
    {"key": "brd_5c", "category": "scope",
     "text": "What assumptions underpin the scope — about systems, teams, data, or timelines?"},
    # ⚠ Risks
    {"key": "brd_6a", "category": "risks",
     "text": "What are the top 3 risks that could prevent this initiative from succeeding?"},
    {"key": "brd_6b", "category": "risks",
     "text": "What mitigation strategies are already in place or planned for these risks?"},
    # 🚀 Delivery
    {"key": "brd_7a", "category": "delivery",
     "text": "Is a phased delivery approach planned — what does Phase 1 (MVP) include?"},
    {"key": "brd_7b", "category": "delivery",
     "text": "What are the key delivery milestones and who is responsible for each?"},
    # 📈 KPIs
    {"key": "brd_8a", "category": "kpis",
     "text": "What KPIs will measure success — and what are the current baseline values?"},
    {"key": "brd_8b", "category": "kpis",
     "text": "What are the specific targets and timeframes for each KPI?"},
]

BRD_PROJECT_PREFILL: dict[str, "Callable[[Project], str]"] = {  # type: ignore[name-defined]
    "brd_1a": lambda p: p.name or "",
}

BRD_LLM_ANALYSIS_KEYS: list[str] = [
    q["key"] for q in BRD_DISCOVER_QUESTIONS if q["key"] not in BRD_PROJECT_PREFILL
]

BRD_UNIT_DISCOVER_MAP: dict[str, list[str]] = {
    "business_context":      ["brd_1a", "brd_1b"],
    "problem_statement":     ["brd_1b", "brd_4a"],
    "objectives":            ["brd_2a", "brd_2b"],
    "stakeholders":          ["brd_3a", "brd_3b"],
    "actors":                ["brd_3a"],
    "scope":                 ["brd_5a", "brd_5b", "brd_5c"],
    "asis_process":          ["brd_4a"],
    "tobe_process":          ["brd_4b"],
    "business_requirements": ["brd_5a", "brd_5b"],
    "data_entities":         [],
    "report_requirements":   ["brd_8a"],
    "assumptions":           ["brd_5c"],
    "constraints":           ["brd_5c"],
    "dependencies":          ["brd_7a", "brd_7b"],
    "risks":                 ["brd_6a", "brd_6b"],
    "implementation_phases": ["brd_7a", "brd_7b"],
    "milestones":            ["brd_7b", "brd_1c"],
    "kpis":                  ["brd_8a", "brd_8b"],
    "open_questions":        [],
    "decisions":             [],
    "references":            [],
    "glossary":              [],
}

BRD_QUESTION_KEYS: list[str] = [q["key"] for q in BRD_DISCOVER_QUESTIONS]
BRD_QUESTION_BY_KEY: dict[str, dict] = {q["key"]: q for q in BRD_DISCOVER_QUESTIONS}

# ── Routing helper ─────────────────────────────────────────────────────────────

def get_catalog_for_artifact(artifact_type: str) -> tuple[list[dict], dict, list[str]]:
    """Return (questions, prefill_map, llm_analysis_keys) for the given artifact type."""
    if artifact_type == "brd":
        return BRD_DISCOVER_QUESTIONS, BRD_PROJECT_PREFILL, BRD_LLM_ANALYSIS_KEYS
    return DISCOVER_QUESTIONS, PROJECT_PREFILL, LLM_ANALYSIS_KEYS
