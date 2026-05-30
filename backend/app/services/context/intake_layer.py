"""Intake Context Pack (E2) — the validated Requirement Understanding + resolved
clarifications + project wiki concept briefs, formatted as a grounding block that
every downstream generator (Concept Brief / BRD / FRS) consumes.

Previously RU.content_json never reached generation; this layer pours it in,
carrying citation tokens so downstream rows can record provenance back to intake.
See .claude/plans/E2-intelligent-intake.md §A8.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gap import GapQuestion
from app.models.project_wiki import ProjectWikiConcept
from app.models.understanding import RequirementUnderstanding

# RU content_json fields surfaced downstream, in display order.
_RU_LIST_FIELDS = [
    ("functional_areas", "Functional areas"),
    ("systems", "Systems"),
    ("integrations", "Integrations"),
    ("roles", "Roles"),
    ("risks", "Risks"),
]


@dataclass
class IntakeLayer:
    understanding: dict
    resolved_clarifications: list[dict]
    wiki_concepts: list[dict]
    formatted_context: str
    citation_index: dict = field(default_factory=dict)


def _format(understanding: dict, clarifs: list[dict], concepts: list[dict]) -> str:
    if not (understanding or clarifs or concepts):
        return ""
    out: list[str] = ["=== Project Understanding (Intake) ==="]

    obj = understanding.get("objective")
    if obj:
        out.append(f"Objective: {obj}")
    tp = understanding.get("target_process")
    if tp:
        out.append(f"Target process: {tp}")
    for key, label in _RU_LIST_FIELDS:
        vals = understanding.get(key) or []
        if vals:
            out.append(f"{label}: {', '.join(str(v) for v in vals)}")

    if clarifs:
        out.append("\n--- Clarified during intake ---")
        for c in clarifs:
            cite = f" [cites: {', '.join(c['citations'])}]" if c.get("citations") else ""
            out.append(f"Q ({c.get('kind', 'gap')}): {c['question']}")
            out.append(f"A: {c['answer']}{cite}\n")

    if concepts:
        out.append("--- Project knowledge (wiki concepts) ---")
        for k in concepts:
            out.append(f"- {k['title']}: {k['brief']}")

    return "\n".join(out)


async def build_intake_layer(project_id: uuid.UUID, db: AsyncSession) -> IntakeLayer:
    ru = (await db.execute(
        select(RequirementUnderstanding).where(RequirementUnderstanding.project_id == project_id)
    )).scalar_one_or_none()
    understanding = (ru.content_json if ru and isinstance(ru.content_json, dict) else {}) or {}

    resolved_rows = (await db.execute(
        select(GapQuestion).where(
            GapQuestion.project_id == project_id,
            GapQuestion.source == "clarifier",
            GapQuestion.resolved.is_(True),
        ).order_by(GapQuestion.ext_id)
    )).scalars().all()
    resolved_clarifications = [
        {
            "question": g.question,
            "answer": g.resolution_text or "",
            "kind": g.kind,
            "citations": g.citations or [],
            "gap_question_id": str(g.id),
        }
        for g in resolved_rows
    ]

    concept_rows = (await db.execute(
        select(ProjectWikiConcept)
        .where(ProjectWikiConcept.project_id == project_id)
        .order_by(ProjectWikiConcept.title)
    )).scalars().all()
    wiki_concepts = [
        {
            "slug": c.slug,
            "title": c.title,
            "brief": c.brief,
            "citations": [f"S:{r.get('doc_id')}:{r.get('node_id')}" for r in (c.tree_node_refs or [])],
        }
        for c in concept_rows
    ]

    # Citation index: resolve tokens -> human label (extended in P6 provenance).
    citation_index: dict = {}
    for c in wiki_concepts:
        citation_index[f"C:{c['slug']}"] = {"kind": "concept", "label": c["title"]}
    for g in resolved_clarifications:
        citation_index[f"Q:{g['gap_question_id']}"] = {"kind": "clarification", "label": g["question"][:80]}

    return IntakeLayer(
        understanding=understanding,
        resolved_clarifications=resolved_clarifications,
        wiki_concepts=wiki_concepts,
        formatted_context=_format(understanding, resolved_clarifications, wiki_concepts),
        citation_index=citation_index,
    )
