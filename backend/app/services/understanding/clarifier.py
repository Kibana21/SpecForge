"""Clarification Engine (E2).

Reasons over the project wiki concepts + detected contradictions + the full
intake grounding to produce high-signal contradiction/ambiguity/gap questions,
each citing its sources. Persists them as GapQuestion(source="clarifier") —
disjoint from RU's source="interview" rows. Idempotent: replaces only UNRESOLVED
clarifier rows, preserving answered ones. See .claude/plans/E2-intelligent-intake.md.
"""
from __future__ import annotations

import logging
import uuid
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.project_wiki import ProjectWikiConcept
from app.services.skills.dspy_intake import run_corpus_clarifier
from app.services.understanding.grounding import build_intake_grounding

log = logging.getLogger(__name__)

_CLARIFIER_SOURCE = "clarifier"


async def run_clarification(
    project_id: uuid.UUID, db: AsyncSession, *, trigger: Literal["interview", "new_document"]
) -> list[dict]:
    """Generate + persist clarification questions for a project. Returns the items."""
    project = await db.get(Project, project_id)
    if project is None:
        return []

    concepts = (await db.execute(
        select(ProjectWikiConcept).where(ProjectWikiConcept.project_id == project_id)
    )).scalars().all()

    # Detect cross-concept contradictions via the wiki linter (reused).
    contradictions: list[dict] = []
    if len(concepts) >= 2:
        from app.services.skills.wiki_compiler.dspy_wiki import ConceptForLint, run_wiki_lint
        valid_slugs = {c.slug for c in concepts}
        try:
            payload = [
                ConceptForLint(slug=c.slug, title=c.title, content_md=(c.content_md or "")[:4000])
                for c in concepts
            ]
            result = await run_wiki_lint(project.name, payload)
            raw = result.get("contradictions", []) if isinstance(result, dict) else []
            contradictions = [
                x for x in raw
                if x.get("concept_a") in valid_slugs and x.get("concept_b") in valid_slugs
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("clarifier wiki_lint failed project_id=%s error=%s", project_id, exc)

    grounding = await build_intake_grounding(project_id, db)
    wiki_concepts_str = "\n".join(
        f"{c.slug} · {c.title} — {c.brief}" for c in concepts
    ) or "(no concepts yet)"
    contradictions_str = "\n".join(
        f"- {x.get('concept_a')} ⟂ {x.get('concept_b')}: {x.get('issue', '')}"
        for x in contradictions
    ) or "(none)"

    result = await run_corpus_clarifier(
        project_name=project.name,
        wiki_concepts=wiki_concepts_str,
        detected_contradictions=contradictions_str,
        brief_context=grounding["brief"],
        app_brain=grounding["app_brain"],
        qa_pairs=grounding["qa"],
    )
    items = (result.get("items", []) if isinstance(result, dict) else []) or []

    # Idempotent replace of UNRESOLVED clarifier rows; resolved answers preserved.
    await db.execute(
        delete(GapQuestion).where(
            GapQuestion.project_id == project_id,
            GapQuestion.source == _CLARIFIER_SOURCE,
            GapQuestion.resolved.is_(False),
        )
    )
    for i, it in enumerate(items, start=1):
        citations = it.get("citations", []) or []
        db.add(GapQuestion(
            project_id=project_id,
            ext_id=f"CL-{i:03d}",
            question=it.get("question", ""),
            category=it.get("category", "scope"),
            severity=it.get("severity", "minor"),
            source=_CLARIFIER_SOURCE,
            section=(citations[0] if citations else None),
            kind=it.get("kind"),
            citations=citations,
            rationale=it.get("rationale", ""),
        ))
    await db.commit()

    log.info(
        "clarification_run project_id=%s trigger=%s concepts=%d contradictions=%d items=%d",
        project_id, trigger, len(concepts), len(contradictions), len(items),
    )
    return items
