#!/usr/bin/env python3
"""
Seed a demo project (PRJ-0001) with an app in scope + a generated Requirement
Understanding, using the MOCK providers (no Vertex calls / cost). Idempotent.

Run AFTER `make seed` (needs the platform_admin user). Usage (from repo root):
    cd backend && .venv/bin/python scripts/seed_projects.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force mock providers BEFORE app.config is imported/cached.
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("CORPUS_INDEX_PROVIDER", "mock")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models.app import App  # noqa: E402
from app.models.fact import AppFact  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.project_intake import ProjectApp  # noqa: E402
from app.models.understanding import RequirementUnderstanding  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.llm.mock_provider import MockProvider  # noqa: E402
from app.services.understanding.orchestrator import generate  # noqa: E402

_HUMAN_ID = "PRJ-0001"
_APP_SHORT = "payhubdemo"


async def _ensure_app(db: AsyncSession) -> App:
    app = (await db.execute(select(App).where(App.short_name == _APP_SHORT))).scalar_one_or_none()
    if app:
        return app
    app = App(name="PayHub", short_name=_APP_SHORT, tier=1, is_onboarded=True,
              description="Payments settlement platform", domain_area="Payments",
              owner_team="Payments Eng", environments=["Prod", "UAT", "DR"])
    db.add(app)
    await db.flush()
    db.add_all([
        AppFact(app_id=app.id, kind="capability", text="Processes card and bank transfers with real-time settlement.",
                confidence="high", status="active"),
        AppFact(app_id=app.id, kind="constraint", text="Transactions are capped at 10 million USD per instruction.",
                confidence="high", status="active"),
        AppFact(app_id=app.id, kind="integration", text="Integrates with SWIFT MT103 for cross-border transfers.",
                confidence="medium", status="active"),
    ])
    return app


async def seed() -> None:
    settings = get_settings()
    assert settings.llm_provider == "mock", "seed must run with LLM_PROVIDER=mock"
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        if (await db.execute(select(Project).where(Project.human_id == _HUMAN_ID))).scalar_one_or_none():
            print(f"{_HUMAN_ID} already seeded — skipping.")
            await engine.dispose()
            return

        admin = (await db.execute(select(User).where(User.role == "platform_admin").limit(1))).scalar_one_or_none()
        if admin is None:
            print("No platform_admin user found — run `make seed` first.")
            await engine.dispose()
            return

        app = await _ensure_app(db)
        project = Project(
            name="PayHub Settlement Modernization", human_id=_HUMAN_ID,
            description="Modernize the PayHub settlement flow for real-time settlement.",
            business_unit="Payments", app_scope="PayHub", status="draft", owner_id=admin.id,
        )
        db.add(project)
        await db.flush()
        db.add(ProjectApp(project_id=project.id, app_id=app.id, included=True))
        db.add(RequirementUnderstanding(project_id=project.id, status="draft"))
        await db.commit()

        await generate(project.id, db, MockProvider())
        print(f"Seeded {_HUMAN_ID} ({project.name}) with app '{app.name}' in scope + generated RU.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
