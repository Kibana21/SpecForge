"""P1 — Project Wiki core (mock-mode).

Verifies the shared compile core produces ProjectWikiSummary + ProjectWikiConcept
rows for a project document, mirroring the App Brain wiki, without touching E1.
Runs against real Postgres with mock LLM (conftest sets LLM_PROVIDER=mock).
"""
import uuid

import pytest
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models.document import Document
from app.models.project import Project
from app.models.project_wiki import ProjectWikiConcept, ProjectWikiSummary


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_compile_project_doc_creates_wiki_rows():
    from workers.tasks import _compile_one_project_doc

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        project = Project(name=f"PWiki Test {_suffix()}", description="claims intake automation")
        db.add(project)
        await db.flush()

        doc = Document(
            project_id=project.id,
            filename=f"claims-spec-{_suffix()}.md",
            mime_type="text/markdown",
            size_bytes=2048,
            storage_path=f"/tmp/{_suffix()}.md",
            extracted_text="# Claims Intake\n\nThe system automates claim triage and retention.",
            parse_status="done",
            indexing_status="done",
        )
        db.add(doc)
        await db.flush()

        try:
            touched = await _compile_one_project_doc(db, project, doc, settings)
            await db.commit()

            assert touched >= 1, "mock compile should touch at least the 'overview' concept"

            summaries = (await db.execute(
                select(ProjectWikiSummary).where(ProjectWikiSummary.project_id == project.id)
            )).scalars().all()
            assert len(summaries) == 1
            assert summaries[0].document_id == doc.id
            assert summaries[0].content_md

            concepts = (await db.execute(
                select(ProjectWikiConcept).where(ProjectWikiConcept.project_id == project.id)
            )).scalars().all()
            assert len(concepts) >= 1
            assert any(c.slug == "overview" for c in concepts)
            # Every concept is attributed to its source doc.
            assert all(str(doc.id) in c.source_doc_ids for c in concepts)
        finally:
            await db.execute(delete(Project).where(Project.id == project.id))
            await db.commit()


@pytest.mark.asyncio
async def test_compile_handles_project_deleted_mid_flight(monkeypatch):
    """If the project is deleted during the (slow) LLM compile, the task exits
    cleanly with 'project_deleted' instead of crashing on the FK violation."""
    import workers.tasks as tasks

    async with AsyncSessionLocal() as db:
        project = Project(name=f"PWiki Race {_suffix()}")
        db.add(project)
        await db.flush()
        doc = Document(
            project_id=project.id, filename=f"d-{_suffix()}.md", mime_type="text/markdown",
            size_bytes=10, storage_path=f"/tmp/{_suffix()}", extracted_text="hello world",
            parse_status="done", indexing_status="done",
        )
        db.add(doc)
        await db.commit()
        project_id, doc_id = str(project.id), str(doc.id)

    # Simulate the race: delete the project from under the running compile, then
    # raise the same kind of error the FK violation would surface as.
    async def _boom(db, project, doc, settings):
        async with AsyncSessionLocal() as other:
            await other.execute(delete(Project).where(Project.id == uuid.UUID(project_id)))
            await other.commit()
        raise RuntimeError("insert ... violates foreign key constraint")

    monkeypatch.setattr(tasks, "_compile_one_project_doc", _boom)

    result = await tasks._compile_project_wiki_for_doc(project_id, doc_id)
    assert result == {"ok": False, "error": "project_deleted"}


@pytest.mark.asyncio
async def test_compile_project_doc_is_idempotent_overview():
    """Recompiling the same doc updates (not duplicates) the 'overview' concept."""
    from workers.tasks import _compile_one_project_doc

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        project = Project(name=f"PWiki Idem {_suffix()}")
        db.add(project)
        await db.flush()
        doc = Document(
            project_id=project.id, filename=f"d-{_suffix()}.md", mime_type="text/markdown",
            size_bytes=10, storage_path=f"/tmp/{_suffix()}", extracted_text="hello world",
            parse_status="done", indexing_status="done",
        )
        db.add(doc)
        await db.flush()
        try:
            await _compile_one_project_doc(db, project, doc, settings)
            await db.flush()
            await _compile_one_project_doc(db, project, doc, settings)
            await db.commit()

            concepts = (await db.execute(
                select(ProjectWikiConcept).where(
                    ProjectWikiConcept.project_id == project.id,
                    ProjectWikiConcept.slug == "overview",
                )
            )).scalars().all()
            assert len(concepts) == 1  # upsert, not duplicate
        finally:
            await db.execute(delete(Project).where(Project.id == project.id))
            await db.commit()
