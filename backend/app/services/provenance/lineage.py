"""Provenance / lineage (E2).

Assembles the intake provenance spine from existing data — no new tables:
    Documents → Wiki concepts (via concept.tree_node_refs)
              → Clarifications (via clarification.citations C:/S: tokens)

Powers the LineageMap (forward "impact" / backward "provenance") and trace-chip
drill-downs. The downstream Artifacts column (CB/BRD/FRS rows tracing back to
intake) is a follow-up: it needs generators to emit traceability rows with the
intake target_kinds, plus a guarded enum migration. See
.claude/plans/E2-intelligent-intake.md §A9.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project_wiki import ProjectWikiConcept


def _docs_from_citations(citations: list[str]) -> set[str]:
    out: set[str] = set()
    for tok in citations or []:
        if tok.startswith("S:"):
            parts = tok.split(":")
            if len(parts) >= 2 and parts[1]:
                out.add(parts[1])
    return out


def _concepts_from_citations(citations: list[str]) -> set[str]:
    return {tok[2:] for tok in (citations or []) if tok.startswith("C:")}


async def build_lineage(project_id: uuid.UUID, db: AsyncSession) -> dict:
    """Return the project's intake lineage as three columns + the edges between
    them, ready for the LineageMap. All derived from existing rows."""
    docs = (await db.execute(
        select(Document.id, Document.filename).where(Document.project_id == project_id)
    )).all()
    doc_label = {str(d_id): name for d_id, name in docs}

    concepts = (await db.execute(
        select(ProjectWikiConcept).where(ProjectWikiConcept.project_id == project_id)
        .order_by(ProjectWikiConcept.title)
    )).scalars().all()

    clarifs = (await db.execute(
        select(GapQuestion).where(
            GapQuestion.project_id == project_id, GapQuestion.source == "clarifier"
        ).order_by(GapQuestion.ext_id)
    )).scalars().all()

    concept_nodes = [
        {
            "slug": c.slug,
            "title": c.title,
            # source_doc_ids is always recorded; tree_node_refs adds section-level
            # grounding when a PageIndex tree exists.
            "doc_ids": sorted(
                {str(d) for d in (c.source_doc_ids or [])}
                | {str(r.get("doc_id")) for r in (c.tree_node_refs or []) if r.get("doc_id")}
            ),
        }
        for c in concepts
    ]
    valid_slugs = {c.slug for c in concepts}

    clarification_nodes = [
        {
            "id": str(g.id),
            "question": g.question,
            "kind": g.kind,
            "severity": g.severity,
            "resolved": g.resolved,
            "concept_slugs": sorted(_concepts_from_citations(g.citations) & valid_slugs),
            "doc_ids": sorted(_docs_from_citations(g.citations) & set(doc_label)),
        }
        for g in clarifs
    ]

    # Only surface documents that actually participate in the lineage, plus any
    # doc that has a wiki summary (i.e. was compiled) — keeps the map relevant.
    referenced_docs: set[str] = set()
    for c in concept_nodes:
        referenced_docs.update(c["doc_ids"])
    for q in clarification_nodes:
        referenced_docs.update(q["doc_ids"])
    document_nodes = [
        {"id": did, "label": doc_label.get(did, did)}
        for did in sorted(referenced_docs, key=lambda d: doc_label.get(d, d))
    ] or [{"id": did, "label": name} for did, name in [(str(i), n) for i, n in docs]]

    return {
        "documents": document_nodes,
        "concepts": concept_nodes,
        "clarifications": clarification_nodes,
    }
