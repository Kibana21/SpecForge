from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project import Project
from app.schemas.envelope import err
from app.services.llm import get_provider
from app.services.llm.base import LLMProvider


async def get_project_or_404(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if project is None:
        err("not_found", f"Project {project_id} not found", 404)
    return project  # type: ignore[return-value]


def get_provider_dep() -> LLMProvider:
    return get_provider()
