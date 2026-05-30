import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404, get_provider_dep
from app.core import audit
from app.db import get_db
from app.limiter import limiter
from app.models.project import Project
from app.models.understanding import InterviewMessage, RequirementUnderstanding
from app.models.user import User
from app.schemas.envelope import err, ok
from app.schemas.understanding import (
    AnswerIn,
    InterviewMessageRead,
    RequirementUnderstandingRead,
)
from app.services import version_service
from app.services.llm.base import LLMProvider

log = logging.getLogger(__name__)
router = APIRouter(tags=["understanding"], dependencies=[Depends(get_current_user)])


async def _detail(project_id: UUID, db: AsyncSession) -> dict:
    ru = (
        await db.execute(
            select(RequirementUnderstanding).where(RequirementUnderstanding.project_id == project_id)
        )
    ).scalar_one_or_none()
    messages = (
        await db.execute(
            select(InterviewMessage)
            .where(InterviewMessage.project_id == project_id)
            .order_by(InterviewMessage.seq)
        )
    ).scalars().all()
    from app.models.gap import GapQuestion
    clarifs = (
        await db.execute(
            select(GapQuestion)
            .where(GapQuestion.project_id == project_id, GapQuestion.source == "clarifier")
            .order_by(GapQuestion.ext_id)
        )
    ).scalars().all()
    return {
        "understanding": RequirementUnderstandingRead.model_validate(ru).model_dump(mode="json") if ru else None,
        "messages": [InterviewMessageRead.model_validate(m).model_dump(mode="json") for m in messages],
        "clarifications": [
            {
                "id": str(c.id), "question": c.question, "kind": c.kind,
                "category": c.category, "severity": c.severity, "rationale": c.rationale,
                "citations": c.citations or [], "resolved": c.resolved,
                "resolution_text": c.resolution_text,
            }
            for c in clarifs
        ],
    }


@router.get("/projects/{project_id}/understanding")
async def get_understanding(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    return ok(await _detail(project_id, db))


@router.post("/projects/{project_id}/understanding/generate")
@limiter.limit("10/minute")
async def generate_understanding(
    request: Request,
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    """Synthesize the RU now from in-scope sources + app facts (the wizard's
    'Generate Understanding' action; also used to re-generate after new uploads)."""
    from app.services.understanding.orchestrator import generate

    await generate(project_id, db, provider)
    return ok(await _detail(project_id, db))


@router.post("/projects/{project_id}/understanding/answer")
@limiter.limit("20/minute")
async def answer_understanding(
    request: Request,
    project_id: UUID,
    body: AnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    provider: LLMProvider = Depends(get_provider_dep),
):
    from app.services.understanding.orchestrator import incorporate_answer

    await incorporate_answer(project_id, body.answer, db, provider, body.seq)
    return ok(await _detail(project_id, db))


class ClarificationAnswerIn(BaseModel):
    answer: str


@router.post("/projects/{project_id}/understanding/clarifications/{gq_id}/answer")
async def answer_clarification(
    project_id: UUID,
    gq_id: UUID,
    body: ClarificationAnswerIn,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a clarification question. Resolved answers flow into the Intake
    Context Pack and reach CB/BRD/FRS generation."""
    from datetime import timezone as _tz

    from app.models.gap import GapQuestion

    gq = (await db.execute(
        select(GapQuestion).where(
            GapQuestion.id == gq_id,
            GapQuestion.project_id == project_id,
            GapQuestion.source == "clarifier",
        )
    )).scalar_one_or_none()
    if gq is None:
        err("clarification_not_found", "Clarification question not found.", 404)
    gq.resolution_text = body.answer
    gq.resolved = True
    gq.resolved_at = datetime.now(_tz.utc)
    await db.commit()
    return ok(await _detail(project_id, db))


@router.post("/projects/{project_id}/understanding/validate")
async def validate_understanding(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The generation gate (BR-M1-012-3): a human approves the RU, unblocking M2."""
    ru = (
        await db.execute(
            select(RequirementUnderstanding).where(RequirementUnderstanding.project_id == project_id)
        )
    ).scalar_one_or_none()
    if ru is None:
        err("understanding_not_found", "No requirement understanding to validate.", 404)
    if not (ru.objective or "").strip():
        err("understanding_incomplete", "Requirement understanding has no objective yet.", 403)

    ru.status = "validated"
    ru.validated_at = datetime.now(timezone.utc)
    ru.validated_by = user.id
    project.ru_validated = True

    await version_service.create_snapshot(
        db,
        document_key=f"requirement_understanding:{project_id}",
        actor_id=user.id,
        generation_type="human",
        change_note="Requirement Understanding validated",
        is_immutable=True,
    )
    await audit.emit(db, event="understanding.validated", actor_id=str(user.id),
                     metadata={"project_id": str(project_id)})
    await db.commit()

    # Refresh similarity embedding now that the objective is locked (best-effort).
    from app.services.projects.embedding_service import upsert_project_embedding
    try:
        await upsert_project_embedding(project_id, db)
    except Exception:  # noqa: BLE001
        pass

    await db.refresh(ru)
    return ok({
        "ru_validated": True,
        "understanding": RequirementUnderstandingRead.model_validate(ru).model_dump(mode="json"),
    })
