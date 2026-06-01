"""NFR layer: all current NFR rows + traceability.

Loaded (optionally, may be empty) for FRS + test_cases generation so that validated
NFRs can softly drive FRS design (target_kind='nfr_driver'). NFR is NEVER a hard gate
on FRS — projection.py only injects this when nfr_status == 'validated'.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import NfrLayer


async def build_nfr_layer(project_id: uuid.UUID, db: AsyncSession) -> NfrLayer:
    """Load the NFR corpus for a project. Returns an empty layer when no NFR exists."""
    from app.models.artifact import ArtifactDocument
    from app.models.nfr import (
        NfrDecision, NfrGlossary, NfrOpenQuestion, NfrReference, NfrRequirement,
        NfrRisk, NfrTextBlock, NfrTradeoff, NfrTraceability,
    )

    doc = (
        await db.execute(
            select(ArtifactDocument).where(
                ArtifactDocument.project_id == project_id,
                ArtifactDocument.artifact_type == "nfr",
            )
        )
    ).scalar_one_or_none()

    if doc is None:
        return NfrLayer(
            nfr_document_id=None, nfr_status=None, nfr_validated_at=None, nfr_snapshot_key=None,
            requirements=[], risks=[], tradeoffs=[], open_questions=[], decisions=[],
            references=[], glossary=[], text_blocks=[], traceability=[],
            formatted_context="(no NFR found)",
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
        return [{"row_key": r.row_key, **{c: getattr(r, c) for c in cols}} for r in rows]

    requirements = await _load(NfrRequirement, ["category", "attribute", "requirement", "priority", "rationale", "measurement", "brd_refs", "na"])
    risks = await _load(NfrRisk, ["risk_id", "description", "affected_attribute", "impact", "likelihood", "mitigation", "owner", "risk_status"])
    tradeoffs = await _load(NfrTradeoff, ["tradeoff", "options_considered", "decision", "rationale", "decided_on", "decision_maker"])
    open_qs = await _load(NfrOpenQuestion, ["question", "owner", "due_date", "oq_status"])
    decisions = await _load(NfrDecision, ["description", "owner", "target_date", "decision_status"])
    refs = await _load(NfrReference, ["ref_type", "title", "location", "notes"])
    glossary = await _load(NfrGlossary, ["term", "definition"])
    text_blocks = await _load(NfrTextBlock, ["block_kind", "content"])

    traces = (
        await db.execute(select(NfrTraceability).where(NfrTraceability.document_id == doc.id))
    ).scalars().all()
    trace_dicts = [{
        "source_table": t.source_table, "source_row_key": t.source_row_key,
        "target_kind": t.target_kind, "target_ref": t.target_ref,
        "target_label": t.target_label, "confidence": t.confidence,
    } for t in traces]

    return NfrLayer(
        nfr_document_id=str(doc.id),
        nfr_status=doc.status,
        nfr_validated_at=doc.validated_at.isoformat() if doc.validated_at else None,
        nfr_snapshot_key=doc.validated_snapshot_key,
        requirements=requirements, risks=risks, tradeoffs=tradeoffs,
        open_questions=open_qs, decisions=decisions, references=refs,
        glossary=glossary, text_blocks=text_blocks, traceability=trace_dicts,
        formatted_context=_format_nfr_context(requirements),
    )


def _format_nfr_context(requirements: list[dict]) -> str:
    """Render validated NFRs grouped by category as a compact prompt block."""
    if not requirements:
        return "(no NFRs)"
    lines: list[str] = ["=== Validated NFR Drivers (optional) ===\n"]
    by_cat: dict[str, list[dict]] = {}
    for r in requirements:
        if r.get("na"):
            continue
        by_cat.setdefault(r.get("category", "other"), []).append(r)
    for cat in sorted(by_cat):
        lines.append(f"\n**{cat.title()}:**")
        for r in by_cat[cat]:
            refs = ", ".join(r.get("brd_refs") or [])
            meas = r.get("measurement") or "—"
            lines.append(
                f"  - [{r['row_key']}] ({r.get('priority', 'should')}) {r['requirement']} "
                f"— measure: {meas}" + (f" ⇒ {refs}" if refs else "")
            )
    return "\n".join(lines)
