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
_FRS_HUMAN_ID = "PRJ-QA01"
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


async def seed_validated_frs() -> None:
    """Seed PRJ-0002 with a fully validated CB→BRD→FRS chain so the Test Cases
    workspace can be generated + verified live. Idempotent."""
    from datetime import datetime, timezone
    from app.models.artifact import ArtifactDocument
    from app.models.brd import BrdBusinessRequirement
    from app.models.frs import (
        FrsAcceptanceScenario, FrsBusinessRule, FrsFunctionalRequirement,
        FrsModule, FrsModuleActor, FrsScreen, FrsSpec, FrsTraceability,
    )

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        if (await db.execute(select(Project).where(Project.human_id == _FRS_HUMAN_ID))).scalar_one_or_none():
            print(f"{_FRS_HUMAN_ID} already seeded — skipping.")
            await engine.dispose()
            return
        admin = (await db.execute(select(User).where(User.role == "platform_admin").limit(1))).scalar_one_or_none()
        if admin is None:
            print("No platform_admin user found — run `make seed` first.")
            await engine.dispose()
            return
        app = await _ensure_app(db)

        project = Project(
            name="PayHub QA Demo (validated FRS)", human_id=_FRS_HUMAN_ID,
            description="A project with a validated FRS, ready for test-case generation.",
            business_unit="Payments", app_scope="PayHub", status="draft", owner_id=admin.id,
        )
        db.add(project)
        await db.flush()
        db.add(ProjectApp(project_id=project.id, app_id=app.id, included=True))

        now = datetime.now(timezone.utc)
        cb = ArtifactDocument(project_id=project.id, artifact_type="concept_brief",
                              status="validated", validated_at=now, validated_snapshot_key="seed")
        brd = ArtifactDocument(project_id=project.id, artifact_type="brd",
                               status="validated", validated_at=now, validated_snapshot_key="seed")
        frs = ArtifactDocument(project_id=project.id, artifact_type="frs",
                               status="validated", validated_at=now, validated_snapshot_key="seed")
        db.add_all([cb, brd, frs])
        await db.flush()

        def _mix(**kw):
            return dict(version=1, is_current=True, is_locked=False, status="active", source="ai", **kw)

        # BRD business requirements (mix of priorities)
        brs = [
            ("BR-001", "Real-time settlement", "must"),
            ("BR-002", "Reject invalid transfers", "must"),
            ("BR-003", "Ledger consistency", "must"),
            ("BR-004", "Transfer history export", "should"),
        ]
        for rk, title, prio in brs:
            db.add(BrdBusinessRequirement(
                document_id=brd.id, row_key=rk, title=title, description=f"{title} requirement.",
                priority=prio, category="functional", acceptance_criteria=[], objective_refs=[],
                stakeholder_refs=[], rationale="", completeness=95, confidence="high", **_mix()))

        # FRS modules + specs. Each spec: 2 scenarios (1 negative), 1 FR, 1 rule, 1 screen.
        modules = [
            ("MOD-001", "Payments", [
                (f"M001-FRS001", "Initiate Payment", "P0", ["BR-001"]),
                (f"M001-FRS002", "Validate Transfer", "P0", ["BR-002"]),
            ]),
            ("MOD-002", "Ledger", [
                (f"M002-FRS001", "Post Ledger Entry", "P0", ["BR-003"]),
                (f"M002-FRS002", "Export History", "P1", ["BR-004"]),
            ]),
        ]
        for mkey, mname, specs in modules:
            db.add(FrsModule(document_id=frs.id, row_key=mkey, name=mname, slug=mname.lower(),
                             layer="vertical", summary=f"{mname} capability.", **_mix()))
            db.add(FrsModuleActor(document_id=frs.id, row_key=f"{mkey}-ACT-1", module_row_key=mkey,
                                  actor_name="analyst", relationship="primary_user", notes="", **_mix()))
            for skey, stitle, sprio, brefs in specs:
                db.add(FrsSpec(document_id=frs.id, row_key=skey, module_row_key=mkey, title=stitle,
                               priority=sprio, layer="vertical", br_refs=brefs,
                               narrative=f"{stitle} flow.", independent_test=f"{stitle} succeeds end to end.",
                               data_and_validation="Inputs validated; amount > 0.",
                               errors_and_edge_cases="Reject invalid input with a clear error.",
                               observability="Audit every transfer attempt.", **_mix()))
                db.add(FrsAcceptanceScenario(document_id=frs.id, row_key=f"{skey}-AS-1", spec_row_key=skey,
                                             scenario_index=1, given="a valid context", when=f"{stitle} is performed",
                                             then="the expected outcome holds", is_negative=False,
                                             fr_refs=[f"{skey}-FR-1"], **_mix()))
                db.add(FrsAcceptanceScenario(document_id=frs.id, row_key=f"{skey}-AS-2", spec_row_key=skey,
                                             scenario_index=2, given="an invalid input", when="it is submitted",
                                             then="the request is rejected with an error", is_negative=True,
                                             fr_refs=[f"{skey}-FR-1"], **_mix()))
                db.add(FrsFunctionalRequirement(document_id=frs.id, row_key=f"{skey}-FR-1", spec_row_key=skey,
                                                fr_id="FR-1", requirement_text=f"The system must {stitle.lower()} correctly.",
                                                scenario_refs=[f"{skey}-AS-1"], **_mix()))
                db.add(FrsBusinessRule(document_id=frs.id, row_key=f"{skey}-BR-1", spec_row_key=skey,
                                       rule_id="BR-1", description="Amount must be positive.",
                                       applies_to="amount", logic_decision="reject if <= 0", **_mix()))
                db.add(FrsScreen(document_id=frs.id, row_key=f"{skey}-SCR-1", spec_row_key=skey,
                                 screen_name=stitle, purpose=f"{stitle} UI", user_roles=["analyst"],
                                 layout="form", navigation="", interactive_behavior="", **_mix()))
                for br in brefs:
                    db.add(FrsTraceability(document_id=frs.id, source_table="frs_specs", source_row_key=skey,
                                           target_kind="brd_business_requirement", target_ref=br,
                                           target_label=br, confidence="high"))
        await db.commit()
        print(f"Seeded {_FRS_HUMAN_ID} ({project.name}) with a validated FRS (2 modules, 4 specs). "
              f"Open it → Test Cases → Generate.")

    await engine.dispose()


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


async def _main() -> None:
    await seed()
    await seed_validated_frs()


if __name__ == "__main__":
    asyncio.run(_main())
