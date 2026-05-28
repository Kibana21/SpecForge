"""FRS Stage-A orchestrator tests (mock mode).

Each test creates a fresh project + a minimal validated BRD (bypassing the
full BRD pipeline) then runs the FRS modularize pipeline and asserts on the
output structure.
"""
import uuid
from uuid import uuid4

import pytest
from sqlalchemy import select, func, delete

pytestmark = pytest.mark.asyncio


async def _seed_validated_brd(client, project_id: str) -> str:
    """Create minimal validated CB + BRD docs directly (bypassing full pipelines).

    The mock-mode CB/BRD pipelines don't produce validation-clean fixtures, so
    instead we hand-craft just enough state for FRS tests:
    - 1 ArtifactDocument with artifact_type='concept_brief', status='validated'
    - 1 ArtifactDocument with artifact_type='brd', status='validated'
    - 8 BRD business_requirement rows (BR-001…BR-008) that match the FRS fixture's
      br_refs. Without these the FRS BR-coverage check would fail.
    Returns the BRD document_id as a string.
    """
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.brd import BrdBusinessRequirement
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as db:
        # Validated CB
        cb_doc = ArtifactDocument(
            project_id=uuid.UUID(project_id),
            artifact_type="concept_brief",
            status="validated",
            validated_at=datetime.now(timezone.utc),
            validated_snapshot_key="test-snapshot",
        )
        db.add(cb_doc)
        # Validated BRD
        brd_doc = ArtifactDocument(
            project_id=uuid.UUID(project_id),
            artifact_type="brd",
            status="validated",
            validated_at=datetime.now(timezone.utc),
            validated_snapshot_key="test-snapshot",
        )
        db.add(brd_doc)
        await db.flush()

        # 8 BR rows matching the FRS fixture's br_refs
        for i in range(1, 9):
            db.add(BrdBusinessRequirement(
                document_id=brd_doc.id,
                row_key=f"BR-{i:03d}",
                version=1, is_current=True, is_locked=False,
                status="active", source="ai",
                title=f"Test BR {i}",
                description=f"Description for BR-{i:03d}",
                priority="must",
                category="functional",
                acceptance_criteria=[],
                objective_refs=[],
                stakeholder_refs=[],
                rationale="",
                completeness=95,
                confidence="high",
            ))
        await db.commit()
        return str(brd_doc.id)


async def test_frs_generate_creates_modules_from_fixture(client):
    """Stage A pipeline against a project with validated BRD produces modules + stubs."""
    p = await client.post("/api/projects", json={
        "name": f"FRS Smoke {uuid4().hex[:6]}",
        "description": "FRS Stage A test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)

    # GET FRS before generation
    detail_before = await client.get(f"/api/projects/{project_id}/artifacts/frs")
    assert detail_before.json()["data"]["document"] is None

    # Generate
    gen = await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate",
        json={"brief": "MVP for the test project"},
    )
    assert gen.status_code == 200, gen.text
    detail = gen.json()["data"]

    # Document moved to in_interview after modularize
    assert detail["document"]["status"] == "in_interview"
    assert "modularize" in detail["document"]["unit_status"]
    assert detail["document"]["unit_status"]["modularize"]["completeness"] > 0

    # Mock fixture produces 6 modules (5 vertical + 1 foundation)
    modules = detail["modules"]
    assert len(modules) == 6
    by_key = {m["row_key"]: m for m in modules}
    assert "MOD-000" in by_key
    assert by_key["MOD-000"]["layer"] == "foundation"
    for mk in ("MOD-001", "MOD-002", "MOD-003", "MOD-004", "MOD-005"):
        assert mk in by_key
        assert by_key[mk]["layer"] == "vertical"

    # Every module has at least one of: actor, responsibility, backlog stub
    for m in modules:
        assert len(m["actors"]) > 0, f"{m['row_key']} has no actors"
        assert len(m["responsibilities"]) > 0, f"{m['row_key']} has no responsibilities"
        # Backlog: at least one stub (MOD-000 has 3, feature modules have 2-3)
        assert len(m["backlog"]) > 0, f"{m['row_key']} has no backlog stubs"

    # Two open module-scoped decisions from the fixture
    open_decisions = [d for d in detail["decisions"] if d["resolution_status"] == "open"]
    assert len(open_decisions) == 2

    # Synthesis message + 2 decision questions
    assert len(detail["messages"]) >= 3


async def test_frs_generate_is_idempotent(client):
    """Running modularize twice with no input changes produces 0 new versions."""
    from app.db import AsyncSessionLocal
    from app.models.frs import FrsModule, FrsModuleActor, FrsSpec

    p = await client.post("/api/projects", json={
        "name": f"FRS Idempotent {uuid4().hex[:6]}",
        "description": "Idempotency test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)

    # First run
    await client.post(f"/api/projects/{project_id}/artifacts/frs/generate", json={"brief": "MVP"})

    # Count total row versions (current + historical) before re-run
    async with AsyncSessionLocal() as db:
        mod_before = await db.scalar(select(func.count(FrsModule.id)))
        actor_before = await db.scalar(select(func.count(FrsModuleActor.id)))
        spec_before = await db.scalar(select(func.count(FrsSpec.id)))

    # Reset status + re-run (same fixture input → same output)
    await client.post(f"/api/projects/{project_id}/artifacts/frs/reset-generating")
    await client.post(f"/api/projects/{project_id}/artifacts/frs/modularize")

    async with AsyncSessionLocal() as db:
        mod_after = await db.scalar(select(func.count(FrsModule.id)))
        actor_after = await db.scalar(select(func.count(FrsModuleActor.id)))
        spec_after = await db.scalar(select(func.count(FrsSpec.id)))

    # No new versions should have been created
    assert mod_after == mod_before, f"new module versions: {mod_after - mod_before}"
    assert actor_after == actor_before, f"new actor versions: {actor_after - actor_before}"
    assert spec_after == spec_before, f"new spec versions: {spec_after - spec_before}"


async def test_frs_locked_module_preserved_on_regen(client):
    """A locked module is preserved verbatim on re-modularize."""
    from app.db import AsyncSessionLocal
    from app.models.frs import FrsModule

    p = await client.post("/api/projects", json={
        "name": f"FRS Lock {uuid4().hex[:6]}",
        "description": "Lock test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    detail = (await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate", json={"brief": "MVP"}
    )).json()["data"]

    mod001 = next(m for m in detail["modules"] if m["row_key"] == "MOD-001")
    original_summary = mod001["summary"]
    original_version = mod001["version"]

    # Edit MOD-001 with a custom summary, then lock it
    edit = await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_modules/{mod001['id']}/edit",
        json={"fields": {"summary": "USER-EDITED LOCKED SUMMARY"}, "lock": True},
    )
    assert edit.status_code == 200

    # Re-run modularize — the locked module should be preserved
    await client.post(f"/api/projects/{project_id}/artifacts/frs/reset-generating")
    await client.post(f"/api/projects/{project_id}/artifacts/frs/modularize")

    async with AsyncSessionLocal() as db:
        current = (await db.execute(
            select(FrsModule).where(
                FrsModule.document_id == uuid.UUID(detail["document"]["id"]),
                FrsModule.row_key == "MOD-001",
                FrsModule.is_current.is_(True),
            )
        )).scalar_one()
        assert current.is_locked
        assert current.summary == "USER-EDITED LOCKED SUMMARY"


async def test_frs_blocked_when_brd_not_validated(client):
    """generate_frs_all raises 409 when the BRD isn't validated."""
    p = await client.post("/api/projects", json={
        "name": f"FRS NoBRD {uuid4().hex[:6]}",
        "description": "BRD-blocked test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    # NOTE: not seeding a BRD — readiness should block

    readiness = await client.post(f"/api/projects/{project_id}/artifacts/frs/readiness")
    r = readiness.json()["data"]
    assert r["brd_ready"] is False
    assert r["can_generate"] is False
    # Either CB or BRD will be the blocking reason (CB is checked first)
    blocking = r["blocking_reason"] or ""
    assert ("BRD" in blocking) or ("Concept Brief" in blocking)

    gen = await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate",
        json={"brief": "should fail"},
    )
    assert gen.status_code == 409
    assert gen.json()["error"]["code"] == "frs_not_ready"


async def test_frs_module_decision_resolve_flow(client):
    """Resolve an open [SPEC-DECISION] and verify the status transition."""
    p = await client.post("/api/projects", json={
        "name": f"FRS Decision {uuid4().hex[:6]}",
        "description": "Decision flow test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    detail = (await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate", json={"brief": "MVP"}
    )).json()["data"]

    open_dec = next(d for d in detail["decisions"] if d["resolution_status"] == "open")
    resolve = await client.post(
        f"/api/projects/{project_id}/artifacts/frs/decisions/{open_dec['id']}/resolve",
        json={"chosen_index": 0, "status": "accepted_ai"},
    )
    assert resolve.status_code == 200
    assert resolve.json()["data"]["resolution_status"] == "accepted_ai"


async def test_frs_findings_returns_warnings_for_open_decisions(client):
    """Validator returns warnings (not blocking) for open module decisions."""
    p = await client.post("/api/projects", json={
        "name": f"FRS Findings {uuid4().hex[:6]}",
        "description": "Findings test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/frs/generate", json={"brief": "MVP"})

    findings = (await client.get(
        f"/api/projects/{project_id}/artifacts/frs/findings"
    )).json()["data"]

    # 2 open decisions → 2 warnings; 0 blocking
    summary = findings["summary"]
    assert summary["blocking"] == 0
    assert summary["warnings"] >= 2
    assert any(f["check_id"] == "open_module_decision" for f in findings["findings"])


async def test_frs_validate_marks_stage_a_approved_when_clean(client):
    """If findings are non-blocking, /validate sets _stage_a_approved=True."""
    p = await client.post("/api/projects", json={
        "name": f"FRS Validate {uuid4().hex[:6]}",
        "description": "Validate test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    detail = (await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate", json={"brief": "MVP"}
    )).json()["data"]

    # Resolve both decisions so warnings drop
    for d in detail["decisions"]:
        if d["resolution_status"] == "open":
            await client.post(
                f"/api/projects/{project_id}/artifacts/frs/decisions/{d['id']}/resolve",
                json={"chosen_index": d["recommended_index"], "status": "accepted_ai"},
            )

    validate = (await client.post(
        f"/api/projects/{project_id}/artifacts/frs/validate"
    )).json()["data"]

    assert validate["ok"] is True
    assert validate["summary"]["blocking"] == 0

    # Confirm stage_a_approved flag on the document
    fresh = (await client.get(
        f"/api/projects/{project_id}/artifacts/frs"
    )).json()["data"]
    assert fresh["document"]["unit_status"].get("_stage_a_approved") is True


async def test_frs_row_history_returns_all_versions(client):
    """Edit a module 3 times → history returns 4 versions (v1 initial + 3 edits)."""
    p = await client.post("/api/projects", json={
        "name": f"FRS History {uuid4().hex[:6]}",
        "description": "History test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    detail = (await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate", json={"brief": "MVP"}
    )).json()["data"]

    mod001_id = next(m["id"] for m in detail["modules"] if m["row_key"] == "MOD-001")

    # Edit 3 times — each bumps version
    for i in range(3):
        edit = await client.post(
            f"/api/projects/{project_id}/artifacts/frs/frs_modules/{mod001_id}/edit",
            json={"fields": {"summary": f"version {i+2}"}},
        )
        assert edit.status_code == 200
        # The new row has a new id; pull the new id for the next iteration
        mod001_id = edit.json()["data"]["id"]

    history = (await client.get(
        f"/api/projects/{project_id}/artifacts/frs/frs_modules/{mod001_id}/history"
    )).json()["data"]

    assert len(history) == 4  # v1 + 3 edits
    versions = [h["version"] for h in history]
    assert versions == [4, 3, 2, 1]  # descending
    assert history[0]["is_current"] is True
    assert all(h["is_current"] is False for h in history[1:])
