"""Markdown export for BRD (Business Requirements Document)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.project import Project


def _esc(text: str | None) -> str:
    """Escape pipe characters to not break Markdown tables."""
    return (str(text) if text is not None else "—").replace("|", "\\|").replace("\n", " ")


def _text_block(sections: dict, field_key: str) -> str:
    """Extract text from brd_text_blocks for a given field_key."""
    rows = sections.get("brd_text_blocks", [])
    for r in rows:
        if r.get("field_key") == field_key:
            return r.get("text") or "—"
    return "—"


def _rows(sections: dict, table: str) -> list[dict]:
    return sections.get(table, [])


def export_brd_markdown(detail: dict, project: Project) -> str:
    """Render the full BRD as structured Markdown."""
    doc = detail.get("document") or {}
    sections = detail.get("sections") or {}
    traceability_by_source = detail.get("traceability_by_source") or {}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    status = "Validated" if doc.get("status") == "validated" else "Draft"
    validated_snapshot_key = doc.get("validated_snapshot_key") or "draft"

    L: list[str] = []

    def h(level: int, title: str) -> None:
        L.append("")
        L.append(f"{'#' * level} {title}")
        L.append("")

    def rule() -> None:
        L.append("")
        L.append("---")
        L.append("")

    def para(text: str) -> None:
        L.append(text or "—")
        L.append("")

    # ── Cover ──────────────────────────────────────────────────────────────────
    L.append("# Business Requirements Document")
    L.append("")
    L.append(f"**Project:** {_esc(project.name)}")
    L.append(f"**Business Unit:** {_esc(project.business_unit)}")
    L.append(f"**Status:** {status}")
    L.append(f"**Generated:** {now}")
    L.append(f"**Version:** v{_esc(validated_snapshot_key)}")
    L.append("")

    rule()

    # ── §1 Business Context ───────────────────────────────────────────────────
    h(2, "§1. Business Context")
    para(_text_block(sections, "business_context"))

    # ── §2 Problem Statement ──────────────────────────────────────────────────
    h(2, "§2. Problem Statement")
    para(_text_block(sections, "problem_statement"))

    root_causes_text = _text_block(sections, "root_causes")
    if root_causes_text and root_causes_text != "—":
        h(3, "Root Causes")
        para(root_causes_text)

    # ── §3 Strategic Objectives ───────────────────────────────────────────────
    h(2, "§3. Strategic Objectives")
    objs = _rows(sections, "brd_objectives")
    if objs:
        L.append("| ID | Statement | Priority | Category | Owner |")
        L.append("|---|---|---|---|---|")
        for o in sorted(objs, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(o.get('row_key'))} "
                f"| {_esc(o.get('statement'))} "
                f"| {_esc(o.get('priority'))} "
                f"| {_esc(o.get('category'))} "
                f"| {_esc(o.get('owner'))} |"
            )
        L.append("")
    else:
        para("_(no objectives generated yet)_")

    # ── §4 Stakeholders & Actors ──────────────────────────────────────────────
    h(2, "§4. Stakeholders & Actors")

    h(3, "Stakeholders")
    stks = _rows(sections, "brd_stakeholders")
    if stks:
        L.append("| ID | Name | Type | Role | Interest | Influence |")
        L.append("|---|---|---|---|---|---|")
        for s in sorted(stks, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(s.get('row_key'))} "
                f"| {_esc(s.get('name'))} "
                f"| {_esc(s.get('stakeholder_type'))} "
                f"| {_esc(s.get('role'))} "
                f"| {_esc(s.get('interest'))} "
                f"| {_esc(s.get('influence'))} |"
            )
        L.append("")
    else:
        para("_(no stakeholders generated yet)_")

    h(3, "Actors")
    actors = _rows(sections, "brd_actors")
    if actors:
        L.append("| ID | Name | Type | Description |")
        L.append("|---|---|---|---|")
        for a in sorted(actors, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(a.get('row_key'))} "
                f"| {_esc(a.get('name'))} "
                f"| {_esc(a.get('actor_type'))} "
                f"| {_esc(a.get('description'))} |"
            )
        L.append("")
    else:
        para("_(no actors generated yet)_")

    # ── §5 Scope ──────────────────────────────────────────────────────────────
    h(2, "§5. Scope")
    scope_items = _rows(sections, "brd_scope_items")

    def _scope_group(kind: str, title: str) -> None:
        h(3, title)
        items = [s for s in scope_items if s.get("kind") == kind]
        if items:
            for item in sorted(items, key=lambda x: x.get("row_key", "")):
                rationale = f" _{_esc(item.get('rationale'))}_" if item.get("rationale") else ""
                L.append(f"- **{_esc(item.get('row_key'))}:** {_esc(item.get('text'))}{rationale}")
            L.append("")
        else:
            para("_(none)_")

    _scope_group("in_scope", "In Scope")
    _scope_group("out_of_scope", "Out of Scope")
    _scope_group("assumption", "Assumptions (Scope)")

    # ── §6 Business Processes ─────────────────────────────────────────────────
    h(2, "§6. Business Processes")
    process_steps = _rows(sections, "brd_process_steps")

    def _process_group(step_type: str, title: str) -> None:
        h(3, title)
        steps = sorted(
            [s for s in process_steps if s.get("step_type") == step_type],
            key=lambda x: x.get("step_number", 0),
        )
        if steps:
            L.append("| Step | Actor | Action | Note |")
            L.append("|---|---|---|---|")
            for s in steps:
                note = s.get("pain_point") or s.get("improvement") or ""
                L.append(
                    f"| {_esc(s.get('step_number'))} "
                    f"| {_esc(s.get('actor'))} "
                    f"| {_esc(s.get('action'))} "
                    f"| {_esc(note)} |"
                )
            L.append("")
        else:
            para("_(none)_")

    _process_group("asis", "As-Is Process")
    _process_group("tobe", "To-Be Process")

    # ── §7 Business Requirements ──────────────────────────────────────────────
    h(2, "§7. Business Requirements ★")
    brs = _rows(sections, "brd_business_requirements")
    if brs:
        L.append("| ID | Priority | Category | Title |")
        L.append("|---|---|---|---|")
        for br in sorted(brs, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(br.get('row_key'))} "
                f"| {_esc(br.get('priority'))} "
                f"| {_esc(br.get('category'))} "
                f"| {_esc(br.get('title'))} |"
            )
        L.append("")

        # Per-BR detail blocks
        for br in sorted(brs, key=lambda x: x.get("row_key", "")):
            rk = br.get("row_key", "")
            L.append(f"### {rk} · {_esc(br.get('priority'))} · {_esc(br.get('title'))}")
            L.append("")
            L.append(f"**Description:** {_esc(br.get('description'))}")
            L.append("")

            ac_list = br.get("acceptance_criteria") or []
            if ac_list:
                L.append("**Acceptance Criteria:**")
                L.append("")
                for ac in ac_list:
                    if isinstance(ac, dict):
                        L.append(
                            f"- Given {_esc(ac.get('given'))} "
                            f"When {_esc(ac.get('when'))} "
                            f"Then {_esc(ac.get('then'))}"
                        )
                L.append("")

            obj_refs = br.get("objective_refs") or []
            if obj_refs:
                L.append(f"**Objective Refs:** {', '.join(_esc(r) for r in obj_refs)}")
                L.append("")

            stk_refs = br.get("stakeholder_refs") or []
            if stk_refs:
                L.append(f"**Stakeholder Refs:** {', '.join(_esc(r) for r in stk_refs)}")
                L.append("")

            if br.get("rationale"):
                L.append(f"**Rationale:** {_esc(br.get('rationale'))}")
                L.append("")
    else:
        para("_(no business requirements generated yet)_")

    # ── §8 Data & Reporting ───────────────────────────────────────────────────
    h(2, "§8. Data & Reporting")

    h(3, "Data Entities")
    entities = _rows(sections, "brd_data_entities")
    if entities:
        L.append("| ID | Entity | Owner System | Sensitivity | Key Attributes |")
        L.append("|---|---|---|---|---|")
        for e in sorted(entities, key=lambda x: x.get("row_key", "")):
            attrs = ", ".join(e.get("key_attributes") or [])
            L.append(
                f"| {_esc(e.get('row_key'))} "
                f"| {_esc(e.get('entity_name'))} "
                f"| {_esc(e.get('owner_system'))} "
                f"| {_esc(e.get('data_sensitivity'))} "
                f"| {_esc(attrs)} |"
            )
        L.append("")
    else:
        para("_(none)_")

    h(3, "Report Requirements")
    rpts = _rows(sections, "brd_report_requirements")
    if rpts:
        L.append("| ID | Report Name | Audience | Frequency | Key Metrics |")
        L.append("|---|---|---|---|---|")
        for r in sorted(rpts, key=lambda x: x.get("row_key", "")):
            metrics = ", ".join(r.get("key_metrics") or [])
            L.append(
                f"| {_esc(r.get('row_key'))} "
                f"| {_esc(r.get('report_name'))} "
                f"| {_esc(r.get('audience'))} "
                f"| {_esc(r.get('frequency'))} "
                f"| {_esc(metrics)} |"
            )
        L.append("")
    else:
        para("_(none)_")

    # ── §9 Assumptions, Dependencies & Constraints ────────────────────────────
    h(2, "§9. Assumptions, Dependencies & Constraints")

    h(3, "Assumptions")
    assumptions = _rows(sections, "brd_assumptions")
    if assumptions:
        for a in sorted(assumptions, key=lambda x: x.get("row_key", "")):
            L.append(f"- **{_esc(a.get('row_key'))}:** {_esc(a.get('assumption'))}")
            if a.get("impact_if_wrong"):
                L.append(f"  _Impact if wrong: {_esc(a.get('impact_if_wrong'))}_")
        L.append("")
    else:
        para("_(none)_")

    h(3, "Constraints")
    constraints = _rows(sections, "brd_constraints")
    if constraints:
        for c in sorted(constraints, key=lambda x: x.get("row_key", "")):
            L.append(
                f"- **{_esc(c.get('row_key'))} [{_esc(c.get('constraint_type'))}]:** "
                f"{_esc(c.get('constraint_text'))}"
            )
        L.append("")
    else:
        para("_(none)_")

    h(3, "Dependencies")
    deps = _rows(sections, "brd_dependencies")
    if deps:
        L.append("| ID | Dependency | Type | Owner | Due Date |")
        L.append("|---|---|---|---|---|")
        for d in sorted(deps, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(d.get('row_key'))} "
                f"| {_esc(d.get('dependency'))} "
                f"| {_esc(d.get('dependency_type'))} "
                f"| {_esc(d.get('owner'))} "
                f"| {_esc(d.get('due_date'))} |"
            )
        L.append("")
    else:
        para("_(none)_")

    # ── §10 Risks ─────────────────────────────────────────────────────────────
    h(2, "§10. Risks & Issues")
    risks = _rows(sections, "brd_risks")
    if risks:
        L.append("| ID | Risk | Severity | Likelihood | Mitigation | Owner |")
        L.append("|---|---|---|---|---|---|")
        for r in sorted(risks, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(r.get('row_key'))} "
                f"| {_esc(r.get('risk'))} "
                f"| {_esc(r.get('severity'))} "
                f"| {_esc(r.get('likelihood'))} "
                f"| {_esc(r.get('mitigation'))} "
                f"| {_esc(r.get('owner'))} |"
            )
        L.append("")
    else:
        para("_(no risks generated yet)_")

    # ── §11 Implementation & Phasing ──────────────────────────────────────────
    h(2, "§11. Implementation & Phasing")

    h(3, "Phases")
    phases = _rows(sections, "brd_phases")
    if phases:
        for p in sorted(phases, key=lambda x: x.get("row_key", "")):
            h(4, f"{_esc(p.get('row_key'))} — {_esc(p.get('phase_name'))}")
            L.append(f"**Target:** {_esc(p.get('target_date'))}")
            L.append("")
            if p.get("description"):
                para(_esc(p.get("description")))
            br_refs = p.get("included_br_refs") or []
            if br_refs:
                L.append(f"**BRs:** {', '.join(_esc(r) for r in br_refs)}")
                L.append("")
    else:
        para("_(none)_")

    h(3, "Milestones")
    milestones = _rows(sections, "brd_milestones")
    if milestones:
        L.append("| ID | Milestone | Target | Phase |")
        L.append("|---|---|---|---|")
        for m in sorted(milestones, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(m.get('row_key'))} "
                f"| {_esc(m.get('milestone'))} "
                f"| {_esc(m.get('target'))} "
                f"| {_esc(m.get('phase_ref'))} |"
            )
        L.append("")
    else:
        para("_(none)_")

    # ── §12 KPIs ──────────────────────────────────────────────────────────────
    h(2, "§12. KPIs & Success Metrics")
    kpis = _rows(sections, "brd_kpis")
    if kpis:
        L.append("| ID | KPI | Baseline | Target | Timeframe | Data Source |")
        L.append("|---|---|---|---|---|---|")
        for k in sorted(kpis, key=lambda x: x.get("row_key", "")):
            L.append(
                f"| {_esc(k.get('row_key'))} "
                f"| {_esc(k.get('kpi_name'))} "
                f"| {_esc(k.get('baseline'))} "
                f"| {_esc(k.get('target'))} "
                f"| {_esc(k.get('timeframe'))} "
                f"| {_esc(k.get('data_source'))} |"
            )
        L.append("")
    else:
        para("_(no KPIs generated yet)_")

    # ── §13 Open Questions & Decisions ────────────────────────────────────────
    h(2, "§13. Open Questions & Decisions")

    h(3, "Open Questions")
    oqs = _rows(sections, "brd_open_questions")
    if oqs:
        for q in sorted(oqs, key=lambda x: x.get("row_key", "")):
            L.append(f"- **{_esc(q.get('row_key'))}:** {_esc(q.get('question'))}")
            if q.get("context"):
                L.append(f"  _Context: {_esc(q.get('context'))}_")
            if q.get("owner"):
                L.append(f"  Owner: {_esc(q.get('owner'))}")
        L.append("")
    else:
        para("_(none)_")

    h(3, "Decisions")
    decisions = _rows(sections, "brd_decisions")
    if decisions:
        for d in sorted(decisions, key=lambda x: x.get("row_key", "")):
            h(4, f"{_esc(d.get('row_key'))} — {_esc(d.get('decision'))}")
            L.append(f"**Rationale:** {_esc(d.get('rationale'))}")
            L.append("")
            if d.get("alternatives_considered"):
                L.append(f"**Alternatives:** {_esc(d.get('alternatives_considered'))}")
                L.append("")
            L.append(
                f"Owner: {_esc(d.get('owner'))} | Date: {_esc(d.get('decision_date'))}"
            )
            L.append("")
    else:
        para("_(none)_")

    # ── §14 References & Glossary ─────────────────────────────────────────────
    h(2, "§14. References & Glossary")

    h(3, "References")
    refs = _rows(sections, "brd_references")
    if refs:
        for r in sorted(refs, key=lambda x: x.get("row_key", "")):
            L.append(
                f"- **{_esc(r.get('row_key'))} [{_esc(r.get('reference_type'))}]:** "
                f"{_esc(r.get('title'))} — {_esc(r.get('description'))}"
            )
        L.append("")
    else:
        para("_(none)_")

    h(3, "Glossary")
    glossary = _rows(sections, "brd_glossary_entries")
    if glossary:
        L.append("| Term | Definition |")
        L.append("|---|---|")
        for g in sorted(glossary, key=lambda x: x.get("term", "")):
            L.append(f"| {_esc(g.get('term'))} | {_esc(g.get('definition'))} |")
        L.append("")
    else:
        para("_(none)_")

    # ── Appendix A — Traceability Matrix ──────────────────────────────────────
    rule()
    h(2, "Appendix A — Traceability Matrix")

    if traceability_by_source:
        L.append("| BRD Row | Target Kind | Target Ref | Target Label | Confidence |")
        L.append("|---|---|---|---|---|")
        for source_row_key in sorted(traceability_by_source.keys()):
            for t in traceability_by_source[source_row_key]:
                L.append(
                    f"| {_esc(source_row_key)} "
                    f"| {_esc(t.get('target_kind'))} "
                    f"| {_esc(t.get('target_ref'))} "
                    f"| {_esc(t.get('target_label'))} "
                    f"| {_esc(t.get('confidence'))} |"
                )
        L.append("")
    else:
        para("_(no traceability entries)_")

    # ── Appendix B — Snapshot ─────────────────────────────────────────────────
    h(2, "Appendix B — Snapshot References")
    L.append("Generated from context bundle captured at validation time.")
    L.append("")
    L.append(f"- **Artifact Document ID:** {_esc(doc.get('id'))}")
    L.append(f"- **Validated Snapshot Key:** {_esc(doc.get('validated_snapshot_key'))}")
    L.append(f"- **Export Date:** {now}")
    L.append("")

    return "\n".join(L)
