"""Brain Wiki grounding for context-aware SDLC artifact generation.

Gathers compiled wiki concepts for the apps in a project's scope and formats
them as grounding context injected into the spec-generation skills. This is what
makes generated specs reflect cross-document app knowledge with provenance,
rather than being built from the project's requirements alone.
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.project_intake import ProjectApp
from app.models.wiki import AppWikiConcept

log = logging.getLogger(__name__)

_DEFAULT_BUDGET = 15_000


async def gather_app_brain_context(
    db: AsyncSession, project_id: uuid.UUID, char_budget: int = _DEFAULT_BUDGET
) -> str:
    """Format compiled wiki concepts for a project's in-scope apps as a grounding
    block. Returns "" when no in-scope app has a compiled wiki.

    Includes full concept bodies until the char budget is reached, then degrades
    to one-line briefs so every concept is at least named.
    """
    app_rows = (await db.execute(
        select(App.id, App.name)
        .join(ProjectApp, ProjectApp.app_id == App.id)
        .where(ProjectApp.project_id == project_id, ProjectApp.included.is_(True))
        .order_by(App.name)
    )).all()
    if not app_rows:
        return ""

    blocks: list[str] = []
    used = 0
    for app_id, app_name in app_rows:
        concepts = (await db.execute(
            select(AppWikiConcept)
            .where(AppWikiConcept.app_id == app_id)
            .order_by(AppWikiConcept.title)
        )).scalars().all()
        if not concepts:
            continue

        lines = [f"## App Brain: {app_name}"]
        for c in concepts:
            full = f"### {c.title}\n{(c.content_md or '').strip()}"
            brief = f"### {c.title}\n{c.brief}"
            entry = full if (used + len(full)) <= char_budget else brief
            lines.append(entry)
            used += len(entry)
        blocks.append("\n\n".join(lines))
        if used >= char_budget:
            break

    return "\n\n".join(blocks)
