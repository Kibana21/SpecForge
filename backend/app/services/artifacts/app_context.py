"""Compose impacted-apps context for artifact grounding."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.fact import AppFact
from app.models.project_intake import ProjectApp


async def gather_impacted_apps_context(project_id: uuid.UUID, db: AsyncSession) -> str:
    """Return a formatted string describing in-scope apps for prompt grounding.

    Includes: app identity (name, tier, domain), impact_note, facts grouped by kind,
    and wiki concepts if available. Returns empty string when no apps are in scope.
    """
    rows = (
        await db.execute(
            select(ProjectApp, App)
            .join(App, App.id == ProjectApp.app_id)
            .where(ProjectApp.project_id == project_id, ProjectApp.included.is_(True))
            .order_by(App.tier, App.name)
        )
    ).all()

    if not rows:
        return ""

    app_ids = [pa.app_id for pa, _ in rows]
    facts_rows = (
        await db.execute(
            select(AppFact, App.name)
            .join(App, App.id == AppFact.app_id)
            .where(AppFact.app_id.in_(app_ids), AppFact.status == "active")
            .order_by(App.name, AppFact.kind)
        )
    ).all()

    facts_by_app: dict[str, list[AppFact]] = {}
    for fact, app_name in facts_rows:
        facts_by_app.setdefault(app_name, []).append(fact)

    # Try to load wiki concepts (best-effort — may not exist)
    wiki_by_app: dict[str, list[str]] = {}
    try:
        from app.models.wiki import AppWikiConcept
        wiki_rows = (
            await db.execute(
                select(AppWikiConcept, App.name)
                .join(App, App.id == AppWikiConcept.app_id)
                .where(AppWikiConcept.app_id.in_(app_ids))
                .order_by(App.name, AppWikiConcept.title)
            )
        ).all()
        for concept, app_name in wiki_rows:
            wiki_by_app.setdefault(app_name, []).append(f"{concept.title}: {concept.brief}")
    except Exception:  # noqa: BLE001
        pass

    parts: list[str] = []
    for pa, app in rows:
        header = f"### {app.name} (Tier {app.tier}{f', {app.domain_area}' if app.domain_area else ''})"
        lines = [header]
        if pa.impact_note:
            lines.append(f"**Impact note:** {pa.impact_note}")
        app_facts = facts_by_app.get(app.name, [])
        if app_facts:
            by_kind: dict[str, list[str]] = {}
            for f in app_facts:
                by_kind.setdefault(f.kind, []).append(f.text)
            for kind, texts in by_kind.items():
                lines.append(f"**{kind.capitalize()}s:**")
                lines.extend(f"  - {t}" for t in texts)
        wiki_concepts = wiki_by_app.get(app.name, [])
        if wiki_concepts:
            lines.append("**Key wiki concepts:**")
            lines.extend(f"  - {c}" for c in wiki_concepts[:5])
        parts.append("\n".join(lines))

    return "\n\n".join(parts)
