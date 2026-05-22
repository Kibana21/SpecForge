"""E2 Phase 5 — Requirement Understanding interview + generation gate."""
import pytest

pytestmark = pytest.mark.asyncio


async def _new_project(client) -> str:
    r = await client.post("/api/projects", json={"name": "RU Flow", "description": "modernize payments"})
    assert r.status_code == 201
    body = r.json()["data"]
    assert body["human_id"].startswith("PRJ-")  # wizard allocates a human id
    return body["id"]


async def test_generate_then_interview_then_validate_and_gate(client):
    pid = await _new_project(client)

    # Gate is closed before validation.
    pre = await client.post(f"/api/projects/{pid}/specs/functional")
    assert pre.status_code == 409
    assert pre.json()["error"]["code"] == "understanding_not_validated"

    # Validating a draft RU (no objective yet) is rejected.
    bad = await client.post(f"/api/projects/{pid}/understanding/validate")
    assert bad.status_code == 403
    assert bad.json()["error"]["code"] == "understanding_incomplete"

    # Generate the RU (mock fixture → objective + open questions + assumptions).
    gen = await client.post(f"/api/projects/{pid}/understanding/generate")
    assert gen.status_code == 200
    detail = gen.json()["data"]
    assert detail["understanding"]["status"] == "in_interview"
    assert detail["understanding"]["objective"]
    assert any(m["role"] == "question" for m in detail["messages"])

    # Answer a question → re-synthesis appends a user turn.
    ans = await client.post(f"/api/projects/{pid}/understanding/answer", json={"answer": "Target latency is under 5 seconds."})
    assert ans.status_code == 200
    assert any(m["role"] == "user" for m in ans.json()["data"]["messages"])

    # Validate → gate opens.
    val = await client.post(f"/api/projects/{pid}/understanding/validate")
    assert val.status_code == 200
    assert val.json()["data"]["ru_validated"] is True

    # Gate is now open (no requirements yet → 422, but NOT the 409 gate error).
    post = await client.post(f"/api/projects/{pid}/specs/functional")
    assert post.status_code != 409
    assert post.json()["error"]["code"] == "no_requirements"


async def test_assumptions_and_open_questions_persisted(client):
    from sqlalchemy import select
    from uuid import UUID

    from app.db import AsyncSessionLocal
    from app.models.gap import GapQuestion
    from app.models.project_intake import Assumption

    pid = await _new_project(client)
    await client.post(f"/api/projects/{pid}/understanding/generate")

    async with AsyncSessionLocal() as db:
        assumptions = (await db.execute(select(Assumption).where(Assumption.project_id == UUID(pid)))).scalars().all()
        interview_gaps = (await db.execute(
            select(GapQuestion).where(GapQuestion.project_id == UUID(pid), GapQuestion.source == "interview")
        )).scalars().all()
    assert len(assumptions) >= 1
    assert len(interview_gaps) >= 1
