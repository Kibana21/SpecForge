"""E2 Phase 4 — portfolio search/views/grouping + triage."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _mk(client, name, **extra):
    r = await client.post("/api/projects", json={"name": name, "description": "d"})
    assert r.status_code == 201
    pid = r.json()["data"]["id"]
    if extra:
        from app.db import AsyncSessionLocal
        from app.models.project import Project
        async with AsyncSessionLocal() as db:
            p = await db.get(Project, uuid.UUID(pid))
            for k, v in extra.items():
                setattr(p, k, v)
            await db.commit()
    return pid


async def test_portfolio_search(client):
    uniq = uuid.uuid4().hex[:8]
    pid = await _mk(client, f"PayHub Modernization {uniq}", business_unit="Payments")
    r = await client.get("/api/projects", params={"q": uniq})
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()["data"]]
    assert pid in ids
    # search that matches nothing
    r2 = await client.get("/api/projects", params={"q": "zzz-no-match-zzz"})
    assert pid not in [p["id"] for p in r2.json()["data"]]


async def test_portfolio_view_high_priority(client):
    pid = await _mk(client, f"Critical Init {uuid.uuid4().hex[:6]}", priority="critical")
    r = await client.get("/api/projects", params={"view": "high_priority"})
    assert r.status_code == 200
    assert pid in [p["id"] for p in r.json()["data"]]
    # finalized view should NOT include it (status defaults to draft)
    r2 = await client.get("/api/projects", params={"view": "finalized"})
    assert pid not in [p["id"] for p in r2.json()["data"]]


async def test_saved_view_counts(client):
    await _mk(client, f"VC {uuid.uuid4().hex[:6]}", priority="high")
    r = await client.get("/api/projects/views")
    assert r.status_code == 200
    views = {v["view"]: v for v in r.json()["data"]}
    assert set(views) == {"all", "mine", "needs_review", "stale", "high_priority", "finalized"}
    assert views["high_priority"]["count"] >= 1
    assert views["all"]["count"] >= views["high_priority"]["count"]


async def test_portfolio_group_by_status(client):
    await _mk(client, f"GB {uuid.uuid4().hex[:6]}")
    r = await client.get("/api/projects", params={"group_by": "status"})
    assert r.status_code == 200
    meta = r.json()["meta"]
    assert "groups" in meta
    keys = [g["key"] for g in meta["groups"]]
    assert "draft" in keys  # new projects default to draft
    for g in meta["groups"]:
        assert {"key", "count", "stale", "review", "finalized"} <= set(g)


async def test_triage_surfaces_pending_validation(client):
    """A project with an indexed source + unvalidated RU shows an 'approval' triage item."""
    from app.db import AsyncSessionLocal
    from app.models.document import Document

    # create_project already makes a draft (unvalidated) RU; add an indexed source.
    pid = await _mk(client, f"Triage Proj {uuid.uuid4().hex[:6]}")
    async with AsyncSessionLocal() as db:
        db.add(Document(project_id=uuid.UUID(pid), filename="s.txt", mime_type="text/plain",
                        size_bytes=10, storage_path="/tmp/x", parse_status="done",
                        indexing_status="done"))
        await db.commit()

    r = await client.get("/api/triage")
    assert r.status_code == 200
    body = r.json()
    kinds = {(i["project_id"], i["kind"]) for i in body["data"]}
    assert (pid, "approval") in kinds
    assert "computed_at" in body["meta"]
