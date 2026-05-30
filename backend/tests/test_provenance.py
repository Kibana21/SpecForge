"""P6 — Provenance lineage (mock-mode).

The lineage spine connects Documents → Concepts → Clarifications from existing
rows (concept tree_node_refs + clarification citations).
"""
import uuid

import pytest
from sqlalchemy import delete

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.services.provenance.lineage import build_lineage


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_lineage_connects_docs_concepts_clarifications():
    settings = get_settings()
    from workers.tasks import _compile_one_project_doc

    async with AsyncSessionLocal() as db:
        project = Project(name=f"Lineage {_suffix()}", description="claims")
        db.add(project)
        await db.flush()
        doc = Document(
            project_id=project.id, filename=f"src-{_suffix()}.md", mime_type="text/markdown",
            size_bytes=20, storage_path=f"/tmp/{_suffix()}", extracted_text="retention and settlement",
            parse_status="done", indexing_status="done",
        )
        db.add(doc)
        await db.flush()
        await _compile_one_project_doc(db, project, doc, settings)
        # A clarification citing the 'overview' concept (created by mock compile).
        db.add(GapQuestion(
            project_id=project.id, ext_id="CL-001", question="Conflict?",
            category="data", severity="blocker", source="clarifier", kind="contradiction",
            citations=["C:overview"],
        ))
        await db.commit()

        try:
            lin = await build_lineage(project.id, db)
            assert any(c["slug"] == "overview" for c in lin["concepts"])
            # The 'overview' concept is grounded in our document.
            ov = next(c for c in lin["concepts"] if c["slug"] == "overview")
            assert str(doc.id) in ov["doc_ids"]
            # The clarification links to the 'overview' concept.
            assert len(lin["clarifications"]) == 1
            assert "overview" in lin["clarifications"][0]["concept_slugs"]
            # The document surfaces in the lineage (it's referenced by the concept).
            assert any(d["id"] == str(doc.id) for d in lin["documents"])
        finally:
            await db.execute(delete(Project).where(Project.id == project.id))
            await db.commit()
