"""Concept Brief layer: all validated CB rows, discover Q&A, and enhanced brief."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import CbLayer


async def build_cb_layer(project_id: uuid.UUID, db: AsyncSession) -> CbLayer:
    """Load the full validated Concept Brief corpus for a project.

    Loads all current, active rows from every CB typed table plus discover Q&A
    and the latest enhanced brief. Status is included so callers know whether
    the CB is validated or still in-progress.
    """
    from app.models.artifact import (
        ArtifactDocument,
        CbCapability,
        CbContextMap,
        CbDiscoverEnhancedBrief,
        CbDiscoverQuestion,
        CbMilestone,
        CbMetric,
        CbOutcome,
        CbScopeItem,
        CbTextBlock,
    )

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "concept_brief",
            )
        )
    ).scalar_one_or_none()

    if doc is None:
        return CbLayer(
            cb_document_id=None,
            cb_status=None,
            cb_validated_at=None,
            cb_snapshot_key=None,
            text_blocks=[],
            context_map=[],
            outcomes=[],
            metrics=[],
            capabilities=[],
            scope_items=[],
            milestones=[],
            enhanced_brief=None,
            discover_qa="(no Concept Brief found)",
            formatted_context="(no Concept Brief found)",
        )

    async def _load_rows(model, extra_cols: list[str]) -> list[dict]:
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
            {"row_key": r.row_key, **{c: getattr(r, c) for c in extra_cols}}
            for r in rows
        ]

    text_blocks = await _load_rows(CbTextBlock, ["field_key", "text"])
    context_map = await _load_rows(CbContextMap, ["dimension", "detail"])
    outcomes = await _load_rows(CbOutcome, ["outcome", "description"])
    metrics = await _load_rows(CbMetric, ["metric", "description", "quantifiable"])
    capabilities = await _load_rows(CbCapability, ["capability", "description"])
    scope_items = await _load_rows(CbScopeItem, ["kind", "text"])
    milestones = await _load_rows(CbMilestone, ["milestone", "target", "description"])

    # Latest enhanced brief
    latest_eb = (
        await db.execute(
            select(CbDiscoverEnhancedBrief)
            .where(CbDiscoverEnhancedBrief.artifact_document_id == doc.id)
            .order_by(CbDiscoverEnhancedBrief.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # All discover Q&A (answered + inferred)
    questions = (
        await db.execute(
            select(CbDiscoverQuestion)
            .where(CbDiscoverQuestion.artifact_document_id == doc.id)
            .order_by(CbDiscoverQuestion.seq)
        )
    ).scalars().all()
    discover_qa = _format_discover_qa(questions)

    formatted_context = _format_cb_context(
        text_blocks, context_map, outcomes, metrics, capabilities, scope_items, milestones, discover_qa,
    )

    return CbLayer(
        cb_document_id=str(doc.id),
        cb_status=doc.status,
        cb_validated_at=doc.validated_at.isoformat() if doc.validated_at else None,
        cb_snapshot_key=doc.validated_snapshot_key,
        text_blocks=text_blocks,
        context_map=context_map,
        outcomes=outcomes,
        metrics=metrics,
        capabilities=capabilities,
        scope_items=scope_items,
        milestones=milestones,
        enhanced_brief=latest_eb.enhanced_brief if latest_eb else None,
        discover_qa=discover_qa,
        formatted_context=formatted_context,
    )


def _format_discover_qa(questions: list) -> str:
    if not questions:
        return "(no discover Q&A recorded)"
    lines = ["=== Concept Brief Discovery Q&A ===\n"]
    for q in questions:
        answer = q.answer or q.inferred_answer or "(not answered)"
        source = q.source or ""
        suffix = f" [from: {source}]" if source else ""
        lines.append(f"Q: {q.question_text}")
        lines.append(f"A: {answer}{suffix}\n")
    return "\n".join(lines)


def _format_cb_context(
    text_blocks: list[dict],
    context_map: list[dict],
    outcomes: list[dict],
    metrics: list[dict],
    capabilities: list[dict],
    scope_items: list[dict],
    milestones: list[dict],
    discover_qa: str,
) -> str:
    sections: list[str] = ["=== Validated Concept Brief ===\n"]

    tb_by_key = {r["field_key"]: r["text"] for r in text_blocks}
    if bc := tb_by_key.get("business_context"):
        sections.append(f"**Business Context:**\n{bc}")
    if ps := tb_by_key.get("problem_statement"):
        sections.append(f"\n**Problem Statement:**\n{ps}")
    if vh_if := tb_by_key.get("value_hypothesis_if"):
        vh_then = tb_by_key.get("value_hypothesis_then", "")
        sections.append(f"\n**Value Hypothesis:**\nIf {vh_if}\nThen {vh_then}")

    if context_map:
        sections.append("\n**Context Map:**")
        for r in context_map:
            sections.append(f"  - {r['dimension']}: {r['detail']}")

    if outcomes:
        sections.append("\n**Expected Outcomes:**")
        for r in outcomes:
            sections.append(f"  - [{r['row_key']}] {r['outcome']}: {r['description']}")

    if metrics:
        sections.append("\n**Success Metrics:**")
        for r in metrics:
            q_flag = " (quantifiable)" if r.get("quantifiable") else ""
            sections.append(f"  - [{r['row_key']}] {r['metric']}{q_flag}: {r['description']}")

    if capabilities:
        sections.append("\n**Proposed Capabilities:**")
        for r in capabilities:
            sections.append(f"  - [{r['row_key']}] {r['capability']}: {r['description']}")

    if scope_items:
        by_kind: dict[str, list] = {}
        for r in scope_items:
            by_kind.setdefault(r["kind"], []).append(r)
        for kind_key, label in [("in_scope", "In Scope"), ("out_of_scope", "Out of Scope"), ("assumption", "Assumptions")]:
            if rows := by_kind.get(kind_key):
                sections.append(f"\n**{label}:**")
                for r in rows:
                    sections.append(f"  - [{r['row_key']}] {r['text']}")

    if milestones:
        sections.append("\n**Milestones:**")
        for r in milestones:
            sections.append(f"  - [{r['row_key']}] {r['milestone']} ({r['target']}): {r['description']}")

    if discover_qa and discover_qa != "(no discover Q&A recorded)":
        sections.append(f"\n{discover_qa}")

    return "\n".join(sections)
