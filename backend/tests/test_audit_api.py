"""Audit Log API — RBAC, filtering, pagination, actor resolution, summary, CSV export."""
import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _emit(event: str, **kw):
    from app.core import audit
    from app.db import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await audit.emit(db, event=event, **kw)
        await db.commit()


async def test_audit_requires_privileged_role(client):
    from app.core.rbac import get_current_user
    from app.main import app
    from app.models.user import User

    # platform_admin (conftest default) → 200
    assert (await client.get("/api/audit")).status_code == 200

    prev = app.dependency_overrides[get_current_user]
    # an ordinary role → 403 on every audit route
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid.uuid4(), email="ba@t.test", display_name="BA", role="business_analyst", status="active")
    assert (await client.get("/api/audit")).status_code == 403
    assert (await client.get("/api/audit/summary")).status_code == 403
    assert (await client.get("/api/audit/export.csv")).status_code == 403

    # compliance_reviewer → allowed
    app.dependency_overrides[get_current_user] = lambda: User(
        id=uuid.uuid4(), email="cr@t.test", display_name="CR", role="compliance_reviewer", status="active")
    assert (await client.get("/api/audit")).status_code == 200

    app.dependency_overrides[get_current_user] = prev


async def test_audit_list_filters_categorize_and_resolve_actor(client):
    from sqlalchemy import delete
    from app.core import audit
    from app.core.security import hash_password
    from app.db import AsyncSessionLocal
    from app.models.user import User

    pid = str(uuid.uuid4())  # unique tag to isolate this test's rows from the shared DB
    actor = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(User(id=actor, email=f"actor-{actor}@t.test", display_name="Audit Actor",
                    password_hash=hash_password("x"), role="app_owner", status="active"))
        await db.commit()
    ghost = str(uuid.uuid4())  # actor_id with no matching user → "Unknown"
    async with AsyncSessionLocal() as db:
        await audit.emit(db, event="login_failed", project_id=pid, actor_id=str(actor))
        await audit.emit(db, event="understanding.validated", project_id=pid, actor_id=str(actor))
        await audit.emit(db, event="app.deleted", project_id=pid, actor_id=ghost)
        await db.commit()

    # all three, newest first, with computed label/category/severity
    body = (await client.get(f"/api/audit?project_id={pid}")).json()
    assert body["meta"]["total"] == 3
    assert {i["event"] for i in body["data"]} == {"login_failed", "understanding.validated", "app.deleted"}

    # category=security includes destructive (app.deleted)
    evs = {i["event"] for i in (await client.get(f"/api/audit?project_id={pid}&category=security")).json()["data"]}
    assert evs == {"login_failed", "app.deleted"}
    # category=compliance
    evs = {i["event"] for i in (await client.get(f"/api/audit?project_id={pid}&category=compliance")).json()["data"]}
    assert evs == {"understanding.validated"}

    # exact event filter + severity/label + unresolvable actor renders "Unknown"
    d = (await client.get(f"/api/audit?project_id={pid}&event=app.deleted")).json()["data"]
    assert len(d) == 1 and d[0]["label"] == "App deleted" and d[0]["severity"] == "danger"
    assert d[0]["actor_name"] == "Unknown"

    # actor resolution (UUID → display name)
    d = (await client.get(f"/api/audit?project_id={pid}&event=login_failed")).json()["data"][0]
    assert d["actor_name"] == "Audit Actor" and d["category"] == "security"

    # free-text search by actor name (scoped to this project)
    body = (await client.get(f"/api/audit?project_id={pid}&q=Audit")).json()
    assert body["meta"]["total"] == 2

    # pagination
    body = (await client.get(f"/api/audit?project_id={pid}&limit=2")).json()
    assert len(body["data"]) == 2 and body["meta"]["total"] == 3 and body["meta"]["limit"] == 2

    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.id == actor))
        await db.commit()


async def test_audit_summary(client):
    await _emit("login_failed")
    s = (await client.get("/api/audit/summary")).json()["data"]
    assert s["failed_logins_24h"] >= 1
    assert s["events_today"] >= 1


async def test_audit_export_csv(client):
    pid = str(uuid.uuid4())
    await _emit("app.deleted", project_id=pid)

    r = await client.get(f"/api/audit/export.csv?project_id={pid}")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.text.startswith("timestamp,event,label")
    assert "app.deleted" in r.text

    # the export itself is audited
    body = (await client.get("/api/audit?event=audit.exported&limit=1")).json()
    assert body["meta"]["total"] >= 1
