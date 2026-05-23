"""E2 Phase 3 — apps-in-scope suggestion, similar-project discovery, app-brain context."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _new_project(client, name="Payments Modernization", desc="Revamp the payments settlement flow"):
    r = await client.post("/api/projects", json={"name": name, "description": desc})
    assert r.status_code == 201
    return r.json()["data"]["id"]


# ── App suggestion ──────────────────────────────────────────────────────────────

async def test_suggest_requires_query(client):
    r = await client.get("/api/apps/suggest")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "missing_query"


async def test_suggest_lists_onboarded_apps(client):
    from app.db import AsyncSessionLocal
    from app.models.app import App

    sn = f"pay{uuid.uuid4().hex[:8]}"
    _app_pk = None
    async with AsyncSessionLocal() as db:
        app = App(name="PayHub", short_name=sn, tier=1, is_onboarded=True,
                  description="payments settlement platform")
        db.add(app)
        await db.commit()
        app_id = str(app.id)
        _app_pk = app.id

    try:
        r = await client.get("/api/apps/suggest", params={"q": "payments settlement"})
        assert r.status_code == 200
        data = r.json()["data"]
        ids = [a["id"] for a in data]
        assert app_id in ids
        payhub = next(a for a in data if a["id"] == app_id)
        # no chunks → not suggested, 0 match, but present with the projection fields
        assert payhub["suggested"] is False
        assert payhub["match_pct"] == 0
        assert "fact_count" in payhub and "corpus_doc_count" in payhub
    finally:
        async with AsyncSessionLocal() as db:
            a = await db.get(App, _app_pk)
            if a:
                await db.delete(a)
                await db.commit()


# ── Similar projects ─────────────────────────────────────────────────────────────

async def test_similar_empty_for_unique_project(client):
    pid = await _new_project(client, name="Totally Unique Initiative XYZ", desc="one of a kind")
    r = await client.get(f"/api/projects/{pid}/similar")
    assert r.status_code == 200
    # nothing else matches above threshold
    assert isinstance(r.json()["data"], list)


async def test_similar_finds_identical_project(client):
    # Two projects with identical identity text → identical mock embeddings → cosine 1.0
    name, desc = "Loan Origination Revamp", "Modernize the loan origination journey end to end"
    a = await _new_project(client, name=name, desc=desc)
    b = await _new_project(client, name=name, desc=desc)

    r = await client.get(f"/api/projects/{a}/similar")
    assert r.status_code == 200
    matches = r.json()["data"]
    match_ids = [m["source_project_id"] for m in matches]
    assert b in match_ids
    twin = next(m for m in matches if m["source_project_id"] == b)
    assert twin["match_pct"] >= 99  # identical text


# ── App-brain context loader ─────────────────────────────────────────────────────

async def test_load_app_facts_for_project(client):
    from app.db import AsyncSessionLocal
    from app.models.app import App
    from app.models.fact import AppFact
    from app.models.project import Project
    from app.models.project_intake import ProjectApp
    from app.services.projects.app_context import load_app_facts_for_project

    _app_pk = None
    _proj_pk = None
    async with AsyncSessionLocal() as db:
        app = App(name="ClaimsEzy", short_name=f"clm{uuid.uuid4().hex[:8]}", tier=2, is_onboarded=True)
        db.add(app)
        await db.flush()
        db.add(AppFact(app_id=app.id, kind="constraint", text="Max claim is 1M USD",
                       confidence="high", status="active"))
        db.add(AppFact(app_id=app.id, kind="capability", text="Supports bulk claim import",
                       confidence="medium", status="dismissed"))  # excluded (not active)
        proj = Project(name="Claims Project", description="d")
        db.add(proj)
        await db.flush()
        db.add(ProjectApp(project_id=proj.id, app_id=app.id, included=True))
        await db.commit()
        _app_pk = app.id
        _proj_pk = proj.id
        pid = proj.id

    try:
        async with AsyncSessionLocal() as db:
            facts = await load_app_facts_for_project(pid, db)
        texts = [f["text"] for f in facts]
        assert "Max claim is 1M USD" in texts
        assert "Supports bulk claim import" not in texts  # dismissed fact excluded
        assert facts[0]["app"] == "ClaimsEzy"
    finally:
        async with AsyncSessionLocal() as db:
            # Delete app first (cascades facts + project_apps), then project
            a = await db.get(App, _app_pk)
            if a:
                await db.delete(a)
                await db.commit()
            p = await db.get(Project, _proj_pk)
            if p:
                await db.delete(p)
                await db.commit()
