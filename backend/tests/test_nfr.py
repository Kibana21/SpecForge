"""NFR (E5) orchestrator + validator tests (mock mode, zero Vertex calls).

Each test creates a project + a validated BRD, then exercises the NFR engine:
generate → validate → CRUD on every section → manual-row-survives-regen →
soft feeds-FRS. Generation runs sequentially over the 9-unit manifest.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text

pytestmark = pytest.mark.asyncio

CATEGORIES = {"performance", "security", "availability", "usability",
              "scalability", "maintainability", "portability"}


@pytest_asyncio.fixture
async def nfr_ctx():
    """Create a user + project + validated BRD; yield (project, user_id); clean up."""
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.models.user import User

    uid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(User(id=uid, email=f"nfr-{uid}@specforge.test", display_name="NFR Test",
                    password_hash="x", role="platform_admin", status="active"))
        await db.commit()
    async with AsyncSessionLocal() as db:
        proj = Project(name=f"ztest-nfr-{uuid.uuid4().hex[:8]}", owner_id=uid)
        db.add(proj)
        await db.flush()
        db.add(ArtifactDocument(project_id=proj.id, artifact_type="brd", status="validated"))
        await db.commit()
        pid = proj.id
        proj_detached = await db.get(Project, pid)
        db.expunge(proj_detached)

    yield proj_detached, uid

    async with AsyncSessionLocal() as db:
        p = await db.get(Project, pid)
        if p:
            await db.delete(p)
        u = await db.get(User, uid)
        if u:
            await db.delete(u)
        await db.commit()


async def _doc_id(pid):
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == pid, ArtifactDocument.artifact_type == "nfr"))).scalar_one()
        return doc.id


async def test_generate_produces_all_categories(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.services.artifacts import nfr_orchestrator as O
    proj, _ = nfr_ctx
    async with AsyncSessionLocal() as db:
        detail = await O.generate_nfr_all(proj, db)

    reqs = detail["sections"]["nfr_requirements"]
    assert len(reqs) == 15
    assert {r["category"] for r in reqs} == CATEGORIES
    # global, contiguous, gap-free NFR-nnn numbering
    nums = sorted(int(r["row_key"].split("-")[1]) for r in reqs)
    assert nums == list(range(1, 16))
    # governance + overview present
    for t in ("nfr_risks", "nfr_tradeoffs", "nfr_open_questions", "nfr_decisions",
              "nfr_references", "nfr_glossary", "nfr_text_blocks"):
        assert detail["sections"].get(t), f"missing section {t}"
    # radar: 7 axes, weighted = Σ MoSCoW weights
    assert len(detail["radar"]) == 7
    perf = next(a for a in detail["radar"] if a["category"] == "performance")
    assert perf["count"] == 3 and perf["weighted"] == 9  # must+should+could = 4+3+2
    # every requirement traced
    assert len(detail["traceability_by_source"]) == 15


async def test_validation_passes_clean(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.services.artifacts import nfr_orchestrator as O
    proj, uid = nfr_ctx
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    async with AsyncSessionLocal() as db:
        res = await O.validate_nfr(proj.id, db, uid)
    assert res["ok"] is True
    assert [f for f in res["findings"] if f["group"] in ("critical", "major")] == []
    # rows locked after validate
    async with AsyncSessionLocal() as db:
        locked = await O._locked_nfr_rows_for("nfr_requirements", await _doc_id(proj.id), db)
        assert len(locked) == 15


async def test_validation_blocks_on_missing_category(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.models.nfr import NfrRequirement
    from app.services.artifacts import nfr_orchestrator as O
    proj, uid = nfr_ctx
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    did = await _doc_id(proj.id)
    # wipe the portability category
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(NfrRequirement).where(
            NfrRequirement.document_id == did, NfrRequirement.category == "portability",
            NfrRequirement.is_current.is_(True)))).scalars().all()
        for r in rows:
            r.status = "removed"
        await db.commit()
    async with AsyncSessionLocal() as db:
        res = await O.validate_nfr(proj.id, db, uid)
    assert res["ok"] is False
    assert any(f["check_id"] == "all_categories_covered" for f in res["findings"])


async def test_crud_every_section(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.services.artifacts import nfr_orchestrator as O
    proj, uid = nfr_ctx
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    did = await _doc_id(proj.id)

    async with AsyncSessionLocal() as db:
        # add to a governance section
        added = await O.add_nfr_row(did, "nfr_glossary",
                                    {"term": "SLA", "definition": "Service Level Agreement"}, db, uid)
        await db.commit()
        assert added["row_key"] == "NFR-G-002"  # NFR-G-001 came from the fixture
        # edit (versions + locks)
        edited = await O.edit_nfr_row("nfr_glossary", uuid.UUID(added["id"]),
                                      {"definition": "edited"}, db, uid)
        await db.commit()
        assert edited["version"] == 2 and edited["is_locked"] is True
        # history
        hist = await O.get_nfr_row_history("nfr_glossary", did, added["row_key"], db)
        assert [h["version"] for h in hist] == [2, 1]
        # unlock → delete → restore
        await O.unlock_nfr_row("nfr_glossary", uuid.UUID(edited["id"]), db)
        await db.commit()
        d = await O.delete_nfr_row("nfr_glossary", uuid.UUID(edited["id"]), db)
        await db.commit()
        assert d["status"] == "removed"
        restored = await O.restore_nfr_row("nfr_glossary", did, added["row_key"], 1, db, uid)
        await db.commit()
        assert restored["version"] == 3


async def test_manual_requirement_survives_regen(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.services.artifacts import nfr_orchestrator as O
    from app.services.context.project_context import gather_project_context
    proj, uid = nfr_ctx
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    did = await _doc_id(proj.id)

    async with AsyncSessionLocal() as db:
        req = await O.add_nfr_row(
            did, "nfr_requirements",
            {"category": "portability", "attribute": "OS", "requirement": "Runs on Linux+Windows",
             "priority": "could", "measurement": "CI matrix covers both"},
            db, uid, brd_links=[{"target_kind": "brd_objective", "target_ref": "OBJ-1"}])
        await db.commit()
        assert req["row_key"] == "NFR-016" and req["source"] == "human"

    async with AsyncSessionLocal() as db:
        p = await db.get(type(proj), proj.id)
        from app.models.artifact import ArtifactDocument
        doc = await db.get(ArtifactDocument, did)
        bundle = await gather_project_context(proj.id, db, artifact_document_id=did, artifact_type="nfr")
        await O.generate_nfr_unit(p, "portability", doc, bundle, db, brief="")
        await db.commit()
        port = await O._current_nfr_rows_for("nfr_requirements", did, db, category="portability")
        assert "NFR-016" in {r["row_key"] for r in port}


async def test_idempotent_regen_no_new_versions(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.models.nfr import NfrRequirement
    from app.services.artifacts import nfr_orchestrator as O
    proj, _ = nfr_ctx
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    did = await _doc_id(proj.id)
    async with AsyncSessionLocal() as db:
        # all current requirement rows should still be version 1 (no churn on identical regen)
        rows = (await db.execute(select(NfrRequirement).where(
            NfrRequirement.document_id == did, NfrRequirement.is_current.is_(True),
            NfrRequirement.status == "active"))).scalars().all()
        assert rows and all(r.version == 1 for r in rows)


async def test_feeds_frs_soft(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.services.artifacts import nfr_orchestrator as O
    from app.services.context.project_context import gather_project_context
    from app.services.context.projection import project_for_unit
    proj, uid = nfr_ctx
    async with AsyncSessionLocal() as db:
        await O.generate_nfr_all(proj, db)
    async with AsyncSessionLocal() as db:
        await O.validate_nfr(proj.id, db, uid)

    async with AsyncSessionLocal() as db:
        fb = await gather_project_context(proj.id, db, artifact_type="frs")
        assert fb.nfr is not None and fb.nfr.nfr_status == "validated"
        assert fb.readiness.nfr_ready is True  # tracked
        uc = project_for_unit(fb, "frs", "modularize")
        assert "Validated NFR Drivers" in uc.combined  # soft-injected


# ── API-level tests (HTTP, gate + Celery-mock in-process path) ──────────────────

async def _make_project(*, brd_status: str | None, cb_validated: bool = False):
    """Create a user + project + optional BRD/CB artifact docs. Returns (pid, uid)."""
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.project import Project
    from app.models.user import User
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(User(id=uid, email=f"nfrapi-{uid}@specforge.test", display_name="NFR API",
                    password_hash="x", role="platform_admin", status="active"))
        await db.commit()
    async with AsyncSessionLocal() as db:
        proj = Project(name=f"ztest-nfr-{uuid.uuid4().hex[:8]}", owner_id=uid)
        db.add(proj)
        await db.flush()
        if brd_status:
            db.add(ArtifactDocument(project_id=proj.id, artifact_type="brd", status=brd_status))
        if cb_validated:
            db.add(ArtifactDocument(project_id=proj.id, artifact_type="concept_brief", status="validated"))
        await db.commit()
        return proj.id, uid


async def _cleanup(pid, uid):
    from app.db import AsyncSessionLocal
    from app.models.project import Project
    from app.models.user import User
    async with AsyncSessionLocal() as db:
        p = await db.get(Project, pid)
        if p:
            await db.delete(p)
        u = await db.get(User, uid)
        if u:
            await db.delete(u)
        await db.commit()


async def test_api_generate_gated_on_validated_brd(client):
    pid, uid = await _make_project(brd_status="in_interview")
    try:
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/generate", json={})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "brd_not_validated"
    finally:
        await _cleanup(pid, uid)


async def test_api_full_flow(client):
    pid, uid = await _make_project(brd_status="validated", cb_validated=True)
    try:
        # generate (mock → in-process)
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/generate",
                              json={"brief": "p99 < 800ms; WCAG 2.2 AA"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert len(data["sections"]["nfr_requirements"]) == 15
        assert len(data["radar"]) == 7

        # validate → ok
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/validate")
        assert r.status_code == 200 and r.json()["data"]["ok"] is True

        # add a glossary row via the generic add route
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/nfr_glossary/add",
                              json={"fields": {"term": "TPS", "definition": "Transactions per second"}})
        assert r.status_code == 200
        gid = r.json()["data"]["id"]
        rk = r.json()["data"]["row_key"]

        # edit it, then history shows 2 versions
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/nfr_glossary/{gid}/edit",
                              json={"fields": {"definition": "edited"}})
        assert r.status_code == 200 and r.json()["data"]["version"] == 2
        r = await client.get(f"/api/projects/{pid}/artifacts/nfr/nfr_glossary/{r.json()['data']['id']}/history")
        assert r.status_code == 200 and len(r.json()["data"]) == 2

        # add a requirement linked to a (nonexistent) BRD row → 422
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/nfr_requirements/add",
                              json={"fields": {"category": "security", "attribute": "X", "requirement": "Y",
                                               "priority": "must", "measurement": "Z"},
                                    "brd_links": [{"target_kind": "brd_objective", "target_ref": "OBJ-DOESNOTEXIST"}]})
        assert r.status_code == 422

        # export markdown
        r = await client.get(f"/api/projects/{pid}/artifacts/nfr/export")
        assert r.status_code == 200 and "Non-Functional Requirements" in r.text

        # enhance the ad-hoc brief
        r = await client.post(f"/api/projects/{pid}/artifacts/nfr/enhance",
                              json={"brief_text": "make it fast and secure"})
        assert r.status_code == 200 and "enhanced_brief" in r.json()["data"]

        # findings (read-only)
        r = await client.get(f"/api/projects/{pid}/artifacts/nfr/findings")
        assert r.status_code == 200 and "summary" in r.json()["data"]
    finally:
        await _cleanup(pid, uid)


# ── Phase 4: soft FRS↔NFR coupling findings (never block FRS) ───────────────────

async def _seed_frs_and_nfr(pid, *, nfr_validated: bool):
    """Create a minimal designed FRS + (optionally validated) NFR with one requirement."""
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.frs import FrsModule, FrsSpec
    from app.models.nfr import NfrRequirement

    def _mix(**kw):
        return dict(version=1, is_current=True, is_locked=False, status="active", source="ai", **kw)

    async with AsyncSessionLocal() as db:
        frs = ArtifactDocument(project_id=pid, artifact_type="frs", status="validated")
        nfr = ArtifactDocument(project_id=pid, artifact_type="nfr",
                               status="validated" if nfr_validated else "in_interview")
        db.add_all([frs, nfr])
        await db.flush()
        db.add(FrsModule(document_id=frs.id, row_key="MOD-001", name="Payments", slug="payments", **_mix()))
        db.add(FrsSpec(document_id=frs.id, row_key="M001-FRS001", module_row_key="MOD-001",
                       title="Initiate Payment", completeness=80, **_mix()))
        db.add(NfrRequirement(document_id=nfr.id, row_key="NFR-001", category="performance",
                              attribute="Latency", requirement="p95 < 300ms", priority="must", **_mix()))
        await db.commit()
        return frs.id


async def test_frs_nfr_drivers_missing_is_minor_non_blocking(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.services.artifacts.validators.frs import run_frs_validation
    proj, _ = nfr_ctx
    frs_id = await _seed_frs_and_nfr(proj.id, nfr_validated=True)
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, frs_id)
        findings = await run_frs_validation(frs_id, doc, db)
    missing = [f for f in findings if f["check_id"] == "nfr_drivers_missing"]
    assert len(missing) == 1 and missing[0]["group"] == "minor"
    # never blocks FRS
    assert all(f["check_id"] != "nfr_drivers_missing" for f in findings if f["group"] in ("critical", "major"))


async def test_frs_nfr_drivers_absent_when_nfr_unvalidated(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.services.artifacts.validators.frs import run_frs_validation
    proj, _ = nfr_ctx
    frs_id = await _seed_frs_and_nfr(proj.id, nfr_validated=False)
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, frs_id)
        findings = await run_frs_validation(frs_id, doc, db)
    assert not [f for f in findings if f["check_id"] in ("nfr_drivers_missing", "nfr_drivers_stale")]


async def test_frs_nfr_drivers_stale_is_minor(nfr_ctx):
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.frs import FrsTraceability
    from app.services.artifacts.validators.frs import run_frs_validation
    proj, _ = nfr_ctx
    frs_id = await _seed_frs_and_nfr(proj.id, nfr_validated=True)
    async with AsyncSessionLocal() as db:
        db.add(FrsTraceability(document_id=frs_id, source_table="frs_specs",
                               source_row_key="M001-FRS001", target_kind="nfr_driver",
                               target_ref="NFR-999"))  # dangling
        await db.commit()
        doc = await db.get(ArtifactDocument, frs_id)
        findings = await run_frs_validation(frs_id, doc, db)
    stale = [f for f in findings if f["check_id"] == "nfr_drivers_stale"]
    assert len(stale) == 1 and stale[0]["group"] == "minor" and stale[0]["target_ref"] == "NFR-999"
