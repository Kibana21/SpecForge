"""Project CRUD API tests. Requires PostgreSQL with schema applied."""
import pytest

pytestmark = pytest.mark.asyncio


async def test_create_project(client):
    r = await client.post("/api/projects", json={"name": "Alpha", "description": "desc"})
    assert r.status_code == 201
    body = r.json()
    assert body["error"] is None
    assert body["data"]["name"] == "Alpha"
    assert "id" in body["data"]


async def test_create_project_empty_name_rejected(client):
    r = await client.post("/api/projects", json={"name": "   "})
    assert r.status_code == 422


async def test_list_projects(client):
    await client.post("/api/projects", json={"name": "ListTest"})
    r = await client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["data"], list)
    assert body["meta"]["total"] >= 1


async def test_get_project_detail(client):
    r = await client.post("/api/projects", json={"name": "Detail"})
    project_id = r.json()["data"]["id"]

    r = await client.get(f"/api/projects/{project_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == project_id
    assert "documents" in data
    assert "latest_specs" in data
    assert "gap_count" in data


async def test_get_nonexistent_project_returns_404(client):
    r = await client.get("/api/projects/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_delete_project_soft_deletes(client):
    r = await client.post("/api/projects", json={"name": "ToDelete"})
    project_id = r.json()["data"]["id"]

    r = await client.delete(f"/api/projects/{project_id}")
    assert r.status_code == 200

    r = await client.get(f"/api/projects/{project_id}")
    assert r.status_code == 404


async def test_deleted_project_absent_from_list(client):
    r = await client.post("/api/projects", json={"name": "HiddenProject"})
    project_id = r.json()["data"]["id"]
    await client.delete(f"/api/projects/{project_id}")

    r = await client.get("/api/projects")
    ids = [p["id"] for p in r.json()["data"]]
    assert project_id not in ids
