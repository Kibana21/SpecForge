"""P3 — Clarification Engine (mock-mode).

The clarifier writes cited GapQuestion(source="clarifier") rows, is idempotent on
unresolved rows, and never touches RU's source="interview" rows.
"""
import uuid

import pytest
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.services.understanding.clarifier import run_clarification


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_clarifier_writes_cited_rows_and_preserves_interview():
    settings = get_settings()
    from workers.tasks import _compile_one_project_doc

    async with AsyncSessionLocal() as db:
        project = Project(name=f"Clarify {_suffix()}", description="claims platform")
        db.add(project)
        await db.flush()

        # A pre-existing RU interview gap question must survive the clarifier run.
        db.add(GapQuestion(
            project_id=project.id, ext_id="Q-001", question="interview Q",
            category="scope", severity="minor", source="interview",
        ))
        # Compile a doc so the wiki has ≥1 concept for the clarifier to reason over.
        doc = Document(
            project_id=project.id, filename=f"d-{_suffix()}.md", mime_type="text/markdown",
            size_bytes=20, storage_path=f"/tmp/{_suffix()}", extracted_text="retention policy and SLA",
            parse_status="done", indexing_status="done",
        )
        db.add(doc)
        await db.flush()
        await _compile_one_project_doc(db, project, doc, settings)
        await db.commit()

        try:
            items = await run_clarification(project.id, db, trigger="interview")
            assert len(items) == 3  # from corpus_clarifier.json fixture

            clar = (await db.execute(
                select(GapQuestion).where(
                    GapQuestion.project_id == project.id, GapQuestion.source == "clarifier"
                )
            )).scalars().all()
            assert len(clar) == 3
            kinds = {c.kind for c in clar}
            assert kinds == {"contradiction", "ambiguity", "gap"}
            # citations carried through; the contradiction row cites two concepts.
            contra = next(c for c in clar if c.kind == "contradiction")
            assert len(contra.citations) >= 2

            # RU interview row untouched.
            interview = (await db.execute(
                select(GapQuestion).where(
                    GapQuestion.project_id == project.id, GapQuestion.source == "interview"
                )
            )).scalars().all()
            assert len(interview) == 1

            # Idempotent: a second run keeps 3 (replaces unresolved), still 1 interview.
            await run_clarification(project.id, db, trigger="interview")
            clar2 = (await db.execute(
                select(GapQuestion).where(
                    GapQuestion.project_id == project.id, GapQuestion.source == "clarifier"
                )
            )).scalars().all()
            assert len(clar2) == 3
        finally:
            await db.execute(delete(Project).where(Project.id == project.id))
            await db.commit()
