from uuid import UUID

from fastapi import Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_user, require_role  # noqa: F401 — re-exported for routers
from app.db import get_db
from app.models.project import Project
from app.models.user import User
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


async def require_ru_validated(
    project: Project = Depends(get_project_or_404),
) -> Project:
    """Generation gate (BR-M1-012-3): downstream spec generation is blocked until a
    human validates the Requirement Understanding."""
    if not project.ru_validated:
        err(
            "understanding_not_validated",
            "Requirement Understanding must be validated before generating specs.",
            409,
        )
    return project  # type: ignore[return-value]


async def require_project_access(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Returns the project if the user has access; 404 for both not-found and unauthorized."""
    from app.models.project import ProjectMember  # noqa: PLC0415

    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if project is None:
        err("not_found", "Project not found", 404)

    is_admin = user.role == "platform_admin"
    is_owner = project.owner_id == user.id  # type: ignore[union-attr]
    member_result = await db.execute(
        select(ProjectMember).where(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user.id,
            )
        )
    )
    is_member = member_result.scalar_one_or_none() is not None

    if not (is_admin or is_owner or is_member):
        err("not_found", "Project not found", 404)

    return project  # type: ignore[return-value]


def get_provider_dep() -> LLMProvider:
    return get_provider()


def require_artifact_validated(artifact_type: str):
    """Gate factory: 409 unless the artifact has status=validated."""
    async def _dep(
        project_id: UUID,
        db: AsyncSession = Depends(get_db),
    ) -> None:
        from sqlalchemy import select
        from app.models.artifact import ArtifactDocument
        doc = (
            await db.execute(
                select(ArtifactDocument).where(
                    ArtifactDocument.project_id == project_id,
                    ArtifactDocument.artifact_type == artifact_type,
                )
            )
        ).scalar_one_or_none()
        if doc is None or doc.status != "validated":
            err(
                f"{artifact_type}_not_validated",
                f"{artifact_type.replace('_', ' ').title()} must be validated first.",
                409,
            )
    return _dep
