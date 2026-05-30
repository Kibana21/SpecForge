"""P4 — Intake Context Pack reaches downstream generation context (mock-mode).

A resolved clarification + the RU understanding + wiki concept briefs must appear
in project_for_unit(...).combined, the single chokepoint CB/BRD/FRS consume.
"""
import uuid

import pytest
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.understanding import RequirementUnderstanding
from app.services.context.project_context import gather_project_context
from app.services.context.projection import project_for_unit


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_resolved_clarification_reaches_combined_context():
    settings = get_settings()
    from workers.tasks import _compile_one_project_doc

    async with AsyncSessionLocal() as db:
        project = Project(name=f"Intake {_suffix()}", description="claims settlement")
        db.add(project)
        await db.flush()

        # RU understanding (would otherwise be siloed).
        db.add(RequirementUnderstanding(
            project_id=project.id, objective="Automate claim settlement",
            content_json={"objective": "Automate claim settlement", "systems": ["Guidewire"]},
            status="validated",
        ))
        # A resolved clarification.
        db.add(GapQuestion(
            project_id=project.id, ext_id="CL-001", question="What retention applies?",
            category="data", severity="blocker", source="clarifier", kind="contradiction",
            citations=["C:data_retention"], resolved=True, resolution_text="7 years per compliance.",
        ))
        # A doc → wiki concept brief.
        doc = Document(
            project_id=project.id, filename=f"d-{_suffix()}.md", mime_type="text/markdown",
            size_bytes=20, storage_path=f"/tmp/{_suffix()}", extracted_text="settlement and retention",
            parse_status="done", indexing_status="done",
        )
        db.add(doc)
        await db.flush()
        await _compile_one_project_doc(db, project, doc, settings)
        await db.commit()

        try:
            bundle = await gather_project_context(project.id, db, artifact_type="brd")
            assert bundle.intake.understanding.get("objective") == "Automate claim settlement"
            assert len(bundle.intake.resolved_clarifications) == 1
            assert len(bundle.intake.wiki_concepts) >= 1

            unit = project_for_unit(bundle, "brd", "business_requirements")
            assert "Project Understanding (Intake)" in unit.combined
            assert "Automate claim settlement" in unit.combined
            assert "7 years per compliance." in unit.combined   # the clarification ANSWER
        finally:
            await db.execute(delete(Project).where(Project.id == project.id))
            await db.commit()
