from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_or_404
from app.db import get_db
from app.models.gap import GapQuestion
from app.models.project import Project
from app.schemas.envelope import err, ok
from app.schemas.gap import GapQuestionRead, GapResolvePatch

router = APIRouter(tags=["gaps"])


@router.patch("/projects/{project_id}/gaps/{gap_id}")
async def resolve_gap(
    project_id: UUID,
    gap_id: UUID,
    body: GapResolvePatch,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    gap = (
        await db.execute(
            select(GapQuestion).where(
                GapQuestion.id == gap_id, GapQuestion.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if gap is None:
        err("not_found", f"Gap {gap_id} not found", 404)

    gap.resolved = body.resolved
    gap.resolution_text = body.resolution_text
    gap.resolved_at = datetime.now(timezone.utc) if body.resolved else None
    await db.commit()
    await db.refresh(gap)
    return ok(GapQuestionRead.model_validate(gap).model_dump(mode="json"))
