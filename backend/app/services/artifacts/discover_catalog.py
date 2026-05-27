"""Fixed catalog of 14 discovery questions and their mappings."""
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
