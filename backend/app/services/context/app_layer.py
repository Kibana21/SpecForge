"""App Brain layer: all in-scope app facts and wiki concepts."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.context.project_context import AppFactEntry, AppLayer


async def build_app_layer(project_id: uuid.UUID, db: AsyncSession) -> AppLayer:
    """Load every fact for every in-scope app. Never trims the fact set."""
    from app.models.app import App
    from app.models.fact import AppFact
    from app.models.project_intake import ProjectApp

    # In-scope apps ordered by tier, then name
    app_rows = (
        await db.execute(
            select(App, ProjectApp.impact_note)
            .join(ProjectApp, ProjectApp.app_id == App.id)
            .where(ProjectApp.project_id == project_id, ProjectApp.included.is_(True))
            .order_by(App.tier, App.name)
        )
    ).all()

    if not app_rows:
        return AppLayer(entries=[], total_facts=0, formatted_context="(no in-scope applications)")

    app_ids = [app.id for app, _ in app_rows]

    # All facts — load once, group by app_id
    fact_rows = (
        await db.execute(
            select(AppFact, App.name)
            .join(App, App.id == AppFact.app_id)
            .where(AppFact.app_id.in_(app_ids), AppFact.status == "active")
            .order_by(App.name, AppFact.kind)
        )
    ).all()

    facts_by_app: dict[str, dict[str, list[str]]] = {}
    for fact, app_name in fact_rows:
        facts_by_app.setdefault(app_name, {}).setdefault(fact.kind, []).append(fact.text)

    # Wiki concepts (best-effort)
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

    entries: list[AppFactEntry] = []
    total_facts = 0
    for app, impact_note in app_rows:
        by_kind = facts_by_app.get(app.name, {})
        fact_count = sum(len(v) for v in by_kind.values())
        total_facts += fact_count
        entries.append(AppFactEntry(
            app_id=str(app.id),
            app_name=app.name,
            tier=app.tier,
            domain_area=app.domain_area,
            impact_note=impact_note,
            facts_by_kind=by_kind,
            wiki_concepts=wiki_by_app.get(app.name, []),
        ))

    return AppLayer(
        entries=entries,
        total_facts=total_facts,
        formatted_context=_format_app_context(entries),
    )


def _format_app_context(entries: list[AppFactEntry]) -> str:
    if not entries:
        return "(no in-scope applications)"
    parts: list[str] = []
    for e in entries:
        tier_info = f"Tier {e.tier}" + (f", {e.domain_area}" if e.domain_area else "")
        header = f"### App Brain: {e.app_name} ({tier_info})"
        lines = [header]
        if e.impact_note:
            lines.append(f"**Impact note:** {e.impact_note}")
        for kind, texts in e.facts_by_kind.items():
            lines.append(f"**{kind.capitalize()}s:**")
            lines.extend(f"  - {t}" for t in texts)
        if e.wiki_concepts:
            lines.append("**Key wiki concepts:**")
            lines.extend(f"  - {c}" for c in e.wiki_concepts)
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
