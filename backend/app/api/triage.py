from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.project_intake import TriageItem
from app.models.user import User
from app.schemas.envelope import ok
from app.schemas.triage import TriageItemRead

router = APIRouter(tags=["triage"])


@router.get("/triage")
async def list_triage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Prioritized, personalized triage worklist (BR-M1-005). If nothing is
    materialized yet (Beat hasn't run), compute on demand."""
    items = (
        await db.execute(
            select(TriageItem)
            .where(TriageItem.user_id == current_user.id)
            .order_by(TriageItem.priority)
        )
    ).scalars().all()

    if not items:
        from app.services.portfolio.triage_service import compute_for_user
        items = await compute_for_user(current_user.id, db)

    computed_at = items[0].computed_at.isoformat() if items else None
    next_at = items[0].next_at.isoformat() if items and items[0].next_at else None
    return ok(
        [TriageItemRead.model_validate(i).model_dump(mode="json") for i in items],
        {"computed_at": computed_at, "next_at": next_at},
    )
