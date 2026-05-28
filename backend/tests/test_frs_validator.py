"""FRS Stage-A validator unit tests.

Tests each rule in isolation by constructing minimal data via direct DB inserts.
Faster than the full pipeline E2E tests in test_frs_orchestrator.py.
"""
import uuid
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.services.artifacts.validators.frs import (
    _TECH_TOKENS,
    _detect_cross_module_cycle,
    run_frs_validation,
    summarize_findings,
)

pytestmark = pytest.mark.asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────


class _MockIface:
    def __init__(self, mod, dir, ctr, name="x"):
        self.module_row_key = mod
        self.direction = dir
        self.counterpart = ctr
        self.name = name
        self.interface_kind = "api"


async def _create_frs_doc(client, project_name: str) -> tuple[str, str]:
    """Create a fresh project + empty FRS doc. Returns (project_id, frs_doc_id)."""
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument

    p = await client.post("/api/projects", json={
        "name": f"{project_name} {uuid4().hex[:6]}",
        "description": "Validator test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]

    # Insert a fresh FRS doc directly (without running modularize)
    async with AsyncSessionLocal() as db:
        doc = ArtifactDocument(
            project_id=uuid.UUID(project_id),
            artifact_type="frs",
            status="in_interview",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return project_id, str(doc.id)


async def _insert_module(
    doc_id: str, row_key: str, name: str = "Test", layer: str = "vertical",
) -> str:
    """Insert a minimal current+active module row. Returns the row id as str."""
    from app.db import AsyncSessionLocal
    from app.models.frs import FrsModule
    async with AsyncSessionLocal() as db:
        mod = FrsModule(
            document_id=uuid.UUID(doc_id),
            row_key=row_key, version=1, is_current=True, is_locked=False,
            status="active", source="ai",
            name=name, slug=row_key.lower(), layer=layer,
            scope_in="", scope_out="", summary="",
            completeness=0, confidence="low",
        )
        db.add(mod)
        await db.commit()
        await db.refresh(mod)
        return str(mod.id)


async def _insert_stub(doc_id: str, row_key: str, module_row_key: str, br_refs: list[str]):
    """Insert a minimal frs_specs stub."""
    from app.db import AsyncSessionLocal
    from app.models.frs import FrsSpec
    async with AsyncSessionLocal() as db:
        s = FrsSpec(
            document_id=uuid.UUID(doc_id),
            row_key=row_key, version=1, is_current=True, is_locked=False,
            status="active", source="ai",
            module_row_key=module_row_key,
            title=row_key, priority="P0", layer="vertical",
            br_refs=br_refs, nfr_refs=[], depends_on=[],
            narrative="", independent_test="", data_and_validation="",
            errors_and_edge_cases="", observability="", implementation_tasks=[],
            completeness=0, confidence="low",
        )
        db.add(s)
        await db.commit()


# ── Pure-function tests (no DB) ───────────────────────────────────────────────


def test_cycle_detector_finds_3_node_cycle():
    """A → B → C → A is detected as a cycle."""
    ifaces = [
        _MockIface("A", "outbound", "B"),
        _MockIface("B", "outbound", "C"),
        _MockIface("C", "outbound", "A"),
    ]
    cycle = _detect_cross_module_cycle(ifaces)
    assert cycle is not None
    # First and last entry are the same (the cycle anchor)
    assert cycle[0] == cycle[-1]


def test_cycle_detector_acyclic_chain():
    """A → B → C with no cycle returns None."""
    ifaces = [
        _MockIface("A", "outbound", "B"),
        _MockIface("B", "outbound", "C"),
    ]
    assert _detect_cross_module_cycle(ifaces) is None


def test_cycle_detector_ignores_inbound():
    """Inbound interfaces don't count toward the graph."""
    ifaces = [
        _MockIface("A", "outbound", "B"),
        _MockIface("B", "inbound", "A"),  # not outbound — ignored
    ]
    assert _detect_cross_module_cycle(ifaces) is None


def test_summarize_findings_counts_blocking():
    """summarize_findings reports critical+major as blocking."""
    findings = [
        {"group": "critical", "check_id": "x"},
        {"group": "major", "check_id": "y"},
        {"group": "warnings", "check_id": "z"},
        {"group": "coverage", "check_id": "w"},
    ]
    s = summarize_findings(findings)
    assert s["total"] == 4
    assert s["critical"] == 1
    assert s["major"] == 1
    assert s["warnings"] == 1
    assert s["coverage"] == 1
    assert s["blocking"] == 2


def test_tech_tokens_include_common_offenders():
    """Common tech-name violations are in the rejection list."""
    for tok in ("api", "service", "db", "lambda", "kafka", "microservice"):
        assert tok in _TECH_TOKENS


# ── DB-backed tests (full validator run) ──────────────────────────────────────


async def test_validator_zero_modules_is_critical(client):
    """A doc with no modules raises critical finding."""
    project_id, doc_id = await _create_frs_doc(client, "ZeroModules")
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, uuid.UUID(doc_id))
        findings = await run_frs_validation(uuid.UUID(doc_id), doc, db)

    by_check = [f["check_id"] for f in findings]
    assert "zero_modules" in by_check
    crit = [f for f in findings if f["check_id"] == "zero_modules"][0]
    assert crit["group"] == "critical"


async def test_validator_module_zero_backlog_critical(client):
    """A module with no backlog stubs raises critical finding."""
    project_id, doc_id = await _create_frs_doc(client, "ZeroBacklog")
    await _insert_module(doc_id, "MOD-001", "Onboarding")
    # No stub inserted

    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, uuid.UUID(doc_id))
        findings = await run_frs_validation(uuid.UUID(doc_id), doc, db)

    by_check = [(f["check_id"], f["row_key"]) for f in findings]
    assert ("module_zero_backlog", "MOD-001") in by_check
    crit = [f for f in findings if f["check_id"] == "module_zero_backlog"][0]
    assert crit["group"] == "critical"


async def test_validator_capability_language_rejects_api_suffix(client):
    """A module named 'Auth API' triggers major finding."""
    project_id, doc_id = await _create_frs_doc(client, "TechName")
    await _insert_module(doc_id, "MOD-001", "Auth API")
    await _insert_stub(doc_id, "M001-FRS001", "MOD-001", ["BR-001"])

    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, uuid.UUID(doc_id))
        findings = await run_frs_validation(uuid.UUID(doc_id), doc, db)

    tech_findings = [f for f in findings if f["check_id"] == "module_tech_name"]
    assert len(tech_findings) == 1
    assert tech_findings[0]["row_key"] == "MOD-001"
    assert tech_findings[0]["group"] == "major"


async def test_validator_capability_language_accepts_clean_names(client):
    """A module named 'Customer Onboarding' does NOT trigger the tech-name rule."""
    project_id, doc_id = await _create_frs_doc(client, "CleanName")
    await _insert_module(doc_id, "MOD-001", "Customer Onboarding")
    await _insert_stub(doc_id, "M001-FRS001", "MOD-001", ["BR-001"])

    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, uuid.UUID(doc_id))
        findings = await run_frs_validation(uuid.UUID(doc_id), doc, db)

    tech_findings = [f for f in findings if f["check_id"] == "module_tech_name"]
    assert len(tech_findings) == 0


async def test_validator_under_decomposed_is_warning(client):
    """A module with exactly 1 backlog stub raises a warning."""
    project_id, doc_id = await _create_frs_doc(client, "UnderDec")
    await _insert_module(doc_id, "MOD-001", "Onboarding")
    await _insert_stub(doc_id, "M001-FRS001", "MOD-001", ["BR-001"])  # only 1

    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, uuid.UUID(doc_id))
        findings = await run_frs_validation(uuid.UUID(doc_id), doc, db)

    by_check = [(f["check_id"], f["row_key"]) for f in findings]
    assert ("module_under_decomposed", "MOD-001") in by_check
    warn = [f for f in findings if f["check_id"] == "module_under_decomposed"][0]
    assert warn["group"] == "warnings"


async def test_validator_no_findings_when_clean(client):
    """A module with 2+ stubs, capability-language name, no open decisions → 0 findings."""
    project_id, doc_id = await _create_frs_doc(client, "Clean")
    await _insert_module(doc_id, "MOD-001", "Customer Onboarding")
    await _insert_stub(doc_id, "M001-FRS001", "MOD-001", ["BR-001"])
    await _insert_stub(doc_id, "M001-FRS002", "MOD-001", ["BR-002"])

    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    async with AsyncSessionLocal() as db:
        doc = await db.get(ArtifactDocument, uuid.UUID(doc_id))
        findings = await run_frs_validation(uuid.UUID(doc_id), doc, db)

    # No critical or major; warnings/coverage may exist depending on whether
    # the project has a BRD (it doesn't in this test). BR coverage check
    # silently passes when there are no must-priority BRs.
    blocking = [f for f in findings if f["group"] in ("critical", "major")]
    assert len(blocking) == 0
