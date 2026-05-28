"""BRD layer: all validated BRD rows + traceability + discover Q&A.

Populated only for FRS generation (artifact_type='frs'). For FRS-specific
context, the readiness check enforces brd_status == 'validated'.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import BrdLayer


async def build_brd_layer(project_id: uuid.UUID, db: AsyncSession) -> BrdLayer:
    """Load the full validated BRD corpus for a project.

    Returns an empty BrdLayer (with brd_status=None) when no BRD exists.
    Callers use the BundleReadiness check to enforce validation status.
    """
    from app.models.artifact import ArtifactDocument
    from app.models.brd import (
        BrdActor, BrdAssumption, BrdBusinessRequirement, BrdConstraint, BrdDataEntity,
        BrdDecision, BrdDependency, BrdGlossaryEntry, BrdKpi, BrdMilestone, BrdObjective,
        BrdOpenQuestion, BrdPhase, BrdProcessStep, BrdReference, BrdReportRequirement,
        BrdRisk, BrdScopeItem, BrdStakeholder, BrdTextBlock, BrdTraceability,
    )

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "brd",
            )
        )
    ).scalar_one_or_none()

    if doc is None:
        return BrdLayer(
            brd_document_id=None, brd_status=None,
            brd_validated_at=None, brd_snapshot_key=None,
            text_blocks=[], objectives=[], stakeholders=[], actors=[],
            scope_items=[], process_steps=[], business_requirements=[],
            data_entities=[], report_requirements=[],
            assumptions=[], constraints=[], dependencies=[],
            risks=[], phases=[], milestones=[], kpis=[],
            open_questions=[], decisions=[], references=[], glossary_entries=[],
            traceability=[], formatted_context="(no BRD found)",
        )

    async def _load(model, cols: list[str]) -> list[dict]:
        rows = (
            await db.execute(
                select(model).where(
                    model.document_id == doc.id,
                    model.is_current.is_(True),
                    model.status == "active",
                )
            )
        ).scalars().all()
        return [
            {"row_key": r.row_key, **{c: getattr(r, c) for c in cols}}
            for r in rows
        ]

    text_blocks = await _load(BrdTextBlock, ["field_key", "text"])
    objectives = await _load(BrdObjective, ["statement", "category", "priority", "owner", "cb_outcome_ref"])
    stakeholders = await _load(BrdStakeholder, ["name", "stakeholder_type", "role", "interest", "influence"])
    actors = await _load(BrdActor, ["name", "actor_type", "description", "interactions"])
    scope_items = await _load(BrdScopeItem, ["kind", "text", "rationale", "cb_scope_ref"])
    process_steps = await _load(BrdProcessStep, ["step_type", "step_number", "actor", "action", "pain_point", "improvement"])
    brs = await _load(BrdBusinessRequirement, [
        "title", "description", "priority", "category",
        "acceptance_criteria", "objective_refs", "stakeholder_refs",
        "rationale", "completeness", "confidence",
    ])
    data_entities = await _load(BrdDataEntity, ["entity_name", "description", "owner_system", "data_sensitivity", "key_attributes"])
    report_reqs = await _load(BrdReportRequirement, ["report_name", "description", "audience", "frequency", "key_metrics"])
    assumptions = await _load(BrdAssumption, ["assumption", "impact_if_wrong", "owner", "cb_scope_ref"])
    constraints = await _load(BrdConstraint, ["constraint_text", "constraint_type", "source_ref"])
    dependencies = await _load(BrdDependency, ["dependency", "dependency_type", "owner", "due_date"])
    risks = await _load(BrdRisk, ["risk", "description", "severity", "likelihood", "mitigation", "owner"])
    phases = await _load(BrdPhase, ["phase_name", "description", "target_date", "included_br_refs"])
    milestones = await _load(BrdMilestone, ["milestone", "target", "description", "phase_ref", "cb_milestone_ref"])
    kpis = await _load(BrdKpi, ["kpi_name", "description", "baseline", "target", "timeframe", "data_source", "objective_ref", "cb_metric_ref"])
    open_qs = await _load(BrdOpenQuestion, ["question", "context", "owner", "due_date"])
    decisions = await _load(BrdDecision, ["decision", "rationale", "owner", "decision_date", "alternatives_considered"])
    refs = await _load(BrdReference, ["title", "reference_type", "location", "description"])
    glossary = await _load(BrdGlossaryEntry, ["term", "definition", "source_ref"])

    # Traceability (not versioned — all rows are current)
    traces = (
        await db.execute(
            select(BrdTraceability).where(BrdTraceability.document_id == doc.id)
        )
    ).scalars().all()
    trace_dicts = [{
        "source_table": t.source_table,
        "source_row_key": t.source_row_key,
        "target_kind": t.target_kind,
        "target_ref": t.target_ref,
        "target_label": t.target_label,
        "confidence": t.confidence,
    } for t in traces]

    formatted = _format_brd_context(
        text_blocks, objectives, stakeholders, actors, scope_items,
        process_steps, brs, data_entities, report_reqs,
        assumptions, constraints, dependencies, risks,
        phases, milestones, kpis, open_qs, decisions,
    )

    return BrdLayer(
        brd_document_id=str(doc.id),
        brd_status=doc.status,
        brd_validated_at=doc.validated_at.isoformat() if doc.validated_at else None,
        brd_snapshot_key=doc.validated_snapshot_key,
        text_blocks=text_blocks, objectives=objectives, stakeholders=stakeholders,
        actors=actors, scope_items=scope_items, process_steps=process_steps,
        business_requirements=brs, data_entities=data_entities,
        report_requirements=report_reqs, assumptions=assumptions,
        constraints=constraints, dependencies=dependencies, risks=risks,
        phases=phases, milestones=milestones, kpis=kpis,
        open_questions=open_qs, decisions=decisions,
        references=refs, glossary_entries=glossary,
        traceability=trace_dicts, formatted_context=formatted,
    )


def _format_brd_context(
    text_blocks, objectives, stakeholders, actors, scope_items,
    process_steps, brs, data_entities, report_reqs,
    assumptions, constraints, dependencies, risks,
    phases, milestones, kpis, open_qs, decisions,
) -> str:
    """Render the BRD as a compact prompt-ready string for FRS modularization.

    Includes every section that influences module decomposition — emphasizes
    business requirements (the keystone) with traces to objectives + stakeholders.
    """
    lines: list[str] = ["=== Validated BRD ===\n"]

    tb_by_key = {r["field_key"]: r["text"] for r in text_blocks}
    for fk in ("business_context", "problem_statement", "root_causes"):
        if text := tb_by_key.get(fk):
            label = fk.replace("_", " ").title()
            lines.append(f"**{label}:**\n{text}\n")

    if objectives:
        lines.append("\n**Strategic Objectives:**")
        for o in objectives:
            owner = o.get("owner") or "—"
            lines.append(f"  - [{o['row_key']}] ({o['priority']}) {o['statement']} — owner: {owner}")

    if stakeholders:
        lines.append("\n**Stakeholders:**")
        for s in stakeholders:
            interest = s.get("interest") or "—"
            influence = s.get("influence") or "—"
            lines.append(
                f"  - [{s['row_key']}] {s['name']} ({s['stakeholder_type']}) — "
                f"role: {s.get('role') or '—'}; interest: {interest}; influence: {influence}"
            )

    if actors:
        lines.append("\n**Actors:**")
        for a in actors:
            lines.append(f"  - [{a['row_key']}] {a['name']} ({a['actor_type']}) — {a.get('description') or ''}")

    if scope_items:
        by_kind: dict[str, list] = {}
        for s in scope_items:
            by_kind.setdefault(s["kind"], []).append(s)
        for kind_key, label in [("in_scope", "In Scope"), ("out_of_scope", "Out of Scope"), ("assumption", "Assumption")]:
            if rows := by_kind.get(kind_key):
                lines.append(f"\n**Scope · {label}:**")
                for r in rows:
                    lines.append(f"  - [{r['row_key']}] {r['text']}")

    if process_steps:
        asis = [p for p in process_steps if p.get("step_type") == "asis"]
        tobe = [p for p in process_steps if p.get("step_type") == "tobe"]
        if asis:
            lines.append("\n**As-Is Process:**")
            for p in sorted(asis, key=lambda x: x.get("step_number") or 0):
                lines.append(f"  {p['step_number']}. ({p.get('actor') or '—'}) {p['action']}")
        if tobe:
            lines.append("\n**To-Be Process:**")
            for p in sorted(tobe, key=lambda x: x.get("step_number") or 0):
                lines.append(f"  {p['step_number']}. ({p.get('actor') or '—'}) {p['action']}")

    if brs:
        lines.append("\n**Business Requirements (KEYSTONE):**")
        for br in brs:
            ac = br.get("acceptance_criteria") or []
            ac_summary = f" · {len(ac)} AC" if ac else ""
            desc = br.get("description") or ""
            desc_short = desc[:200] + ("…" if len(desc) > 200 else "")
            obj_refs = ", ".join(br.get("objective_refs") or [])
            stk_refs = ", ".join(br.get("stakeholder_refs") or [])
            lines.append(
                f"  - [{br['row_key']}] ({br['priority']}, {br['category']}) {br['title']}{ac_summary}\n"
                f"    {desc_short}\n"
                f"    Traces → objectives: {obj_refs or '—'} · stakeholders: {stk_refs or '—'}"
            )

    if kpis:
        lines.append("\n**KPIs:**")
        for k in kpis:
            lines.append(
                f"  - [{k['row_key']}] {k['kpi_name']}: "
                f"baseline '{k.get('baseline') or '—'}' → target '{k.get('target') or '—'}' "
                f"({k.get('timeframe') or '—'})"
            )

    if risks:
        lines.append("\n**Risks:**")
        for r in risks:
            lines.append(
                f"  - [{r['row_key']}] ({r['severity']}/{r['likelihood']}) {r['risk']} — "
                f"mitigation: {r.get('mitigation') or '—'}"
            )

    if assumptions:
        lines.append("\n**Assumptions:**")
        for a in assumptions:
            lines.append(f"  - [{a['row_key']}] {a['assumption']}")

    if constraints:
        lines.append("\n**Constraints:**")
        for c in constraints:
            lines.append(f"  - [{c['row_key']}] ({c.get('constraint_type') or '—'}) {c['constraint_text']}")

    if dependencies:
        lines.append("\n**Dependencies:**")
        for d in dependencies:
            lines.append(f"  - [{d['row_key']}] ({d.get('dependency_type') or '—'}) {d['dependency']}")

    if phases:
        lines.append("\n**Implementation Phases:**")
        for p in phases:
            br_refs = ", ".join(p.get("included_br_refs") or [])
            lines.append(
                f"  - [{p['row_key']}] {p['phase_name']} "
                f"(target: {p.get('target_date') or '—'}) — covers BRs: {br_refs or '—'}"
            )

    if milestones:
        lines.append("\n**Milestones:**")
        for m in milestones:
            lines.append(f"  - [{m['row_key']}] {m['milestone']} ({m.get('target') or '—'})")

    if data_entities:
        lines.append("\n**Data Entities (BRD level):**")
        for e in data_entities:
            lines.append(
                f"  - [{e['row_key']}] {e['entity_name']} "
                f"({e.get('data_sensitivity') or 'standard'}) — owner: {e.get('owner_system') or '—'}"
            )

    if report_reqs:
        lines.append("\n**Reporting Requirements:**")
        for r in report_reqs:
            lines.append(
                f"  - [{r['row_key']}] {r['report_name']} → audience: {r.get('audience') or '—'} "
                f"({r.get('frequency') or '—'})"
            )

    if open_qs:
        lines.append("\n**Open Questions (BRD):**")
        for q in open_qs:
            lines.append(f"  - [{q['row_key']}] {q['question']} (owner: {q.get('owner') or '—'})")

    if decisions:
        lines.append("\n**Decisions Recorded:**")
        for d in decisions:
            lines.append(f"  - [{d['row_key']}] {d['decision']} — rationale: {d.get('rationale') or '—'}")

    return "\n".join(lines)
