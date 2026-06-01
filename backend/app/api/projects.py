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
from app.schemas.assumption import AssumptionPatch
from app.schemas.document import DocumentRead
from app.schemas.envelope import err, ok
from app.schemas.project import ProjectCreate, ProjectDetail, ProjectListItem, ProjectRead, ProjectUpdate

router = APIRouter(tags=["projects"])


@router.post("/projects", status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Wizard create (BR-M1-006): atomic project + apps-in-scope + reuse + draft RU,
    then dispatch Requirement Understanding generation."""
    from sqlalchemy import text as sa_text

    from app.core import audit
    from app.models.app import App
    from app.models.project_intake import ProjectApp, ReuseSelection
    from app.models.understanding import RequirementUnderstanding

    # Allocate a human id (PRJ-0001) — mirrors spec version_number allocation.
    # Only numeric PRJ-NNNN ids feed the sequence; ignore non-numeric ids
    # (e.g. demo seeds like PRJ-QA01) so CAST never sees a non-integer suffix.
    max_num = await db.scalar(sa_text(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(human_id FROM 5) AS INTEGER)), 0) "
        "FROM projects WHERE human_id ~ '^PRJ-[0-9]+$'"
    ))
    human_id = f"PRJ-{(max_num or 0) + 1:04d}"

    project = Project(
        name=body.name, description=body.description, owner_id=current_user.id,
        human_id=human_id, business_unit=body.business_unit, app_scope=body.app_scope,
        status="draft",
    )
    db.add(project)
    await db.flush()

    # Apps in scope (validate they exist; onboarded check omitted intentionally)
    if body.app_ids:
        valid_ids = set((
            await db.execute(select(App.id).where(App.id.in_(body.app_ids)))
        ).scalars().all())
        for app_id in valid_ids:
            db.add(ProjectApp(project_id=project.id, app_id=app_id, included=True))

    # Reuse selections (provenance)
    for r in body.reuse:
        db.add(ReuseSelection(project_id=project.id, source_project_id=r.source_project_id,
                              asset_category=r.asset_category))

    # Draft RU placeholder
    db.add(RequirementUnderstanding(project_id=project.id, status="draft"))

    await audit.emit(db, event="project.created", actor_id=str(current_user.id),
                     metadata={"project_id": str(project.id), "human_id": human_id,
                               "app_count": len(body.app_ids)})
    await db.commit()
    await db.refresh(project)

    # Seed the similarity embedding (best-effort; never blocks create).
    from app.services.projects.embedding_service import upsert_project_embedding
    try:
        await upsert_project_embedding(project.id, db)
    except Exception:  # noqa: BLE001
        pass

    # Dispatch RU generation (waits for any sources to finish indexing).
    from workers.dispatch import dispatch
    from workers.tasks import generate_requirement_understanding
    dispatch(generate_requirement_understanding, str(project.id))

    return ok(ProjectRead.model_validate(project).model_dump(mode="json"))


@router.get("/projects")
async def list_projects(
    q: str | None = None,
    view: str = "all",
    group_by: str = "none",
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Portfolio list (BR-M1-001/003/004): RBAC-scoped search + saved view + grouping."""
    from app.services.portfolio import query_service

    rows, total, groups = await query_service.list_projects(
        db=db, user=current_user, q=q, view=view, group_by=group_by, limit=limit, offset=offset
    )
    meta = {"total": total, "limit": min(limit, 100), "offset": offset}
    if groups is not None:
        meta["groups"] = groups
        return ok([], meta)

    items = []
    for project, doc_count, latest_spec_type, open_review_count, is_stale in rows:
        item = ProjectListItem.model_validate(project)
        item.doc_count = doc_count or 0
        item.latest_spec_type = latest_spec_type
        item.open_review_count = open_review_count or 0
        item.is_stale = bool(is_stale)
        items.append(item.model_dump(mode="json"))
    return ok(items, meta)


@router.get("/projects/views")
async def project_views(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saved-view counts (BR-M1-002), RBAC-scoped."""
    from app.services.portfolio import query_service

    return ok(await query_service.view_counts(db, current_user))


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

    # ── E2 workspace panels (BR-M1-010/011) ────────────────────────────────────
    from app.models.app import App
    from app.models.audit import AuditEvent
    from app.models.gap import GapQuestion as GQ
    from app.models.project_intake import Assumption, ProjectApp
    from app.models.understanding import RequirementUnderstanding
    from app.services.quality import quality_service

    apps_rows = (
        await db.execute(
            select(ProjectApp, App.name, App.short_name, App.tier)
            .join(App, App.id == ProjectApp.app_id)
            .where(ProjectApp.project_id == project_id)
        )
    ).all()
    apps_in_scope = [
        {"app_id": str(pa.app_id), "name": name, "short_name": short, "tier": tier,
         "included": pa.included, "suggested": pa.suggested}
        for pa, name, short, tier in apps_rows
    ]

    assumptions = (
        await db.execute(select(Assumption).where(Assumption.project_id == project_id).order_by(Assumption.ext_id))
    ).scalars().all()

    open_questions = (
        await db.execute(
            select(GQ).where(GQ.project_id == project_id, GQ.source == "interview", GQ.resolved.is_(False))
            .order_by(GQ.ext_id)
        )
    ).scalars().all()

    activity = (
        await db.execute(
            select(AuditEvent).where(AuditEvent.project_id == str(project_id))
            .order_by(AuditEvent.ts.desc()).limit(15)
        )
    ).scalars().all()
    recent_activity = [
        {"event": a.event, "actor_id": a.actor_id, "ts": a.ts.isoformat(),
         "kind": "ai" if a.ai_meta else "human"}
        for a in activity
    ]

    ru_status = await db.scalar(
        select(RequirementUnderstanding.status).where(RequirementUnderstanding.project_id == project_id)
    )

    stage_progress = await quality_service.compute_stage_progress(project_id, db)
    quality = await quality_service.subscores(project_id, db)

    # Persist derived stage_progress so portfolio/triage (stale view) can read it.
    if project.stage_progress != stage_progress:
        project.stage_progress = stage_progress
        await db.commit()

    detail = ProjectDetail.model_validate(project)
    detail.documents = [DocumentRead.model_validate(d).model_dump(mode="json") for d in project.documents]
    detail.gap_count = gap_row.total
    detail.unresolved_gap_count = gap_row.unresolved
    detail.latest_specs = latest_specs
    detail.apps_in_scope = apps_in_scope
    detail.assumptions = [
        {"id": str(a.id), "ext_id": a.ext_id, "text": a.text, "confidence": a.confidence,
         "source_ref": a.source_ref, "status": a.status}
        for a in assumptions
    ]
    detail.open_questions = [
        {"id": str(q.id), "ext_id": q.ext_id, "question": q.question, "section": q.section}
        for q in open_questions
    ]
    detail.recent_activity = recent_activity
    detail.quality = quality
    detail.ru_status = ru_status

    # Stale check: any doc indexed after RU was last updated
    from app.models.understanding import RequirementUnderstanding as RU
    ru_row = (
        await db.execute(
            select(RU).where(RU.project_id == project_id)
        )
    ).scalar_one_or_none()
    docs_stale = (
        ru_row is not None
        and ru_row.status in ("in_interview", "validated")
        and any(
            d.created_at > ru_row.updated_at
            for d in project.documents
            if d.indexing_status == "done"
        )
    )
    detail.docs_stale_for_ru = docs_stale

    detail.stage_progress = stage_progress
    return ok(detail.model_dump(mode="json"))


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit project metadata (name, business unit, priority, status, go-live, app scope, …)."""
    from app.core import audit

    changes = body.model_dump(exclude_unset=True)
    app_scope_entries = changes.pop("app_scope_entries", None)

    for field, value in changes.items():
        setattr(project, field, value)

    # Diff app-scope entries when provided
    if app_scope_entries is not None:
        from app.models.app import App
        from app.models.project_intake import ProjectApp
        from sqlalchemy import delete

        new_ids = {UUID(str(e["app_id"])) for e in app_scope_entries}
        # Validate they exist (onboarded check intentionally omitted — a newly
        # registered app with no corpus yet is still a valid scope entry)
        valid_ids = set((
            await db.execute(select(App.id).where(App.id.in_(new_ids)))
        ).scalars().all())

        # Remove stale entries
        existing_rows = (
            await db.execute(select(ProjectApp).where(ProjectApp.project_id == project_id))
        ).scalars().all()
        existing_by_app: dict = {pa.app_id: pa for pa in existing_rows}

        for app_id, pa in list(existing_by_app.items()):
            if app_id not in valid_ids:
                await db.delete(pa)

        # Upsert new/updated entries
        notes_by_id = {UUID(str(e["app_id"])): e.get("impact_note") for e in app_scope_entries}
        for app_id in valid_ids:
            if app_id in existing_by_app:
                existing_by_app[app_id].included = True
                existing_by_app[app_id].impact_note = notes_by_id.get(app_id)
            else:
                db.add(ProjectApp(project_id=project_id, app_id=app_id, included=True,
                                  impact_note=notes_by_id.get(app_id)))

    await audit.emit(db, event="project.updated", actor_id=str(current_user.id),
                     metadata={"project_id": str(project_id), "fields": list(changes.keys())})
    await db.commit()
    await db.refresh(project)

    # Name/description feed the similarity embedding — refresh it (best-effort).
    if changes.keys() & {"name", "description"}:
        from app.services.projects.embedding_service import upsert_project_embedding
        try:
            await upsert_project_embedding(project_id, db)
        except Exception:  # noqa: BLE001
            pass

    return ok(ProjectRead.model_validate(project).model_dump(mode="json"))


@router.get("/projects/{project_id}/assumptions")
async def list_assumptions(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    from app.models.project_intake import Assumption
    from app.schemas.assumption import AssumptionRead

    rows = (
        await db.execute(
            select(Assumption).where(Assumption.project_id == project_id).order_by(Assumption.ext_id)
        )
    ).scalars().all()
    return ok([AssumptionRead.model_validate(a).model_dump(mode="json") for a in rows])


@router.patch("/projects/{project_id}/assumptions/{assumption_id}")
async def patch_assumption(
    project_id: UUID,
    assumption_id: UUID,
    body: AssumptionPatch,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
):
    from app.models.project_intake import Assumption
    from app.schemas.assumption import AssumptionRead

    a = (
        await db.execute(
            select(Assumption).where(Assumption.id == assumption_id, Assumption.project_id == project_id)
        )
    ).scalar_one_or_none()
    if a is None:
        err("not_found", "Assumption not found", 404)
    if body.status not in ("open", "confirmed", "rejected"):
        err("invalid_status", "status must be open|confirmed|rejected", 422)
    a.status = body.status
    await db.commit()
    await db.refresh(a)
    return ok(AssumptionRead.model_validate(a).model_dump(mode="json"))


@router.get("/projects/{project_id}/similar")
async def similar_projects(
    project_id: UUID,
    project: Project = Depends(get_project_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Projects similar to this one (for reuse discovery in the wizard, BR-M1-007)."""
    from app.services.projects.discovery_service import find_similar_projects

    results = await find_similar_projects(project_id, db)
    return ok([s.model_dump(mode="json") for s in results])


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
