"""FRS exporter tests.

Verifies the zip bundle structure + content rendered from the live DB state.
Uses the Stage B test setup (Stage A → design MOD-001) so there's at least
one designed spec to render.
"""
import csv
import io
import zipfile
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


async def _seed_validated_brd(client, project_id: str) -> None:
    from datetime import datetime, timezone
    import uuid
    from app.db import AsyncSessionLocal
    from app.models.artifact import ArtifactDocument
    from app.models.brd import BrdBusinessRequirement
    async with AsyncSessionLocal() as db:
        cb = ArtifactDocument(
            project_id=uuid.UUID(project_id), artifact_type="concept_brief",
            status="validated", validated_at=datetime.now(timezone.utc),
            validated_snapshot_key="t",
        )
        brd = ArtifactDocument(
            project_id=uuid.UUID(project_id), artifact_type="brd",
            status="validated", validated_at=datetime.now(timezone.utc),
            validated_snapshot_key="t",
        )
        db.add_all([cb, brd])
        await db.flush()
        for i in range(1, 9):
            db.add(BrdBusinessRequirement(
                document_id=brd.id, row_key=f"BR-{i:03d}",
                version=1, is_current=True, is_locked=False,
                status="active", source="ai",
                title=f"Test BR {i}",
                description=f"Description for BR-{i:03d}",
                priority="must", category="functional",
                acceptance_criteria=[], objective_refs=[], stakeholder_refs=[],
                rationale="", completeness=95, confidence="high",
            ))
        await db.commit()


async def _setup_with_designed_module(client) -> str:
    p = await client.post("/api/projects", json={
        "name": f"FRS EXP {uuid4().hex[:6]}",
        "description": "Exporter test",
        "business_unit": "Operations",
    })
    project_id = p.json()["data"]["id"]
    await _seed_validated_brd(client, project_id)
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/generate",
        json={"brief": "Exporter test setup"},
    )
    await client.post(
        f"/api/projects/{project_id}/artifacts/frs/modules/MOD-001/design",
    )
    return project_id


# ─── Tests ──────────────────────────────────────────────────────────────────


async def test_exporter_zip_top_level_structure(client):
    """Zip contains README + modules/ + specs/ + traceability/."""
    project_id = await _setup_with_designed_module(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/export")
    assert res.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(res.content))
    names = z.namelist()
    assert "README.md" in names
    assert any(n.startswith("modules/") and n.endswith(".md") for n in names)
    assert any(n.startswith("specs/") and n.endswith(".md") for n in names)
    assert "traceability/br-to-frs.md" in names
    assert "traceability/nfr-to-frs.md" in names
    assert "traceability/module-to-frs.md" in names
    assert "traceability/matrix.csv" in names


async def test_exporter_readme_has_counts(client):
    """README mentions module + spec + traceability counts."""
    project_id = await _setup_with_designed_module(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/export")
    z = zipfile.ZipFile(io.BytesIO(res.content))
    readme = z.read("README.md").decode("utf-8")
    assert "Modules:" in readme
    assert "FRS specs:" in readme
    assert "Traceability rows:" in readme


async def test_exporter_spec_file_renders_template_sections(client):
    """One spec file contains the canonical template section headings."""
    project_id = await _setup_with_designed_module(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/export")
    z = zipfile.ZipFile(io.BytesIO(res.content))
    spec_files = [n for n in z.namelist() if n.startswith("specs/")]
    assert len(spec_files) >= 1
    sample = z.read(spec_files[0]).decode("utf-8")
    # Section headers per templates/frs-template.md
    for header in (
        "## Intent / Narrative",
        "## Detailed Design",
        "### 1. UI Specification",
        "### 2. Backend Service Specification",
        "### 3. Data / Storage / Cache Specification",
        "### 4. Cross-Cutting Specifications",
        "## Independent Test",
        "## Acceptance Scenarios",
        "## Functional Requirements",
    ):
        assert header in sample, f"missing '{header}' in spec file"


async def test_exporter_module_file_renders_sections(client):
    """A module file contains scope / actors / responsibilities / interfaces / FRS backlog headers."""
    project_id = await _setup_with_designed_module(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/export")
    z = zipfile.ZipFile(io.BytesIO(res.content))
    module_files = [n for n in z.namelist() if n.startswith("modules/")]
    assert len(module_files) >= 1
    sample = z.read(module_files[0]).decode("utf-8")
    for header in (
        "## Scope", "## Actors and Dependencies",
        "## Responsibilities", "## Interfaces",
        "## Data", "## FRS Backlog",
    ):
        assert header in sample, f"missing '{header}' in module file"


async def test_exporter_matrix_csv_has_header_and_rows(client):
    """traceability/matrix.csv has the documented columns + ≥1 row."""
    project_id = await _setup_with_designed_module(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/export")
    z = zipfile.ZipFile(io.BytesIO(res.content))
    raw = z.read("traceability/matrix.csv").decode("utf-8")
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    assert len(rows) >= 2, "expected header + at least one data row"
    header = rows[0]
    assert header == [
        "source_table", "source_row_key", "target_kind", "target_ref",
        "target_label", "confidence",
    ]


async def test_exporter_br_to_frs_includes_covered_brs(client):
    """br-to-frs.md mentions at least one BR-XXX that the fixture covers."""
    project_id = await _setup_with_designed_module(client)
    res = await client.get(f"/api/projects/{project_id}/artifacts/frs/export")
    z = zipfile.ZipFile(io.BytesIO(res.content))
    body = z.read("traceability/br-to-frs.md").decode("utf-8")
    # Fixture covers BR-001
    assert "BR-001" in body
