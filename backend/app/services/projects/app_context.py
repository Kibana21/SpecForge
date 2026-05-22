"""Load app-brain facts for a project's in-scope apps (grounding for the RU)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app import App
from app.models.fact import AppFact
from app.models.project_intake import ProjectApp


async def load_app_facts_for_project(project_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Active app-brain facts for every app marked in-scope (included) for the project.

    Used by the RU orchestrator to ground the Requirement Understanding in the
    relevant applications' knowledge. Returns plain dicts (app, kind, text,
    confidence, source_ref) for prompt construction."""
    app_ids = (
        await db.execute(
            select(ProjectApp.app_id).where(
                ProjectApp.project_id == project_id, ProjectApp.included.is_(True)
            )
        )
    ).scalars().all()
    if not app_ids:
        return []

    rows = (
        await db.execute(
            select(AppFact, App.name)
            .join(App, App.id == AppFact.app_id)
            .where(AppFact.app_id.in_(app_ids), AppFact.status == "active")
            .order_by(App.name, AppFact.kind)
        )
    ).all()

    return [
        {
            "app": name,
            "kind": fact.kind,
            "text": fact.text,
            "confidence": fact.confidence,
            "source_ref": fact.source_ref,
        }
        for fact, name in rows
    ]
