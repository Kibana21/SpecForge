from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_project_or_404
from app.db import get_db
from app.models.document import Document
from app.models.gap import GapQuestion
from app.models.project import Project
from app.models.spec import SpecVersion
from app.models.user import User
from app.schemas.document import DocumentRead
from app.schemas.envelope import ok
from app.schemas.project import ProjectCreate, ProjectDetail, ProjectListItem, ProjectRead

router = APIRouter(tags=["projects"])


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(name=body.name, description=body.description, owner_id=current_user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ok(ProjectRead.model_validate(project).model_dump(mode="json"))


@router.get("/projects")
async def list_projects(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = min(limit, 100)

    doc_count_sq = (
        select(func.count(Document.id))
        .where(Document.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    latest_spec_sq = (
        select(SpecVersion.spec_type)
        .where(SpecVersion.project_id == Project.id)
        .order_by(SpecVersion.updated_at.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )

    rows = (
        await db.execute(
            select(
                Project,
                doc_count_sq.label("doc_count"),
                latest_spec_sq.label("latest_spec_type"),
            )
            .where(Project.deleted_at.is_(None))
            .order_by(Project.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    total = await db.scalar(
        select(func.count(Project.id)).where(Project.deleted_at.is_(None))
    )

    items = []
    for project, doc_count, latest_spec_type in rows:
        item = ProjectListItem.model_validate(project)
        item.doc_count = doc_count or 0
        item.latest_spec_type = latest_spec_type
        items.append(item.model_dump(mode="json"))

    return ok(items, {"total": total or 0, "limit": limit, "offset": offset})


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    gap_row = (
        await db.execute(
            select(
                func.count(GapQuestion.id).label("total"),
                func.count(GapQuestion.id)
                .filter(GapQuestion.resolved.is_(False))
                .label("unresolved"),
            ).where(GapQuestion.project_id == project_id)
        )
    ).one()

    spec_rows = (
        await db.execute(
            select(SpecVersion)
            .where(SpecVersion.project_id == project_id)
            .order_by(SpecVersion.spec_type, SpecVersion.version_number.desc())
        )
    ).scalars().all()

    latest_specs: dict = {}
    for s in spec_rows:
        if s.spec_type not in latest_specs:
            latest_specs[s.spec_type] = {
                "id": str(s.id),
                "spec_type": s.spec_type,
                "version_number": s.version_number,
                "is_edited": s.is_edited,
                "updated_at": s.updated_at.isoformat(),
            }

    detail = ProjectDetail.model_validate(project)
    detail.documents = [DocumentRead.model_validate(d).model_dump(mode="json") for d in project.documents]
    detail.gap_count = gap_row.total
    detail.unresolved_gap_count = gap_row.unresolved
    detail.latest_specs = latest_specs
    return ok(detail.model_dump(mode="json"))


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return ok({"id": str(project_id)})
