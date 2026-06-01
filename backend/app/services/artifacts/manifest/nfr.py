"""NFR generation manifest — 9 single-phase units (overview → 7 categories → governance).

Mirrors manifest/brd.py: a UnitSpec dataclass + the unit list + TOPO order. The
NFR engine is single-phase (no FRS A/B); the 7 category units write the shared
nfr_requirements table scoped by category, governance writes the 6 governance
tables, overview writes nfr_text_blocks.

Table/column maps live in nfr_orchestrator.py (like brd_orchestrator.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NfrUnitSpec:
    unit_key: str
    label: str
    writes: list[str]                       # NFR table names this unit owns
    depends_on: list[str]                   # unit_keys that must run first
    unit_instruction: str                   # guidance surfaced to the DSPy signature
    discover_question_keys: list[str] = field(default_factory=list)
    timeout_seconds: int = 90


# The 7 quality categories (NfrCategory enum values), in elicitation order.
NFR_CATEGORY_UNITS: list[str] = [
    "performance", "security", "availability", "usability",
    "scalability", "maintainability", "portability",
]

_CATEGORY_LABELS: dict[str, str] = {
    "performance": "Performance & Efficiency",
    "security": "Security & Compliance",
    "availability": "Availability, Reliability & Resilience",
    "usability": "Usability",
    "scalability": "Scalability & Capacity",
    "maintainability": "Maintainability & Supportability",
    "portability": "Portability & Compatibility",
}

_CATEGORY_FOCUS: dict[str, str] = {
    "performance": "latency, throughput, and response-time budgets (state metric + threshold, e.g. 'p95 API latency < 300ms @ 200 concurrent users')",
    "security": "confidentiality, integrity, auditability, and legal/regulatory obligations",
    "availability": "uptime targets, failure tolerance, recovery (RTO/RPO) and SLA assumptions",
    "usability": "accessibility standards (e.g. WCAG), UX quality, and internationalisation",
    "scalability": "expected and peak load, data-volume growth, and capacity headroom",
    "maintainability": "support model, observability, and change/patch effort expectations",
    "portability": "environment targets, interoperability boundaries, and browser/platform compatibility",
}

_CATEGORY_QUESTION_KEYS: dict[str, list[str]] = {
    "performance": ["nfr_perf_latency", "nfr_perf_throughput", "nfr_perf_budget"],
    "security": ["nfr_sec_confidentiality", "nfr_sec_integrity", "nfr_sec_compliance", "nfr_sec_audit"],
    "availability": ["nfr_avail_uptime", "nfr_avail_failure", "nfr_avail_rto_rpo"],
    "usability": ["nfr_use_accessibility", "nfr_use_ux", "nfr_use_i18n"],
    "scalability": ["nfr_scale_peak", "nfr_scale_growth", "nfr_scale_data"],
    "maintainability": ["nfr_maint_support", "nfr_maint_observability", "nfr_maint_change"],
    "portability": ["nfr_port_env", "nfr_port_interop", "nfr_port_browser"],
}


def _category_instruction(cat: str) -> str:
    return (
        f"You are a senior architect authoring the {_CATEGORY_LABELS[cat]} non-functional "
        f"requirements (NFR template). Focus on {_CATEGORY_FOCUS[cat]}.\n\n"
        "Derive testable, SOLUTION-AGNOSTIC quality requirements from the validated BRD "
        "objectives, KPIs and constraints, the Concept Brief, and any ad-hoc requirements in "
        "the brief. Hard rules:\n"
        "  • Every requirement MUST be measurable — put the metric + threshold in `measurement`.\n"
        "  • Every requirement MUST NOT prescribe a technology/product ('use Redis' is forbidden).\n"
        "  • Every requirement MUST carry a MoSCoW `priority` (must/should/could/wont).\n"
        "  • Continue the GLOBAL NFR-nnn numbering from current_nfrs; never renumber or alter "
        "locked_nfrs — reproduce them verbatim.\n"
        "  • Emit a traceability row for every requirement linking it to ≥1 BRD objective "
        "(target_kind='brd_objective') or business requirement (target_kind='brd_business_requirement') "
        "via brd_refs AND the traceability list.\n"
        f"  • Set category='{cat}' on every requirement row.\n"
        "  • If this category is genuinely not applicable to the initiative, emit ONE row with "
        "na=true and a one-line rationale.\n"
        "Produce ≤8 requirements; merge overlaps. For every open_question populate `example` "
        "with a concrete sample answer."
    )


OVERVIEW_UNIT = NfrUnitSpec(
    unit_key="overview",
    label="Context & objectives",
    writes=["nfr_text_blocks"],
    depends_on=[],
    unit_instruction=(
        "Write the NFR document's Context overview and three Objectives, grounded in the "
        "validated BRD + Concept Brief + any ad-hoc brief. The overview (1–2 paragraphs) frames "
        "the initiative's quality posture and system boundary; the objectives are three crisp "
        "quality goals. Emit two text blocks: row_key 'NFR-TB-overview' (block_kind='overview') "
        "and row_key 'NFR-TB-objectives' (block_kind='objectives')."
    ),
    discover_question_keys=["nfr_ctx_initiative", "nfr_ctx_boundary", "nfr_ctx_goals"],
)

GOVERNANCE_UNIT = NfrUnitSpec(
    unit_key="governance",
    label="Risks, trade-offs & governance",
    writes=[
        "nfr_risks", "nfr_tradeoffs", "nfr_open_questions",
        "nfr_decisions", "nfr_references", "nfr_glossary",
    ],
    depends_on=list(NFR_CATEGORY_UNITS),
    unit_instruction=(
        "Author the governance sections for the NFR document, informed by the requirements "
        "already produced across all seven categories (provided as upstream). Produce: NFR risks "
        "(row_key NFR-R-nnn) with impact/likelihood/mitigation/owner; trade-off decisions "
        "(NFR-TD-nnn); open questions (NFR-OQ-nnn); pending decisions (NFR-PD-nnn); references "
        "(NFR-REF-nnn); and a glossary (NFR-G-nnn). Keep entries concise and only include rows "
        "that add real governance value. For every open_question populate `example`."
    ),
    discover_question_keys=["nfr_risk_top", "nfr_risk_tradeoff"],
)


def _category_unit(cat: str) -> NfrUnitSpec:
    return NfrUnitSpec(
        unit_key=cat,
        label=_CATEGORY_LABELS[cat],
        writes=["nfr_requirements"],
        depends_on=["overview"],
        unit_instruction=_category_instruction(cat),
        discover_question_keys=_CATEGORY_QUESTION_KEYS[cat],
    )


NFR_MANIFEST: list[NfrUnitSpec] = (
    [OVERVIEW_UNIT]
    + [_category_unit(c) for c in NFR_CATEGORY_UNITS]
    + [GOVERNANCE_UNIT]
)
NFR_MANIFEST_BY_KEY: dict[str, NfrUnitSpec] = {u.unit_key: u for u in NFR_MANIFEST}
NFR_TOPO_ORDER: list[str] = [u.unit_key for u in NFR_MANIFEST]
