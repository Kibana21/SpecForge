"""Fact resolver (E2 traceability).

The `F:<app_fact_id>` citation token cited in intake grounding / clarifications
must resolve to its App Brain fact — scoped to the project's in-scope apps so a
fact can't be read across projects. Mirrors the load_app_facts test setup.
"""
import uuid

import pytest

from app.db import AsyncSessionLocal


def _sn() -> str:
    return f"clm{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
async def test_resolve_fact_scoped_to_project(client):
    from app.models.app import App
    from app.models.fact import AppFact
    from app.models.project import Project
    from app.models.project_intake import ProjectApp

    app_pk = proj_pk = other_proj_pk = fact_pk = None
    async with AsyncSessionLocal() as db:
        app = App(name="ClaimsEzy", short_name=_sn(), tier=2, is_onboarded=True)
        db.add(app)
        await db.flush()
        fact = AppFact(app_id=app.id, kind="constraint", text="Max claim is 1M USD",
                       confidence="high", status="active", source_ref="policy.pdf §2")
        db.add(fact)
        proj = Project(name="Claims Project", description="d")
        other = Project(name="Other Project", description="d")
        db.add_all([proj, other])
        await db.flush()
        db.add(ProjectApp(project_id=proj.id, app_id=app.id, included=True))
        await db.commit()
        app_pk, proj_pk, other_proj_pk, fact_pk = app.id, proj.id, other.id, fact.id

    try:
        # In-scope project resolves the fact with its provenance.
        r = await client.get(f"/api/projects/{proj_pk}/facts/{fact_pk}")
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["id"] == str(fact_pk)
        assert data["app"] == "ClaimsEzy"
        assert data["kind"] == "constraint"
        assert data["text"] == "Max claim is 1M USD"
        assert data["source_ref"] == "policy.pdf §2"

        # A project that doesn't include the app cannot read the fact (404).
        r2 = await client.get(f"/api/projects/{other_proj_pk}/facts/{fact_pk}")
        assert r2.status_code == 404

        # Positional resolver: F1 → the first (only) in-scope fact.
        r3 = await client.get(f"/api/projects/{proj_pk}/facts/by-index/1")
        assert r3.status_code == 200, r3.text
        assert r3.json()["data"]["text"] == "Max claim is 1M USD"
        # Out-of-range index → 404 (not a crash).
        r4 = await client.get(f"/api/projects/{proj_pk}/facts/by-index/999")
        assert r4.status_code == 404
    finally:
        async with AsyncSessionLocal() as db:
            a = await db.get(App, app_pk)
            if a:
                await db.delete(a)
                await db.commit()
            for pk in (proj_pk, other_proj_pk):
                p = await db.get(Project, pk)
                if p:
                    await db.delete(p)
                    await db.commit()
