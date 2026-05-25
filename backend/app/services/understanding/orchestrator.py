"""Requirement Understanding orchestrator.

Stateless re-synthesis: every turn rebuilds the RU from the project's reasoning
source sections + in-scope app facts + the full accumulated interview Q&A. This
keeps it idempotent and robust (an answer simply adds to the Q&A and re-runs).
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import audit
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.project_intake import Assumption
from app.models.project_source import DocumentTree
from app.models.understanding import InterviewMessage, RequirementUnderstanding
from app.services.corpus_index import IndexedDoc, RetrievedSection, get_corpus_index_provider
from app.services.projects.app_context import load_app_facts_for_project
from app.services.skills.dspy_intake import run_requirement_understanding

log = logging.getLogger(__name__)

_SKILL = "requirement_understanding"


async def _retrieve_project_sections(
    project_id: uuid.UUID,
    query: str,
    top_k: int,
    db: AsyncSession,
    document_ids: list[uuid.UUID] | None = None,
) -> list[RetrievedSection]:
    stmt = (
        select(DocumentTree, Document.filename)
        .join(Document, Document.id == DocumentTree.document_id)
        .where(DocumentTree.project_id == project_id)
    )
    if document_ids is not None:
        stmt = stmt.where(DocumentTree.document_id.in_(document_ids))
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []
    docs = [
        IndexedDoc(document_id=t.document_id, doc_name=name, tree=t.tree_json, page_texts=t.page_texts)
        for t, name in rows
    ]
    return await get_corpus_index_provider().tree_search(query=query, docs=docs, top_k=top_k)


def _format_sections(sections: list[RetrievedSection]) -> str:
    parts = []
    for i, s in enumerate(sections, start=1):
        parts.append(f"[S{i}] {s.doc_name} › {s.title}\n{s.text[:1200]}")
    return "\n\n".join(parts)


def _format_facts(facts: list[dict]) -> str:
    return "\n".join(
        f"[F{i}] ({f['kind']}, {f['confidence']}) {f['app']}: {f['text']}"
        for i, f in enumerate(facts, start=1)
    )


async def _gather_qa(project_id: uuid.UUID, db: AsyncSession) -> str:
    rows = (
        await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.project_id == project_id, InterviewMessage.role.in_(("question", "user")))
            .order_by(InterviewMessage.seq)
        )
    ).scalars().all()
    lines = []
    for m in rows:
        prefix = "Q" if m.role == "question" else "A"
        lines.append(f"{prefix}: {m.content}")
    return "\n".join(lines)


async def _next_seq(project_id: uuid.UUID, db: AsyncSession) -> int:
    cur = await db.scalar(
        select(func.coalesce(func.max(InterviewMessage.seq), 0)).where(
            InterviewMessage.project_id == project_id
        )
    )
    return (cur or 0) + 1


async def generate(project_id: uuid.UUID, db: AsyncSession, provider) -> dict | None:
    """Synthesize (or re-synthesize) the RU and persist it + the interview turn."""
    project = await db.get(Project, project_id)
    if project is None:
        return None

    settings = get_settings()
    probe = f"{project.name}. {project.description or ''}".strip()
    sections = await _retrieve_project_sections(project_id, probe, settings.tree_search_top_k, db)
    facts = await load_app_facts_for_project(project_id, db)
    qa = await _gather_qa(project_id, db)

    result = await run_requirement_understanding(
        project_name=project.name,
        business_unit=project.business_unit or "—",
        description=project.description or "—",
        source_sections=_format_sections(sections) or "(no source sections)",
        app_facts=_format_facts(facts) or "(no app facts)",
        qa_pairs=qa or "(none yet)",
    )

    await _persist(project, result, db)
    log.info("ru_generated project_id=%s sections=%d facts=%d", project_id, len(sections), len(facts))
    return result


async def incorporate_answer(
    project_id: uuid.UUID, answer: str, db: AsyncSession, provider, seq: int | None = None
) -> dict | None:
    """Append the user's answer to the transcript and re-synthesize the RU."""
    next_seq = await _next_seq(project_id, db)
    db.add(InterviewMessage(project_id=project_id, understanding_id=await _ru_id(project_id, db),
                            role="user", content=answer, seq=next_seq))
    await db.commit()
    return await generate(project_id, db, provider)


async def _ru_id(project_id: uuid.UUID, db: AsyncSession) -> uuid.UUID:
    ru = (
        await db.execute(
            select(RequirementUnderstanding).where(RequirementUnderstanding.project_id == project_id)
        )
    ).scalar_one_or_none()
    if ru is None:
        ru = RequirementUnderstanding(project_id=project_id, status="in_interview")
        db.add(ru)
        await db.flush()
    return ru.id


async def _persist(project: Project, result: dict, db: AsyncSession) -> None:
    ru = (
        await db.execute(
            select(RequirementUnderstanding).where(RequirementUnderstanding.project_id == project.id)
        )
    ).scalar_one_or_none()
    if ru is None:
        ru = RequirementUnderstanding(project_id=project.id)
        db.add(ru)
        await db.flush()

    ru.objective = result.get("objective")
    ru.content_json = result
    ru.field_confidence = result.get("field_confidence", {})
    ru.status = "in_interview"
    ru.version_number = (ru.version_number or 0) + 1

    # Append transcript: an 'understanding' snapshot + a 'question' per open question.
    seq = await _next_seq(project.id, db)
    citations = result.get("citations", [])
    db.add(InterviewMessage(project_id=project.id, understanding_id=ru.id, role="understanding",
                            content=result.get("objective") or "Updated understanding.",
                            citations=citations, seq=seq))
    seq += 1
    for oq in result.get("open_questions", []):
        db.add(InterviewMessage(project_id=project.id, understanding_id=ru.id, role="question",
                                content=oq.get("question", ""), seq=seq))
        seq += 1

    # Replace assumptions + interview gap-questions (re-synthesis supersedes prior).
    await db.execute(delete(Assumption).where(Assumption.project_id == project.id))
    for i, a in enumerate(result.get("assumptions", []), start=1):
        db.add(Assumption(project_id=project.id, ext_id=f"A-{i:03d}", text=a.get("text", ""),
                          confidence=a.get("confidence", "medium"), source_ref=a.get("source_ref"),
                          status="open"))

    await db.execute(
        delete(GapQuestion).where(GapQuestion.project_id == project.id, GapQuestion.source == "interview")
    )
    for i, oq in enumerate(result.get("open_questions", []), start=1):
        db.add(GapQuestion(project_id=project.id, ext_id=f"Q-{i:03d}", question=oq.get("question", ""),
                           category="scope", severity="minor", source="interview", section=oq.get("field")))

    await audit.emit(db, event="understanding.generated", actor_id=None,
                     metadata={"project_id": str(project.id), "skill": _SKILL})
    await db.commit()
