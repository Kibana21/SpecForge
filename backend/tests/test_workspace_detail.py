"""E2 Phase 6 — workspace detail panels, quality heuristics, stage map, assumptions."""
import pytest

pytestmark = pytest.mark.asyncio


async def _project_with_ru(client) -> str:
    r = await client.post("/api/projects", json={"name": "WS Detail", "description": "payments work"})
    pid = r.json()["data"]["id"]
    await client.post(f"/api/projects/{pid}/understanding/generate")
    return pid


async def test_detail_has_workspace_panels(client):
    pid = await _project_with_ru(client)
    r = await client.get(f"/api/projects/{pid}")
    assert r.status_code == 200
    d = r.json()["data"]

    # quality subscores
    assert "quality" in d and "overall" in d["quality"]
    assert d["quality"]["heuristic"] is True
    assert d["quality"]["completeness"] > 0  # mock RU has field_confidence completeness

    # 10-stage map; RU in progress after generate (not yet validated)
    sp = d["stage_progress"]
    assert len(sp) == 10
    assert sp["requirement_understanding"]["status"] == "in_progress"

    # panels populated from the RU synthesis
    assert d["ru_status"] == "in_interview"
    assert len(d["assumptions"]) >= 1
    assert len(d["open_questions"]) >= 1


async def test_stage_progress_done_after_validate(client):
    pid = await _project_with_ru(client)
    v = await client.post(f"/api/projects/{pid}/understanding/validate")
    assert v.status_code == 200
    r = await client.get(f"/api/projects/{pid}")
    assert r.json()["data"]["stage_progress"]["requirement_understanding"]["status"] == "done"


async def test_assumptions_list_and_patch(client):
    pid = await _project_with_ru(client)
    lst = await client.get(f"/api/projects/{pid}/assumptions")
    assert lst.status_code == 200
    assumptions = lst.json()["data"]
    assert len(assumptions) >= 1

    aid = assumptions[0]["id"]
    patched = await client.patch(f"/api/projects/{pid}/assumptions/{aid}", json={"status": "confirmed"})
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "confirmed"

    bad = await client.patch(f"/api/projects/{pid}/assumptions/{aid}", json={"status": "nope"})
    assert bad.status_code == 422
