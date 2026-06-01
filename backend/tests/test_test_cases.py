"""Test Cases (E3) orchestrator + API tests (mock mode, zero Vertex calls).

Each test creates a project + a minimal validated FRS (modules/specs/scenarios/
FRs/business-rules/screens + FRS→BR traceability + validated CB/BRD with must-BRs),
then exercises generate → coverage → add+link → edit/delete/history → validate →
regenerate-preserves-manual.
"""
import uuid
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select

pytestmark = pytest.mark.asyncio

SPEC = "M001-FRS001"


async def _seed_validated_frs(project_id: str) -> None:
    """Hand-craft a validated CB + BRD + FRS with one fully-specified spec."""
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.brd import BrdBusinessRequirement
    from app.models.frs import (
        FrsAcceptanceScenario, FrsBusinessRule, FrsFunctionalRequirement,
        FrsModule, FrsModuleActor, FrsScreen, FrsSpec, FrsTraceability,
    )

    pid = uuid.UUID(project_id)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        for at in ("concept_brief", "brd"):
            db.add(ArtifactDocument(project_id=pid, artifact_type=at, status="validated",
                                    validated_at=now, validated_snapshot_key="test"))
        frs_doc = ArtifactDocument(project_id=pid, artifact_type="frs", status="validated",
                                   validated_at=now, validated_snapshot_key="test")
        db.add(frs_doc)
        await db.flush()

        brd_doc = (await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == pid, ArtifactDocument.artifact_type == "brd"))).scalar_one()
        db.add(BrdBusinessRequirement(
            document_id=brd_doc.id, row_key="BR-001", version=1, is_current=True, is_locked=False,
            status="active", source="ai", title="Transfer funds", description="...", priority="must",
            category="functional", acceptance_criteria=[], objective_refs=[], stakeholder_refs=[],
            rationale="", completeness=95, confidence="high",
        ))

        def _mix(**kw):
            return dict(version=1, is_current=True, is_locked=False, status="active", source="ai", **kw)

        db.add(FrsModule(document_id=frs_doc.id, row_key="MOD-001", name="Payments",
                         slug="payments", layer="vertical", summary="Move money", **_mix()))
        db.add(FrsModuleActor(document_id=frs_doc.id, row_key="MOD-001-ACT-1", module_row_key="MOD-001",
                              actor_name="analyst", relationship="primary_user", **_mix()))
        db.add(FrsSpec(document_id=frs_doc.id, row_key=SPEC, module_row_key="MOD-001",
                       title="Initiate Payment", priority="P0", layer="vertical",
                       br_refs=["BR-001"], narrative="Initiate a transfer",
                       independent_test="Transfer succeeds end to end",
                       data_and_validation="amount > 0", observability="audit transfer events", **_mix()))
        db.add(FrsAcceptanceScenario(document_id=frs_doc.id, row_key=f"{SPEC}-AS-1", spec_row_key=SPEC,
                                     scenario_index=1, given="funded account", when="transfer 50",
                                     then="balance debited 50", is_negative=False,
                                     fr_refs=[f"{SPEC}-FR-1"], **_mix()))
        db.add(FrsAcceptanceScenario(document_id=frs_doc.id, row_key=f"{SPEC}-AS-2", spec_row_key=SPEC,
                                     scenario_index=2, given="funded account", when="transfer -50",
                                     then="rejected with error", is_negative=True,
                                     fr_refs=[f"{SPEC}-FR-1"], **_mix()))
        db.add(FrsFunctionalRequirement(document_id=frs_doc.id, row_key=f"{SPEC}-FR-1", spec_row_key=SPEC,
                                        fr_id="FR-1", requirement_text="Debit the exact amount",
                                        scenario_refs=[f"{SPEC}-AS-1"], **_mix()))
        db.add(FrsBusinessRule(document_id=frs_doc.id, row_key=f"{SPEC}-BR-1", spec_row_key=SPEC,
                               rule_id="BR-1", description="Amount must be positive",
                               applies_to="amount", logic_decision="reject if <= 0", **_mix()))
        db.add(FrsScreen(document_id=frs_doc.id, row_key=f"{SPEC}-SCR-1", spec_row_key=SPEC,
                         screen_name="Transfer", purpose="enter transfer", user_roles=["analyst"],
                         layout="form", navigation="", interactive_behavior="", **_mix()))
        db.add(FrsTraceability(document_id=frs_doc.id, source_table="frs_specs", source_row_key=SPEC,
                               target_kind="brd_business_requirement", target_ref="BR-001",
                               target_label="Transfer funds", confidence="high"))
        await db.commit()


async def _new_project(client) -> str:
    p = await client.post("/api/projects", json={
        "name": f"TC {uuid4().hex[:6]}", "description": "test-cases", "business_unit": "Ops",
    })
    return p.json()["data"]["id"]


async def test_generate_creates_suites_plans_cases(client):
    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)

    gen = await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})
    assert gen.status_code == 200, gen.text
    detail = gen.json()["data"]
    assert detail["document"]["status"] == "in_interview"

    suites = detail["suites"]
    assert len(suites) == 1
    plans = suites[0]["plans"]
    assert len(plans) == 1
    cases = plans[0]["cases"]
    assert len(cases) >= 5
    types = {c["test_type"] for c in cases}
    assert {"functional", "negative", "e2e", "edge_case", "responsive"} <= types
    # every case rich + traced
    for c in cases:
        assert len(c["key_assertions"]) >= 2
        assert c["expected_result"].strip()
        assert c["traceability"], f"{c['row_key']} has no traceability"
    # responsive case has viewports
    resp = [c for c in cases if c["test_type"] == "responsive"]
    assert resp and resp[0]["viewports"]


async def test_coverage_full_chain(client):
    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})

    cov = await client.get(f"/api/projects/{project_id}/artifacts/test_cases/coverage")
    assert cov.status_code == 200, cov.text
    data = cov.json()["data"]
    assert data["project_pct"] == 100.0
    assert data["summary"]["must_br_total"] == 1
    assert data["summary"]["must_br_untested"] == 0
    assert data["brd_chain"][0]["br_row_key"] == "BR-001"
    assert data["brd_chain"][0]["tested"] is True
    # outcome rollup present
    assert "MOD-001" in data["outcomes"]
    assert data["outcomes"]["MOD-001"]["risk_coverage"]["negative"] >= 1


async def test_add_and_link_manual_case(client):
    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})

    plan_key = f"TP-{SPEC}"
    add = await client.post(
        f"/api/projects/{project_id}/artifacts/test_cases/plans/{plan_key}/cases",
        json={
            "title": "Manual: large transfer", "test_type": "functional",
            "given": "a funded account", "when": "transfer near limit", "then": "succeeds",
            "key_assertions": ["balance debited exactly", "audit event recorded"],
            "expected_result": "Large transfer succeeds and is audited.",
            "links": {"fr_refs": [f"{SPEC}-FR-1"]},
        },
    )
    assert add.status_code == 200, add.text
    new_key = add.json()["data"]["row_key"]
    assert new_key.startswith(plan_key)

    # invalid link rejected
    bad = await client.post(
        f"/api/projects/{project_id}/artifacts/test_cases/plans/{plan_key}/cases",
        json={"title": "x", "key_assertions": ["a", "b"], "expected_result": "y",
              "links": {"fr_refs": ["DOES-NOT-EXIST"]}},
    )
    assert bad.status_code == 422, bad.text

    # the manual case is human-sourced and present in detail
    detail = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases")).json()["data"]
    cases = detail["suites"][0]["plans"][0]["cases"]
    manual = [c for c in cases if c["row_key"] == new_key]
    assert manual and manual[0]["source"] == "human"


async def test_edit_delete_history(client):
    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})
    detail = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases")).json()["data"]
    case = detail["suites"][0]["plans"][0]["cases"][0]
    cid = case["id"]

    edit = await client.post(
        f"/api/projects/{project_id}/artifacts/test_cases/test_cases/{cid}/edit",
        json={"fields": {"title": "Edited title"}},
    )
    assert edit.status_code == 200, edit.text
    assert edit.json()["data"]["version"] == 2

    # history shows both versions
    new_id = edit.json()["data"]["id"]
    hist = await client.get(f"/api/projects/{project_id}/artifacts/test_cases/test_cases/{new_id}/history")
    assert hist.status_code == 200
    assert len(hist.json()["data"]["versions"]) == 2

    # delete (soft)
    dele = await client.post(f"/api/projects/{project_id}/artifacts/test_cases/test_cases/{new_id}/delete")
    assert dele.status_code == 200
    after = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases")).json()["data"]
    remaining = [c["row_key"] for c in after["suites"][0]["plans"][0]["cases"]]
    assert case["row_key"] not in remaining


async def test_validate_clean_locks_rows(client):
    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})

    val = await client.post(f"/api/projects/{project_id}/artifacts/test_cases/validate")
    assert val.status_code == 200, val.text
    body = val.json()["data"]
    assert body["ok"] is True, body["findings"]
    assert body["locked_row_count"] > 0
    detail = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases")).json()["data"]
    assert detail["document"]["status"] == "validated"


async def test_regenerate_preserves_manual_case(client):
    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})
    plan_key = f"TP-{SPEC}"
    add = await client.post(
        f"/api/projects/{project_id}/artifacts/test_cases/plans/{plan_key}/cases",
        json={"title": "Manual keepme", "key_assertions": ["a", "b"],
              "expected_result": "kept", "links": {"fr_refs": [f"{SPEC}-FR-1"]}},
    )
    manual_key = add.json()["data"]["row_key"]

    # regenerate the plan
    regen = await client.post(f"/api/projects/{project_id}/artifacts/test_cases/plans/{SPEC}/regenerate")
    assert regen.status_code == 200, regen.text

    detail = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases")).json()["data"]
    keys = [c["row_key"] for c in detail["suites"][0]["plans"][0]["cases"]]
    assert manual_key in keys, "manual case must survive AI regeneration"


def test_sanitize_refs_drops_invalid():
    """_sanitize_refs removes refs/traceability pointing to non-existent FRS rows."""
    from app.services.artifacts.tc_orchestrator import _sanitize_refs
    target = {"row_key": "S1", "br_refs": ["BR-001"],
              "scenarios": [{"row_key": "S1-AS-1"}], "functional_requirements": [{"row_key": "S1-FR-1"}],
              "business_rules": [], "screens": []}
    result = {"test_cases": [{
        "row_key": "x", "scenario_refs": ["S1-AS-1", "S1-AS-9"],  # AS-9 bogus
        "fr_refs": ["S1-FR-1"], "br_refs": ["S1-BR-Z"],            # BR-Z bogus
        "source_ref": "GHOST",
    }], "traceability": [
        {"source_table": "test_cases", "source_row_key": "x", "target_kind": "frs_acceptance_scenario", "target_ref": "S1-AS-1"},
        {"source_table": "test_cases", "source_row_key": "x", "target_kind": "frs_acceptance_scenario", "target_ref": "S1-AS-9"},  # bogus
    ]}
    out = _sanitize_refs(result, target)
    c = out["test_cases"][0]
    assert c["scenario_refs"] == ["S1-AS-1"]
    assert c["br_refs"] == []           # bogus dropped
    assert c["source_ref"] is None      # bogus dropped
    assert len(out["traceability"]) == 1 and out["traceability"][0]["target_ref"] == "S1-AS-1"


async def test_gap_fill_recovers_deleted_coverage(client):
    """Deleting a plan's cases creates gaps; gap-fill re-authors only the uncovered elements."""
    from app.db import AsyncSessionLocal
    from sqlalchemy import update as sa_update
    from app.models.artifact import ArtifactDocument
    from app.models.test_cases import TestCase

    project_id = await _new_project(client)
    await _seed_validated_frs(project_id)
    await client.post(f"/api/projects/{project_id}/artifacts/test_cases/generate", json={})
    plan_key = f"TP-{SPEC}"

    # Soft-delete every case in this plan to create coverage gaps.
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(__import__('sqlalchemy').select(ArtifactDocument).where(
            ArtifactDocument.project_id == __import__('uuid').UUID(project_id),
            ArtifactDocument.artifact_type == "test_cases"))).scalar_one()
        await db.execute(sa_update(TestCase).where(
            TestCase.document_id == doc.id, TestCase.plan_row_key == plan_key,
            TestCase.is_current.is_(True)).values(status="removed"))
        await db.commit()

    before = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases")).json()["data"]
    plan_before = next(p for s in before["suites"] for p in s["plans"] if p["row_key"] == plan_key)
    assert len(plan_before["cases"]) == 0

    res = await client.post(f"/api/projects/{project_id}/artifacts/test_cases/plans/{SPEC}/gap-fill")
    assert res.status_code == 200, res.text
    after = res.json()["data"]
    plan_after = next(p for s in after["suites"] for p in s["plans"] if p["row_key"] == plan_key)
    assert len(plan_after["cases"]) >= 4   # re-authored cases for the uncovered scenarios/FR/rule/screen
    # coverage of this spec back up
    cov = (await client.get(f"/api/projects/{project_id}/artifacts/test_cases/coverage")).json()["data"]
    spec_pct = next(sp["pct"] for m in cov["modules"] for sp in m["specs"] if sp["spec_row_key"] == SPEC)
    assert spec_pct == 100.0
