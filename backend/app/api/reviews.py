from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_or_404
from app.db import get_db
from app.models.project import Project
from app.models.review import ReviewComment
from app.schemas.envelope import err, ok
from app.schemas.review import ReviewCommentRead, ReviewDismissPatch

router = APIRouter(tags=["reviews"])


@router.get("/projects/{project_id}/reviews")
async def list_reviews(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(ReviewComment)
            .where(ReviewComment.project_id == project_id)
            .order_by(ReviewComment.severity, ReviewComment.created_at)
        )
    ).scalars().all()
    return ok([ReviewCommentRead.model_validate(r).model_dump(mode="json") for r in rows])


@router.patch("/projects/{project_id}/reviews/{comment_id}")
async def dismiss_review(
    project_id: UUID,
    comment_id: UUID,
    body: ReviewDismissPatch,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    comment = (
        await db.execute(
            select(ReviewComment).where(
                ReviewComment.id == comment_id, ReviewComment.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if comment is None:
        err("not_found", f"Review comment {comment_id} not found", 404)

    comment.dismissed = body.dismissed
    comment.dismissed_at = datetime.now(timezone.utc) if body.dismissed else None
    await db.commit()
    await db.refresh(comment)
    return ok(ReviewCommentRead.model_validate(comment).model_dump(mode="json"))
