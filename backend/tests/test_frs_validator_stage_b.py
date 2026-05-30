"""FRS Stage-B validator tests.

Unit tests for the pure helpers + integration tests for rule firings against
designed Stage B state. Uses the same _seed_validated_brd + design helpers as
the orchestrator test file.
"""
from uuid import uuid4

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


# ─── Setup helpers ──────────────────────────────────────────────────────────


async def _seed_validated_brd(client, project_id: str) -> str:
    """Same as the orchestrator test helper."""
    from datetime import datetime, timezone
    import uuid
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.brd import BrdBusinessRequirement
    async with AsyncSessionLocal() as db:
        cb_doc = ArtifactDocument(
            project_id=uuid.UUID(project_id), artifact_type="concept_brief",
            status="validated", validated_at=datetime.now(timezone.utc),
            validated_snapshot_key="test-snapshot",
        )
        db.add(cb_doc)
        brd_doc = ArtifactDocument(
            project_id=uuid.UUID(project_id), artifact_type="brd",
            status="validated", validated_at=datetime.now(timezone.utc),
            validated_snapshot_key="test-snapshot",
        )
        db.add(brd_doc)
        await db.flush()
        for i in range(1, 9):
            db.add(BrdBusinessRequirement(
                document_id=brd_doc.id, row_key=f"BR-{i:03d}",
                version=1, is_current=True, is_locked=False,
                status="active", source="ai",
                title=f"Test BR {i}",
                description=f"Description for BR-{i:03d}",
                priority="must", category="functional",
                acceptance_criteria=[], objective_refs=[], stakeholder_refs=[],
                rationale="", completeness=95, confidence="high",
            ))
        await db.commit()
        return str(brd_doc.id)


async def _setup_designed(client) -> tuple[str, dict]:
    p = await client.post("/api/projects", json={
        "name": f"FRS BVAL {uuid4().hex[:6]}",
        "description": "Stage B validator test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate",
        json={"brief": "Stage B validator setup"},
    )
    res = await client.post(
        f"/api/projects/{project_id}/artifacts/frs/modules/MOD-001/design",
    )
    return project_id, res.json()["data"]


def _check_present(findings: list[dict], check_id: str) -> list[dict]:
    return [f for f in findings if f["check_id"] == check_id]


def _get_spec(detail: dict, spec_row_key: str) -> dict:
    """Find a spec by row_key across all modules. Raises AssertionError if not found.

    Uses next(..., None) so StopIteration never escapes into async context
    (PEP 479 / Python 3.7+ converts that to RuntimeError).
    """
    for mod in detail.get("modules", []):
        spec = next((s for s in mod.get("backlog", []) if s["row_key"] == spec_row_key), None)
        if spec is not None:
            return spec
    raise AssertionError(f"spec {spec_row_key!r} not found in any module of detail")


# ─── Unit tests (pure helpers) ──────────────────────────────────────────────


def test_validator_cycle_detector_acyclic_chain():
    """Acyclic depends_on graph returns False."""
    from app.services.artifacts.validators.frs import _has_depends_on_cycle

    class S:
        def __init__(self, k, deps):
            self.row_key = k; self.depends_on = deps
    specs = [S("A", ["B"]), S("B", ["C"]), S("C", [])]
    assert _has_depends_on_cycle(specs) is False


def test_validator_cycle_detector_finds_cycle():
    """A → B → A is detected."""
    from app.services.artifacts.validators.frs import _has_depends_on_cycle

    class S:
        def __init__(self, k, deps):
            self.row_key = k; self.depends_on = deps
    specs = [S("A", ["B"]), S("B", ["A"])]
    assert _has_depends_on_cycle(specs) is True


def test_validator_cycle_detector_finds_3node_cycle():
    """A → B → C → A is detected."""
    from app.services.artifacts.validators.frs import _has_depends_on_cycle

    class S:
        def __init__(self, k, deps):
            self.row_key = k; self.depends_on = deps
    specs = [S("A", ["B"]), S("B", ["C"]), S("C", ["A"])]
    assert _has_depends_on_cycle(specs) is True


def test_validator_cycle_detector_handles_unknown_dep():
    """Dep targets that don't appear in the graph are treated as terminal."""
    from app.services.artifacts.validators.frs import _has_depends_on_cycle

    class S:
        def __init__(self, k, deps):
            self.row_key = k; self.depends_on = deps
    specs = [S("A", ["GHOST"])]  # GHOST not in graph keys → no cycle
    assert _has_depends_on_cycle(specs) is False


# ─── Integration tests (real DB state) ──────────────────────────────────────


async def test_validator_too_few_scenarios(client):
    """Deleting scenarios until <6 fires `too_few_scenarios`."""
    from app.db import AsyncSessionLocal
    from app.models.frs import FrsAcceptanceScenario

    project_id, detail = await _setup_designed(client)
    spec = _get_spec(detail, "M001-FRS001")
    # Mark a single scenario as removed to trigger the rule
    sc = spec["scenarios"][-1]
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(FrsAcceptanceScenario).where(FrsAcceptanceScenario.id == sc["id"])
        )).scalar_one()
        row.status = "removed"
        await db.commit()

    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    findings = res.json()["data"]["findings"]
    hits = _check_present(findings, "too_few_scenarios")
    assert len(hits) >= 1
    assert any("M001-FRS001" in (h.get("row_key") or "") for h in hits)


async def test_validator_too_few_negative_scenarios(client):
    """If only 1 negative scenario, `too_few_negative_scenarios` fires."""
    from app.db import AsyncSessionLocal
    from app.models.frs import FrsAcceptanceScenario

    project_id, detail = await _setup_designed(client)
    spec = _get_spec(detail, "M001-FRS001")
    async with AsyncSessionLocal() as db:
        # Flip all but one negative to non-negative
        rows = (await db.execute(
            select(FrsAcceptanceScenario).where(
                FrsAcceptanceScenario.spec_row_key == "M001-FRS001",
                FrsAcceptanceScenario.is_current.is_(True),
                FrsAcceptanceScenario.status == "active",
                FrsAcceptanceScenario.is_negative.is_(True),
            ).order_by(FrsAcceptanceScenario.scenario_index)
        )).scalars().all()
        # Leave first one negative, flip the rest
        for r in rows[1:]:
            r.is_negative = False
        await db.commit()

    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "too_few_negative_scenarios")
    assert len(hits) >= 1


async def test_validator_fr_no_scenario(client):
    """An FR with empty scenario_refs fires `fr_no_scenario`."""
    project_id, detail = await _setup_designed(client)
    spec = _get_spec(detail, "M001-FRS001")
    fr = spec["functional_requirements"][0]

    # Wipe scenario_refs via editRow
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_functional_requirements/{fr['id']}/edit",
        json={"fields": {"scenario_refs": []}, "lock": False},
    )
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "fr_no_scenario")
    assert len(hits) >= 1


async def test_validator_scenario_no_fr(client):
    """A scenario with empty fr_refs fires `scenario_no_fr`."""
    project_id, detail = await _setup_designed(client)
    spec = _get_spec(detail, "M001-FRS001")
    sc = spec["scenarios"][0]

    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_acceptance_scenarios/{sc['id']}/edit",
        json={"fields": {"fr_refs": []}, "lock": False},
    )
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "scenario_no_fr")
    assert len(hits) >= 1


async def test_validator_depends_on_missing(client):
    """Spec.depends_on pointing at a non-existent FRS fires `depends_on_missing`."""
    project_id, detail = await _setup_designed(client)
    spec = _get_spec(detail, "M001-FRS001")

    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_specs/{spec['id']}/edit",
        json={"fields": {"depends_on": ["GHOST-FRS-999"]}, "lock": False},
    )
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "depends_on_missing")
    assert len(hits) >= 1


async def test_validator_depends_on_cycle(client):
    """Cyclic depends_on graph fires `depends_on_cycle`."""
    project_id, detail = await _setup_designed(client)
    s1 = _get_spec(detail, "M001-FRS001")
    s2 = _get_spec(detail, "M001-FRS002")

    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_specs/{s1['id']}/edit",
        json={"fields": {"depends_on": ["M001-FRS002"]}, "lock": False},
    )
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_specs/{s2['id']}/edit",
        json={"fields": {"depends_on": ["M001-FRS001"]}, "lock": False},
    )
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "depends_on_cycle")
    assert len(hits) >= 1


async def test_validator_spec_completeness_minor(client):
    """Spec with completeness < 90 fires the `spec_completeness` minor."""
    project_id, detail = await _setup_designed(client)
    spec = _get_spec(detail, "M001-FRS001")

    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/frs_specs/{spec['id']}/edit",
        json={"fields": {"completeness": 70}, "lock": False},
    )
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "spec_completeness")
    assert len(hits) >= 1


async def test_validator_figma_link_skipped_warning(client):
    """A spec whose screen.figma_link is the sentinel surfaces a warning."""
    project_id, _ = await _setup_designed(client)
    # First apply the sentinel via the figma-link endpoint on M001-FRS002 (ui_blocked in fixture)
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/specs/M001-FRS002/figma-link",
        json={"link": "https://figma.com/file/example/spec?node-id=1-1"},
    )
    # Then switch to sentinel
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/specs/M001-FRS002/figma-link",
        json={"link": "__none__"},
    )
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "figma_link_skipped")
    assert len(hits) >= 1


async def test_validator_open_spec_decision_warning(client):
    """An open spec-scoped decision surfaces as a warning."""
    project_id, detail = await _setup_designed(client)
    # The fixture's M001-FRS001 has an open spec_decision
    spec = _get_spec(detail, "M001-FRS001")
    has_open = any(
        d["resolution_status"] == "open" for d in spec.get("decisions", [])
    )
    if not has_open:
        pytest.skip("fixture lacks an open spec_decision; nothing to assert")

    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    hits = _check_present(res.json()["data"]["findings"], "open_spec_decision")
    assert len(hits) >= 1


async def test_validator_summary_counts_blocking_correctly(client):
    """summary.blocking = critical + major."""
    project_id, _ = await _setup_designed(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/findings")
    data = res.json()["data"]
    summary = data["summary"]
    assert summary["blocking"] == summary["critical"] + summary["major"]
