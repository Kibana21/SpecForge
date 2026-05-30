"""Full-context intake grounding (G8).

Single source of truth for what the Requirement Understanding synthesis AND the
Clarification Engine reason over: the brief, ALL uploaded documents (breadth +
targeted depth), the associated App Brain (wiki concepts + facts), and the prior
interview Q&A. See .claude/plans/E2-intelligent-intake.md §6.0.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import ArtifactDocument, CbDiscoverEnhancedBrief
from app.models.project import Project
from app.models.understanding import InterviewMessage


async def _brief(project: Project, db: AsyncSession) -> str:
    parts: list[str] = []
    if project.description:
        parts.append(project.description.strip())
    # Latest enhanced brief from the Concept Brief discover flow, if present.
    ad_id = (await db.execute(
        select(ArtifactDocument.id).where(
            ArtifactDocument.project_id == project.id,
            ArtifactDocument.artifact_type == "concept_brief",
        )
    )).scalar_one_or_none()
    if ad_id is not None:
        eb = (await db.execute(
            select(CbDiscoverEnhancedBrief)
            .where(CbDiscoverEnhancedBrief.artifact_document_id == ad_id)
            .order_by(CbDiscoverEnhancedBrief.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if eb and eb.enhanced_brief:
            parts.append("Enhanced brief:\n" + eb.enhanced_brief.strip())
    return "\n\n".join(parts) or "(no brief provided)"


async def _qa(project_id: uuid.UUID, db: AsyncSession) -> str:
    rows = (await db.execute(
        select(InterviewMessage)
        .where(
            InterviewMessage.project_id == project_id,
            InterviewMessage.role.in_(("question", "user")),
        )
        .order_by(InterviewMessage.seq)
    )).scalars().all()
    lines = [f"{'Q' if m.role == 'question' else 'A'}: {m.content}" for m in rows]
    return "\n".join(lines) or "(none yet)"


async def _app_brain(project_id: uuid.UUID, db: AsyncSession) -> str:
    """In-scope App Brain wiki concepts + facts, formatted for grounding."""
    from app.services.projects.app_context import load_app_facts_for_project
    from app.services.rag.wiki_grounding import gather_app_brain_context

    wiki_ctx = ""
    try:
        wiki_ctx = await gather_app_brain_context(db, project_id)
    except Exception:  # noqa: BLE001 — grounding is best-effort
        wiki_ctx = ""

    facts = await load_app_facts_for_project(project_id, db)
    # Positional `[F#]` markers (paired with the matching `[S#]` source markers)
    # — the RU/clarifier cite these inline and the UI resolves them against the
    # generated `citations` array. Small ints echo reliably; UUIDs do not.
    facts_str = "\n".join(
        f"[F{i}] ({f['kind']}, {f['confidence']}) {f['app']}: {f['text']}"
        for i, f in enumerate(facts, start=1)
    )
    return "\n\n".join(p for p in (wiki_ctx, facts_str) if p) or "(no app brain)"


async def build_intake_grounding(project_id: uuid.UUID, db: AsyncSession) -> dict:
    """Assemble the complete intake context once, for RU + clarifier + triggers."""
    from app.config import get_settings
    from app.services.context.docs_layer import build_docs_layer, depth_search

    project = await db.get(Project, project_id)
    if project is None:
        return {"brief": "", "doc_breadth": "", "doc_depth": "", "app_brain": "", "qa": "(none yet)"}

    settings = get_settings()
    probe = f"{project.name}. {project.description or ''}".strip()

    docs = await build_docs_layer(project_id, db)
    doc_breadth = docs.outline_text or "(no document outlines)"
    try:
        doc_depth = await depth_search(project_id, db, probe, top_k=settings.tree_search_top_k)
    except TypeError:
        doc_depth = await depth_search(project_id, db, probe)
    except Exception:  # noqa: BLE001
        doc_depth = ""

    return {
        "brief": await _brief(project, db),
        "doc_breadth": doc_breadth,
        "doc_depth": doc_depth or "(no matching sections)",
        "app_brain": await _app_brain(project_id, db),
        "qa": await _qa(project_id, db),
    }
