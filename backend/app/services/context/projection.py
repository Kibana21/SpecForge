"""Per-unit context projection: narrow the full bundle to what each unit needs."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.context.project_context import ProjectContextBundle


@dataclass
class UnitContext:
    """Projected context ready for injection into a DSPy unit prompt."""
    app_brain: str
    doc_sections: str           # from depth_search() — caller provides this
    cb_context: str
    brd_context: str            # populated for artifact_type in ('frs','test_cases')
    discover_qa: str
    combined: str               # convenience: all layers concatenated
    frs_context: str = ""       # populated for artifact_type='test_cases'
    nfr_context: str = ""       # validated NFR drivers (soft) for frs/test_cases


# Per-unit CB element inclusion map: which CB tables to project for each BRD unit
_UNIT_CB_ELEMENTS: dict[str, list[str]] = {
    "business_context":      ["text_blocks", "context_map", "discover_qa"],
    "problem_statement":     ["text_blocks", "context_map", "discover_qa"],
    "objectives":            ["text_blocks", "outcomes", "metrics", "discover_qa"],
    "stakeholders":          ["text_blocks", "context_map", "scope_items", "discover_qa"],
    "actors":                ["text_blocks", "context_map", "discover_qa"],
    "scope":                 ["capabilities", "scope_items", "discover_qa"],
    "asis_process":          ["text_blocks", "context_map", "scope_items", "discover_qa"],
    "tobe_process":          ["capabilities", "scope_items", "discover_qa"],
    "business_requirements": ["text_blocks", "outcomes", "metrics", "capabilities", "scope_items", "discover_qa"],
    "data_entities":         ["capabilities", "scope_items", "discover_qa"],
    "report_requirements":   ["metrics", "outcomes", "discover_qa"],
    "assumptions":           ["scope_items", "context_map", "discover_qa"],
    "constraints":           ["scope_items", "context_map", "discover_qa"],
    "dependencies":          ["context_map", "scope_items", "discover_qa"],
    "risks":                 ["scope_items", "context_map", "discover_qa"],
    "implementation_phases": ["milestones", "scope_items", "discover_qa"],
    "milestones":            ["milestones", "discover_qa"],
    "kpis":                  ["outcomes", "metrics", "discover_qa"],
    "open_questions":        ["text_blocks", "discover_qa"],
    "decisions":             ["text_blocks", "scope_items", "discover_qa"],
    "references":            ["text_blocks", "discover_qa"],
    "glossary":              ["text_blocks", "context_map", "discover_qa"],
}


def project_for_unit(
    bundle: ProjectContextBundle,
    artifact_type: str,
    unit_key: str,
    *,
    doc_sections: str = "",
) -> UnitContext:
    """Project the bundle to the subset relevant for this generation unit.

    doc_sections should be passed in from a preceding depth_search() call.
    """
    brd_context = ""
    if artifact_type == "brd":
        elements = _UNIT_CB_ELEMENTS.get(unit_key, ["text_blocks", "discover_qa"])
        cb_context = _project_cb(bundle.cb, elements)
    elif artifact_type == "frs":
        # FRS modularize grounds on the entire CB + entire BRD (full corpus rule).
        cb_context = bundle.cb.formatted_context
        brd_context = bundle.brd.formatted_context if bundle.brd else "(no BRD)"
    elif artifact_type == "test_cases":
        # Test-case generation grounds on the entire FRS + BRD + CB (full corpus
        # rule). The FRS is the keystone; BRD provides outcome framing for the
        # transitive must-BR rollup. frs_context lands in the combined block via
        # the dedicated FRS section appended below.
        cb_context = bundle.cb.formatted_context
        brd_context = bundle.brd.formatted_context if bundle.brd else "(no BRD)"
    elif artifact_type == "nfr":
        # NFR grounds on the entire CB + entire BRD (same corpus as FRS).
        cb_context = bundle.cb.formatted_context
        brd_context = bundle.brd.formatted_context if bundle.brd else "(no BRD)"
    else:
        # For unknown artifact types, pass the full CB context
        cb_context = bundle.cb.formatted_context

    # Soft NFR-driver feed: only when a validated NFR exists. With no/unvalidated NFR
    # this stays "" and nothing is appended, so FRS prompts are byte-identical to before.
    nfr_context = ""
    if artifact_type in ("frs", "test_cases"):
        nfr = getattr(bundle, "nfr", None)
        if nfr and nfr.nfr_status == "validated" and nfr.requirements:
            nfr_context = nfr.formatted_context

    combined_parts = [
        "=== App Brain ===\n" + bundle.apps.formatted_context,
        "=== Project Documents ===\n" + (doc_sections or bundle.docs.outline_text),
    ]
    # Intake Context Pack — the validated understanding + resolved clarifications
    # + wiki concepts. Injected for every unit/artifact (the single chokepoint).
    intake_ctx = getattr(getattr(bundle, "intake", None), "formatted_context", "")
    if intake_ctx:
        combined_parts.append(intake_ctx)
    combined_parts.append(cb_context)
    if brd_context:
        combined_parts.append(brd_context)

    frs_context = ""
    if artifact_type == "test_cases":
        frs_context = bundle.frs.formatted_context if getattr(bundle, "frs", None) else "(no FRS)"
        combined_parts.append(frs_context)

    if nfr_context:
        combined_parts.append(nfr_context)

    combined = "\n\n".join(p for p in combined_parts if p.strip())

    return UnitContext(
        app_brain=bundle.apps.formatted_context,
        doc_sections=doc_sections or bundle.docs.outline_text,
        cb_context=cb_context,
        brd_context=brd_context,
        discover_qa=bundle.cb.discover_qa,
        combined=combined,
        frs_context=frs_context,
        nfr_context=nfr_context,
    )


def _project_cb(cb, elements: list[str]) -> str:
    """Build a CB context string including only the requested element groups."""
    sections = ["=== Concept Brief (validated) ===\n"]

    def _add_text_blocks():
        tb_by_key = {r["field_key"]: r["text"] for r in cb.text_blocks}
        for fk in ["business_context", "problem_statement", "value_hypothesis_if", "value_hypothesis_then"]:
            if text := tb_by_key.get(fk):
                label = fk.replace("_", " ").title()
                sections.append(f"**{label}:**\n{text}")

    def _add_context_map():
        if cb.context_map:
            sections.append("\n**Context Map:**")
            for r in cb.context_map:
                sections.append(f"  - {r['dimension']}: {r['detail']}")

    def _add_outcomes():
        if cb.outcomes:
            sections.append("\n**Outcomes:**")
            for r in cb.outcomes:
                sections.append(f"  - [{r['row_key']}] {r['outcome']}: {r['description']}")

    def _add_metrics():
        if cb.metrics:
            sections.append("\n**Metrics:**")
            for r in cb.metrics:
                q = " (quantifiable)" if r.get("quantifiable") else ""
                sections.append(f"  - [{r['row_key']}] {r['metric']}{q}: {r['description']}")

    def _add_capabilities():
        if cb.capabilities:
            sections.append("\n**Capabilities:**")
            for r in cb.capabilities:
                sections.append(f"  - [{r['row_key']}] {r['capability']}: {r['description']}")

    def _add_scope_items():
        if cb.scope_items:
            by_kind: dict[str, list] = {}
            for r in cb.scope_items:
                by_kind.setdefault(r["kind"], []).append(r)
            for kind_key, label in [("in_scope", "In Scope"), ("out_of_scope", "Out of Scope"), ("assumption", "Assumptions")]:
                if rows := by_kind.get(kind_key):
                    sections.append(f"\n**{label}:**")
                    for r in rows:
                        sections.append(f"  - [{r['row_key']}] {r['text']}")

    def _add_milestones():
        if cb.milestones:
            sections.append("\n**Milestones:**")
            for r in cb.milestones:
                sections.append(f"  - [{r['row_key']}] {r['milestone']} ({r['target']})")

    def _add_discover_qa():
        if cb.discover_qa and cb.discover_qa not in ("(no discover Q&A recorded)", "(no Concept Brief found)"):
            sections.append(f"\n{cb.discover_qa}")

    dispatch = {
        "text_blocks":  _add_text_blocks,
        "context_map":  _add_context_map,
        "outcomes":     _add_outcomes,
        "metrics":      _add_metrics,
        "capabilities": _add_capabilities,
        "scope_items":  _add_scope_items,
        "milestones":   _add_milestones,
        "discover_qa":  _add_discover_qa,
    }
    for elem in elements:
        if fn := dispatch.get(elem):
            fn()

    return "\n".join(sections)
