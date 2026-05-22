"""
Spec generation pipeline tests. Requires PostgreSQL with schema applied.
Exercises the full sequential flow: upload → extract → gaps → generate × 4 → export.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent / "fixtures"


async def _setup_project_with_docs(client) -> str:
    """Create a project, upload sample.txt, mark RU validated (gate), return project_id."""
    import uuid as _uuid

    r = await client.post("/api/projects", json={"name": "SpecPipeline"})
    project_id = r.json()["data"]["id"]
    content = (FIXTURES / "sample.txt").read_bytes()
    await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("sample.txt", content, "text/plain")},
    )
    # Spec generation is gated behind RU validation (E2). Mark it validated for these
    # pre-E2 pipeline tests.
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    async with AsyncSessionLocal() as db:
        p = await db.get(Project, _uuid.UUID(project_id))
        p.ru_validated = True
        await db.commit()
    return project_id


async def test_full_spec_pipeline(client):
    """End-to-end: extract → gaps → functional → technical → stories → review → export."""
    project_id = await _setup_project_with_docs(client)

    # Extract requirements
    r = await client.post(f"/api/projects/{project_id}/extract")
    assert r.status_code == 200, r.text
    reqs = r.json()["data"]
    assert len(reqs) >= 1

    # List requirements
    r = await client.get(f"/api/projects/{project_id}/requirements")
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1

    # Detect gaps
    r = await client.post(f"/api/projects/{project_id}/detect-gaps")
    assert r.status_code == 200, r.text
    gaps = r.json()["data"]
    assert isinstance(gaps, list)

    # List gaps
    r = await client.get(f"/api/projects/{project_id}/gaps")
    assert r.status_code == 200

    # Resolve a gap if any
    if gaps:
        gap_id = gaps[0]["id"]
        r = await client.patch(
            f"/api/projects/{project_id}/gaps/{gap_id}",
            json={"resolved": True, "resolution_text": "Clarified in kickoff meeting."},
        )
        assert r.status_code == 200
        assert r.json()["data"]["resolved"] is True

    # Generate functional spec
    r = await client.post(f"/api/projects/{project_id}/specs/functional")
    assert r.status_code == 200, r.text
    func_spec = r.json()["data"]
    assert func_spec["spec_type"] == "functional"
    assert func_spec["version_number"] == 1
    func_spec_id = func_spec["id"]

    # Generate technical spec
    r = await client.post(f"/api/projects/{project_id}/specs/technical")
    assert r.status_code == 200, r.text
    tech_spec = r.json()["data"]
    assert tech_spec["spec_type"] == "technical"
    assert tech_spec["version_number"] == 2  # global per-project counter

    # Generate user stories
    r = await client.post(f"/api/projects/{project_id}/specs/user-stories")
    assert r.status_code == 200, r.text
    stories = r.json()["data"]
    assert stories["spec_type"] == "user_stories"
    assert stories["version_number"] == 3

    # Run review
    r = await client.post(f"/api/projects/{project_id}/review")
    assert r.status_code == 200, r.text
    review = r.json()["data"]
    assert review["spec_type"] == "review"
    assert review["version_number"] == 4

    # Review comments should be created
    r = await client.get(f"/api/projects/{project_id}/reviews")
    assert r.status_code == 200
    comments = r.json()["data"]
    assert len(comments) >= 1

    # Dismiss a comment
    comment_id = comments[0]["id"]
    r = await client.patch(
        f"/api/projects/{project_id}/reviews/{comment_id}",
        json={"dismissed": True},
    )
    assert r.status_code == 200
    assert r.json()["data"]["dismissed"] is True

    # List specs — default returns latest per type (4 entries)
    r = await client.get(f"/api/projects/{project_id}/specs")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 4

    # Get specific spec version
    r = await client.get(f"/api/projects/{project_id}/specs/{func_spec_id}")
    assert r.status_code == 200
    assert r.json()["data"]["id"] == func_spec_id

    # Patch (autosave) spec
    r = await client.patch(
        f"/api/projects/{project_id}/specs/{func_spec_id}",
        json={"content_markdown": "# Updated\n\nEdited content."},
    )
    assert r.status_code == 200
    assert r.json()["data"]["is_edited"] is True
    assert r.json()["data"]["content_markdown"] == "# Updated\n\nEdited content."

    # Export single spec
    r = await client.get(f"/api/projects/{project_id}/export/markdown?spec_type=functional")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert "attachment" in r.headers["content-disposition"]

    # Export all specs combined
    r = await client.get(f"/api/projects/{project_id}/export/markdown?spec_type=all")
    assert r.status_code == 200
    assert "---" in r.text  # combined sections are separated by ---


async def _mark_validated(project_id: str) -> None:
    import uuid as _uuid
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    async with AsyncSessionLocal() as db:
        p = await db.get(Project, _uuid.UUID(project_id))
        p.ru_validated = True
        await db.commit()


async def test_generate_technical_without_functional_returns_422(client):
    r = await client.post("/api/projects", json={"name": "NoFuncSpec"})
    project_id = r.json()["data"]["id"]
    await _mark_validated(project_id)
    r = await client.post(f"/api/projects/{project_id}/specs/technical")
    assert r.status_code == 422
    assert "functional" in r.json()["error"]["message"].lower()


async def test_version_number_increments_per_project(client):
    r = await client.post("/api/projects", json={"name": "VersionTest"})
    project_id = r.json()["data"]["id"]
    await _mark_validated(project_id)
    content = (FIXTURES / "sample.txt").read_bytes()
    await client.post(
        f"/api/projects/{project_id}/documents",
        files={"file": ("s.txt", content, "text/plain")},
    )
    await client.post(f"/api/projects/{project_id}/extract")

    r1 = await client.post(f"/api/projects/{project_id}/specs/functional")
    r2 = await client.post(f"/api/projects/{project_id}/specs/functional")
    v1 = r1.json()["data"]["version_number"]
    v2 = r2.json()["data"]["version_number"]
    assert v2 == v1 + 1


async def test_export_invalid_spec_type_returns_400(client):
    r = await client.post("/api/projects", json={"name": "ExportBad"})
    project_id = r.json()["data"]["id"]
    r = await client.get(f"/api/projects/{project_id}/export/markdown?spec_type=bogus")
    assert r.status_code == 400
